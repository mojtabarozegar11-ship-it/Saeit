"""Fail-closed direct publisher for the Mojtaba / Zomorod / MojPlayWin hub.

Standalone infrastructure, NOT installed as a Django route or scheduled worker.
No credentials are stored in source, no external POST occurs by default.
Production execution requires all independent gates including a verified target,
brand-isolated token, explicit approval, execution flag, and durable SQLite ledger.
Supported posting adapters: Telegram Bot API and Discord Bot API.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

BRANDS = frozenset({"personal", "zomorod", "mojplaywin"})
ADAPTERS = frozenset({"telegram", "discord"})
MAX_TEXT = {"telegram": 4096, "discord": 2000}
PLATFORM_LIMITS = {
    "telegram": "Bot API: bot must administer the destination",
    "discord": "Bot API: bot must have send-message permission",
}
_RESTRICTED = "dr.mojtaba.rozegar"


class PublicationBlocked(ValueError):
    """Request must not cause an external publication."""


class PublishUncertain(RuntimeError):
    """No automatic retry: outcome could be unknown."""


def _env_prefix(brand: str, platform: str) -> str:
    return "MPW_SOCIAL_" + brand.upper() + "_" + platform.upper()


def _validated(job: dict) -> dict:
    if not isinstance(job, dict):
        raise PublicationBlocked("job must be an object")
    brand, platform = job.get("brand"), job.get("platform")
    if brand not in BRANDS or platform not in ADAPTERS:
        raise PublicationBlocked("unsupported brand or publishing adapter")
    text, destination = job.get("text"), job.get("destination")
    if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT[platform]:
        raise PublicationBlocked("invalid text or platform length")
    if not isinstance(destination, str) or not destination or len(destination) > 120:
        raise PublicationBlocked("invalid destination")
    if _RESTRICTED in (destination + " " + text).casefold():
        raise PublicationBlocked("restricted Instagram account cannot be promoted")
    if platform == "telegram":
        if not re.fullmatch(r"(?:-?[0-9]{5,20}|@[A-Za-z][A-Za-z0-9_]{4,31})", destination):
            raise PublicationBlocked("unsupported Telegram target identifier")
    if platform == "discord" and not re.fullmatch(r"[0-9]{15,22}", destination):
        raise PublicationBlocked("unsupported Discord channel identifier")
    job_id = job.get("job_id")
    if not isinstance(job_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,96}", job_id):
        raise PublicationBlocked("job_id must be a stable unique identifier")
    return {
        "brand": brand, "platform": platform, "text": text, "destination": destination,
        "job_id": job_id, "approved": job.get("approved") is True,
        "approval_id": job.get("approval_id"),
    }


def _fingerprint(job: dict) -> str:
    raw = json.dumps([job[k] for k in ("brand", "platform", "destination", "text")],
                     ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def readiness(job: dict, environ=None) -> dict:
    """Safe preview: never reveals tokens, never opens a socket or writes files."""
    job = _validated(job)
    env = os.environ if environ is None else environ
    prefix = _env_prefix(job["brand"], job["platform"])
    destinations = {s.strip() for s in env.get(prefix + "_VERIFIED_TARGETS", "").split(",") if s.strip()}
    checks = {
        "owner_verified_destination": job["destination"] in destinations,
        "brand_token_configured": bool(env.get(prefix + "_TOKEN", "").strip()),
        "operator_approval": job["approved"] and isinstance(job["approval_id"], str)
                             and 4 <= len(job["approval_id"]) <= 100,
        "execution_gate_enabled": env.get("MPW_SOCIAL_EXECUTION_ENABLED") == "1",
    }
    return {
        "job_id": job["job_id"], "brand": job["brand"], "platform": job["platform"],
        "destination": job["destination"], "fingerprint": _fingerprint(job),
        "checks": checks, "can_execute": all(checks.values()),
        "mode": "preview_only",
    }


def _transport(req, timeout=15):
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status, response.read(8192)
    except urllib.error.HTTPError as exc:
        # Never log remote error bodies or exception URLs; Telegram token is in the URL.
        raise PublishUncertain("upstream HTTP status " + str(exc.code)) from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise PublishUncertain("upstream communication failed; reconcile manually") from None


def _request(job: dict, token: str) -> urllib.request.Request:
    if job["platform"] == "telegram":
        if not re.fullmatch(r"[0-9]{5,15}:[A-Za-z0-9_-]{20,100}", token):
            raise PublicationBlocked("Telegram token format invalid")
        # Token is private and must never be returned in output or logs.
        url = "https://api.telegram.org/bot" + token + "/sendMessage"
        body = {"chat_id": job["destination"], "text": job["text"]}
        headers = {"Content-Type": "application/json"}
    else:
        url = "https://discord.com/api/v10/channels/" + job["destination"] + "/messages"
        body = {"content": job["text"], "allowed_mentions": {"parse": []}}
        headers = {"Content-Type": "application/json", "Authorization": "Bot " + token}
    return urllib.request.Request(url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                                  headers=headers, method="POST")


def publish(job: dict, *, ledger_path, environ=None, transport=None) -> dict:
    """Execute one approved publication once; ambiguous failures require manual reconciliation.

    ledger_path must be a persistent volume in a private directory with restricted access.
    The caller is responsible for authentication, actual approval verification and
    verification of account ownership before populating *_VERIFIED_TARGETS.
    """
    job = _validated(job)
    env = os.environ if environ is None else environ
    snapshot = readiness(job, env)
    if not snapshot["can_execute"]:
        raise PublicationBlocked("publication blocked: " + ",".join(k for k,v in snapshot["checks"].items() if not v))
    if ledger_path is None:
        raise PublicationBlocked("persistent ledger path required")
    prefix = _env_prefix(job["brand"], job["platform"])
    req = _request(job, env[prefix + "_TOKEN"].strip())
    transport = transport or _transport
    path = Path(ledger_path)
    if not path.parent.is_dir():
        raise PublicationBlocked("ledger directory must already exist")
    if path.parent.stat().st_mode & 0o077:
        raise PublicationBlocked("ledger directory must deny group/world access")
    if path.is_symlink():
        raise PublicationBlocked("ledger cannot be a symlink")
    if path.exists():
        if not path.is_file() or path.stat().st_mode & 0o077:
            raise PublicationBlocked("existing ledger must be a private regular file")
    else:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
            os.close(fd)
        except FileExistsError:
            raise PublicationBlocked("ledger appeared during preflight") from None
    conn = sqlite3.connect(str(path), timeout=15, isolation_level=None)
    try:
        conn.execute("PRAGMA busy_timeout=15000")
        conn.execute("CREATE TABLE IF NOT EXISTS publications "
                     "(job_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, state TEXT NOT NULL, "
                     "remote_id TEXT NOT NULL DEFAULT '')")
        conn.execute("BEGIN IMMEDIATE")
        old = conn.execute("SELECT fingerprint,state FROM publications WHERE job_id=?",
                           (job["job_id"],)).fetchone()
        if old:
            conn.execute("ROLLBACK")
            if old[0] != snapshot["fingerprint"]:
                raise PublicationBlocked("job_id reuse with changed content")
            raise PublicationBlocked("job already attempted: " + old[1] + "; no automatic retry")
        conn.execute("INSERT INTO publications(job_id,fingerprint,state) VALUES (?,?,?)",
                     (job["job_id"], snapshot["fingerprint"], "inflight"))
        conn.execute("COMMIT")
        try:
            status, data = transport(req)
            if not 200 <= status < 300:
                raise PublishUncertain("upstream HTTP status " + str(status))
            response = json.loads(data)
            if job["platform"] == "telegram":
                if response.get("ok") is not True:
                    raise PublishUncertain("Telegram did not confirm publication")
                remote_id = str((response.get("result") or {}).get("message_id", ""))
            else:
                remote_id = str(response.get("id", ""))
            if not remote_id:
                raise PublishUncertain("remote publication ID was missing")
        except Exception:
            conn.execute("UPDATE publications SET state='needs_review' WHERE job_id=?", (job["job_id"],))
            # Never retry automatically; an HTTP timeout may follow a successful send.
            raise PublishUncertain("publication outcome requires manual reconciliation") from None
        conn.execute("UPDATE publications SET state='published',remote_id=? WHERE job_id=?",
                     (remote_id, job["job_id"]))
        return {"job_id": job["job_id"], "platform": job["platform"],
                "brand": job["brand"], "status": "published", "remote_id": remote_id}
    finally:
        conn.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description="Personal-site social publisher: preview by default")
    parser.add_argument("--job", required=True, help="JSON file with a single publication")
    parser.add_argument("--execute", action="store_true", help="Explicitly request real publication")
    parser.add_argument("--ledger", help="Existing private directory / persistent SQLite ledger path")
    args = parser.parse_args(argv)
    try:
        job = json.loads(Path(args.job).read_text(encoding="utf-8"))
        if args.execute:
            result = publish(job, ledger_path=args.ledger)
        else:
            result = readiness(job)
    except (PublicationBlocked, PublishUncertain, ValueError, OSError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
