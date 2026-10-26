"""Private, durable, transactional queue and account registry; no tokens stored."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import uuid

from .adapters import Blocked
from .catalog import BRANDS, RESTRICTED_HANDLES, platform

def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def normalize_schedule(value):
    if not value:
        return utc_now()
    if not isinstance(value, str):
        raise Blocked("Invalid schedule")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("Timezone missing")
        return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    except ValueError:
        raise Blocked("Schedule must include an explicit timezone") from None

def _safe(value):
    return str(value)[:100]

class Store:
    def __init__(self, location):
        path = Path(location)
        if not path.is_absolute() or path.name in ("", ".", "..") or path.is_symlink():
            raise Blocked("Use a non-symlink absolute database path")
        if not path.parent.exists() or not path.parent.is_dir() or path.parent.is_symlink():
            raise Blocked("Private DB directory missing")
        if path.parent.stat().st_mode & 0o077:
            raise Blocked("DB directory must deny group/world access")
        if path.exists():
            if not stat.S_ISREG(path.stat().st_mode) or path.stat().st_mode & 0o077:
                raise Blocked("DB file must be private regular file")
        else:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
            os.close(fd)
        self.db = sqlite3.connect(str(path), timeout=20, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=20000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self._schema()

    def _schema(self):
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS accounts (
          id TEXT PRIMARY KEY,
          brand TEXT NOT NULL, platform TEXT NOT NULL,
          destination TEXT NOT NULL, public_url TEXT NOT NULL DEFAULT '',
          instance TEXT NOT NULL DEFAULT '',
          token_env TEXT NOT NULL,
          verified INTEGER NOT NULL DEFAULT 0,
          proof TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          verified_at TEXT NOT NULL DEFAULT '',
          UNIQUE(brand, platform, destination)
        );
        CREATE TABLE IF NOT EXISTS posts (
          id TEXT PRIMARY KEY,
          brand TEXT NOT NULL, account_id TEXT NOT NULL REFERENCES accounts(id),
          payload TEXT NOT NULL, payload_hash TEXT NOT NULL,
          state TEXT NOT NULL DEFAULT 'draft', scheduled_at TEXT NOT NULL,
          approved_by TEXT NOT NULL DEFAULT '',
          approved_at TEXT NOT NULL DEFAULT '',
          remote_id TEXT NOT NULL DEFAULT '',
          note TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS api_checks (
          account_id TEXT PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
          state TEXT NOT NULL,
          provider_identity TEXT NOT NULL DEFAULT '',
          note_code TEXT NOT NULL DEFAULT '',
          checked_at TEXT NOT NULL,
          checked_by TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS api_checks_checked_at ON api_checks(checked_at);
        CREATE TABLE IF NOT EXISTS events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          subject TEXT NOT NULL, brand TEXT NOT NULL,
          actor TEXT NOT NULL, event TEXT NOT NULL,
          at TEXT NOT NULL, detail TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS posts_state_due ON posts(state,scheduled_at);
        CREATE INDEX IF NOT EXISTS posts_brand_created ON posts(brand,created_at);
        CREATE INDEX IF NOT EXISTS events_subject_id ON events(subject,id);
        """)

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def event(self, subject, brand, actor, event, detail=""):
        self.db.execute("INSERT INTO events(subject,brand,actor,event,at,detail) VALUES (?,?,?,?,?,?)",
                        (subject, brand, _safe(actor), event, utc_now(), _safe(detail)))

    def add_account(self, *, brand, platform_key, destination, public_url="", instance="", actor="system"):
        if brand not in BRANDS:
            raise Blocked("Brand not in scope")
        p = platform(platform_key)
        if not isinstance(destination, str) or not 2 <= len(destination) <= 180:
            raise Blocked("Invalid account destination")
        if not isinstance(public_url, str) or len(public_url) > 500:
            raise Blocked("Invalid public URL")
        if any(k in (destination + " " + public_url).casefold() for k in RESTRICTED_HANDLES):
            raise Blocked("Restricted account")
        if public_url and not public_url.startswith("https://"):
            raise Blocked("Public account URL must be HTTPS")
        if not isinstance(instance, str) or len(instance) > 200:
            raise Blocked("Invalid instance")
        # Enforce exactly the same network-host and forbidden-handle checks for
        # single registration as for atomic bulk import; no bypass through UI/CLI.
        from .onboarding import validate_manifest
        validate_manifest({"schema_version":1,"owner_confirmed":True,"accounts":[
            {"brand":brand,"platform":platform_key,"destination":destination,
             "public_url":public_url,"instance":instance}]})
        aid = uuid.uuid4().hex
        alias = "MPW_SOCIAL_" + brand.upper() + "_" + platform_key.upper() + "_" + aid.upper() + "_TOKEN"
        with self.transaction():
            self.db.execute("INSERT INTO accounts(id,brand,platform,destination,public_url,instance,token_env,created_at) "
                            "VALUES (?,?,?,?,?,?,?,?)",
                            (aid,brand,platform_key,destination,public_url,instance,alias,utc_now()))
            self.event(aid,brand,actor,"account_planned",p.capability)
        return aid

    def verify_account(self, account_id, *, proof, actor):
        if not isinstance(proof,str) or len(proof.strip()) < 16:
            raise Blocked("Independent ownership proof/reference required")
        with self.transaction():
            account = self.account(account_id)
            if not account:
                raise Blocked("Account not found")
            if not platform(account["platform"]).sendable:
                # Scientific and commerce profiles may have no sanctioned posting
                # API, but can still be owner-attested and listed publicly.
                if not account["public_url"]:
                    raise Blocked("Manual-only network requires a genuine public profile URL")
                from .onboarding import _valid_url
                _valid_url(account["public_url"],account["platform"],account["instance"])
            self.db.execute("UPDATE accounts SET verified=1,proof=?,verified_at=? WHERE id=?",
                            (proof.strip()[:500], utc_now(), account_id))
            self.event(account_id,account["brand"],actor,"account_verified","")

    def suspend_account(self, account_id, *, actor):
        """Immediately remove public profile, invalidate read check and stop queued sends.

        Keep private evidence and in-flight records intact for audit. The social
        provider's own token must also be revoked at its official developer portal.
        """
        with self.transaction():
            account=self.account(account_id)
            if not account:
                raise Blocked("Account to suspend not found")
            self.db.execute("UPDATE accounts SET verified=0 WHERE id=?",(account_id,))
            self.db.execute("DELETE FROM api_checks WHERE account_id=?",(account_id,))
            count=self.db.execute(
                "UPDATE posts SET state='cancelled',updated_at=? WHERE account_id=? "
                "AND state='approved'",(utc_now(),account_id)).rowcount
            inflight=self.db.execute("SELECT COUNT(*) FROM posts WHERE account_id=? "
                "AND state='dispatching'",(account_id,)).fetchone()[0]
            self.event(account_id,account["brand"],actor,"account_suspended",
                       "queued_cancelled="+str(count)+";inflight_manual_review="+str(inflight))
        return {"account_id":account_id,"state":"suspended","approved_posts_cancelled":count,
                "inflight_requires_review":inflight,"provider_token_revocation_required":True}

    def account(self, account_id):
        row = self.db.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
        return dict(row) if row else None

    def accounts(self, brand=None):
        q = "SELECT id,brand,platform,destination,public_url,instance,token_env,verified,verified_at,created_at FROM accounts"
        args = ()
        if brand:
            if brand not in BRANDS:
                raise Blocked("Brand not in scope")
            q += " WHERE brand=?"
            args = (brand,)
        return [dict(row) for row in self.db.execute(q + " ORDER BY created_at DESC",args)]

    def api_check(self, account_id):
        row=self.db.execute("SELECT state,provider_identity,note_code,checked_at,checked_by "
                            "FROM api_checks WHERE account_id=?",(account_id,)).fetchone()
        return dict(row) if row else None

    def record_api_check(self, account_id, *, status, identity, note, actor):
        if status not in ("identity_verified","credential_valid_only","failed"):
            raise Blocked("Unrecognized provider check result")
        if not isinstance(identity,str) or len(identity)>160 or any(ord(c)<32 for c in identity):
            raise Blocked("Invalid diagnostic identity")
        if not isinstance(note,str) or not re.fullmatch(r"[a-z0-9_]{3,100}",note):
            raise Blocked("Invalid diagnostic code")
        with self.transaction():
            account=self.account(account_id)
            if not account:
                raise Blocked("Account not found")
            if status=="identity_verified" and not account["verified"]:
                raise Blocked("Cannot verify an unattested account")
            now=utc_now()
            self.db.execute(
                "INSERT INTO api_checks(account_id,state,provider_identity,note_code,checked_at,checked_by) "
                "VALUES (?,?,?,?,?,?) ON CONFLICT(account_id) DO UPDATE SET "
                "state=excluded.state,provider_identity=excluded.provider_identity,"
                "note_code=excluded.note_code,checked_at=excluded.checked_at,"
                "checked_by=excluded.checked_by",
                (account_id,status,identity,note,now,_safe(actor)))
            self.event(account_id,account["brand"],actor,"provider_read_only_check",status)

    def api_checks(self, brand=None):
        q=("SELECT c.account_id,c.state,c.note_code,c.checked_at,a.brand,a.platform "
           "FROM api_checks c JOIN accounts a ON a.id=c.account_id")
        args=()
        if brand:
            if brand not in BRANDS:
                raise Blocked("Brand not in scope")
            q+=" WHERE a.brand=?"
            args=(brand,)
        return [dict(x) for x in self.db.execute(q,args)]

    def draft(self, *, account_id, content, schedule_at=None, actor):
        account = self.account(account_id)
        if not account:
            raise Blocked("Unknown account")
        if not platform(account["platform"]).sendable:
            raise Blocked("Platform cannot publish via the generic API")
        if not isinstance(content, dict) or not content or len(json.dumps(content,ensure_ascii=False)) > 180000:
            raise Blocked("Content must be a bounded object")
        if any(k in json.dumps(content,ensure_ascii=False).casefold() for k in RESTRICTED_HANDLES):
            raise Blocked("Restricted Instagram account")
        serialized = json.dumps(content,ensure_ascii=False,sort_keys=True,separators=(",",":"))
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        pid = uuid.uuid4().hex
        now = utc_now()
        with self.transaction():
            self.db.execute("INSERT INTO posts(id,brand,account_id,payload,payload_hash,state,scheduled_at,created_at,updated_at) "
                            "VALUES (?,?,?,?,?,'draft',?,?,?)",
                            (pid,account["brand"],account_id,serialized,digest,
                             normalize_schedule(schedule_at),now,now))
            self.event(pid,account["brand"],actor,"draft_created","")
        return pid

    def post(self, post_id):
        row = self.db.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
        return dict(row) if row else None

    def approve(self, post_id, actor):
        with self.transaction():
            post = self.post(post_id)
            if not post or post["state"] != "draft":
                raise Blocked("Only a draft may be approved")
            account = self.account(post["account_id"])
            if not account or not account["verified"]:
                raise Blocked("Cannot approve unverified account")
            now = utc_now()
            self.db.execute("UPDATE posts SET state='approved',approved_by=?,approved_at=?,updated_at=? WHERE id=?",
                            (_safe(actor),now,now,post_id))
            self.event(post_id,post["brand"],actor,"approved","")

    def revoke(self, post_id, actor):
        with self.transaction():
            post = self.post(post_id)
            if not post or post["state"] not in ("draft","approved"):
                raise Blocked("Post cannot be revoked after dispatch")
            self.db.execute("UPDATE posts SET state='cancelled',updated_at=? WHERE id=?",(utc_now(),post_id))
            self.event(post_id,post["brand"],actor,"cancelled","")

    def claim(self, post_id, actor="private-worker"):
        with self.transaction():
            post = self.post(post_id)
            if not post or post["state"] != "approved" or post["scheduled_at"] > utc_now():
                raise Blocked("Not approved or not due")
            account = self.account(post["account_id"])
            if not account or account["brand"] != post["brand"] or not account["verified"]:
                raise Blocked("Account not verified")
            # No automatic retry, including after a crash between external send and receipt.
            self.db.execute("UPDATE posts SET state='dispatching',updated_at=? WHERE id=?",
                            (utc_now(),post_id))
            self.event(post_id,post["brand"],actor,"dispatch_claimed","")
            return post, account

    def settle(self, post_id, state, remote_id="", note="", actor="private-worker"):
        if state not in ("published","submitted","draft_created","needs_review"):
            raise Blocked("Invalid final state")
        with self.transaction():
            post = self.post(post_id)
            if not post or post["state"] != "dispatching":
                raise Blocked("Post not in claimed state")
            if state != "needs_review" and not remote_id:
                raise Blocked("Remote receipt is required")
            self.db.execute("UPDATE posts SET state=?,remote_id=?,note=?,updated_at=? WHERE id=?",
                            (state,str(remote_id)[:500],str(note)[:500],utc_now(),post_id))
            self.event(post_id,post["brand"],actor,state,"receipt_present" if remote_id else "manual_review")

    def posts(self, brand=None, limit=100):
        limit = min(max(int(limit),1),200)
        query = ("SELECT p.id,p.brand,p.account_id,a.platform,a.destination,p.state,"
                 "p.scheduled_at,p.approved_by,p.remote_id,p.created_at,p.updated_at "
                 "FROM posts p JOIN accounts a ON p.account_id=a.id")
        args = ()
        if brand:
            if brand not in BRANDS:
                raise Blocked("Brand not in scope")
            query += " WHERE p.brand=?"
            args = (brand,)
        query += " ORDER BY p.created_at DESC LIMIT " + str(limit)
        return [dict(row) for row in self.db.execute(query,args)]

    def summary(self, brand=None):
        rows = self.posts(brand,200)
        out = {state:0 for state in ("draft","approved","dispatching","published","submitted","draft_created","needs_review","cancelled")}
        for post in rows:
            out[post["state"]] = out.get(post["state"],0)+1
        return {"recent_posts": len(rows), "accounts": len(self.accounts(brand)),
                "verified_accounts": sum(bool(a["verified"]) for a in self.accounts(brand)),
                "states": out}

    def history(self, post_id):
        return [dict(x) for x in self.db.execute(
            "SELECT actor,event,at,detail FROM events WHERE subject=? ORDER BY id DESC LIMIT 50",(post_id,))]
