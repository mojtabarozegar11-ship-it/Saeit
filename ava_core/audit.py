"""Owner-scoped tamper-evident code-review event log for the unified AVA runtime.

This optional host-owned SQLite journal records hashes and event kinds, never
source code, memory text, credentials, or API requests. The secret is supplied
by the authenticated host and must be stored separately from the database.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import stat


class AuditIntegrityError(ValueError):
    """Stored sequence, owner head or authentication code was modified."""


class AuditKeyError(PermissionError):
    """The supplied audit key cannot authenticate this journal."""


@dataclass(frozen=True)
class AuditEvent:
    sequence: int
    owner_id: str
    review_id: str
    kind: str
    evidence_sha256: str
    occurred_at: str
    previous_mac: str
    mac: str


@dataclass(frozen=True)
class AuditVerification:
    owner_id: str
    event_count: int
    head_mac: str
    verified_at: str


class SQLiteCodeAuditTrail:
    """HMAC-chained, private SQLite audit with owner pseudonyms and head check.

    Detects in-place tampering and incomplete tail deletion when the head row
    remains. Cannot prove the absence of full database rollback without an
    independently stored, signed external head checkpoint.
    """

    EVENTS = frozenset({
        "review_staged", "review_evaluated_pass", "review_evaluated_fail",
        "handoff_approved", "rollback_prepared",
    })
    _HEX = re.compile(r"[0-9a-f]{64}\Z")

    def __init__(self, path: str | Path, *, key: bytes) -> None:
        if not isinstance(key, bytes) or len(key) != 32:
            raise ValueError("32-byte audit key required")
        if not isinstance(path, (str, Path)) or not str(path):
            raise ValueError("Explicit journal path required")
        target = Path(path)
        if target.is_symlink():
            raise PermissionError("Journal path cannot be a symlink")
        flags = os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(target, flags, 0o600)
        try:
            mode = os.fstat(fd).st_mode
            if not stat.S_ISREG(mode) or stat.S_IMODE(mode) & 0o077:
                raise PermissionError("Journal must be a private regular file (0600)")
        finally:
            os.close(fd)
        self._owner_key = hmac.digest(key, b"ava-audit-owner-v1", "sha256")
        self._mac_key = hmac.digest(key, b"ava-audit-mac-v1", "sha256")
        self._verifier = hmac.digest(key, b"ava-audit-key-check-v1", "sha256")
        self._db = sqlite3.connect(str(target), timeout=5)
        try:
            self._db.execute("PRAGMA trusted_schema=OFF")
            self._db.execute("PRAGMA secure_delete=ON")
            self._db.execute("PRAGMA journal_mode=DELETE")
            self._db.execute("PRAGMA synchronous=FULL")
            with self._db:
                self._db.execute(
                    "CREATE TABLE IF NOT EXISTS audit_key ("
                    "id INTEGER PRIMARY KEY CHECK (id=1), verifier BLOB NOT NULL)"
                )
                self._db.execute(
                    "CREATE TABLE IF NOT EXISTS audit_events ("
                    "id INTEGER PRIMARY KEY, owner_tag BLOB NOT NULL, "
                    "seq INTEGER NOT NULL, review_id TEXT NOT NULL, kind TEXT NOT NULL, "
                    "evidence_sha256 TEXT NOT NULL, occurred_at TEXT NOT NULL, "
                    "previous_mac TEXT NOT NULL, mac TEXT NOT NULL, "
                    "UNIQUE(owner_tag, seq))"
                )
                self._db.execute(
                    "CREATE TABLE IF NOT EXISTS audit_heads ("
                    "owner_tag BLOB PRIMARY KEY, seq INTEGER NOT NULL, mac TEXT NOT NULL)"
                )
                old = self._db.execute("SELECT verifier FROM audit_key WHERE id=1").fetchone()
                if old is None:
                    if (self._db.execute("SELECT 1 FROM audit_events LIMIT 1").fetchone()
                            or self._db.execute("SELECT 1 FROM audit_heads LIMIT 1").fetchone()):
                        raise AuditKeyError("Journal has recorded history but no key verification record")
                    self._db.execute(
                        "INSERT INTO audit_key(id, verifier) VALUES(1, ?)",
                        (self._verifier,),
                    )
                elif not hmac.compare_digest(old[0], self._verifier):
                    raise AuditKeyError("Incorrect audit journal key")
        except Exception:
            self._db.close()
            raise

    def _tag(self, owner_id: str) -> bytes:
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise ValueError("Authenticated owner_id required")
        return hmac.digest(self._owner_key, owner_id.encode("utf-8"), "sha256")

    @staticmethod
    def _payload(owner_tag: bytes, event: AuditEvent) -> bytes:
        return json.dumps({
            "owner_tag": owner_tag.hex(), "seq": event.sequence,
            "review_id": event.review_id, "kind": event.kind,
            "evidence_sha256": event.evidence_sha256,
            "occurred_at": event.occurred_at, "previous_mac": event.previous_mac,
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

    def _event_mac(self, owner_tag: bytes, event: AuditEvent) -> str:
        return hmac.new(self._mac_key, self._payload(owner_tag, event), hashlib.sha256).hexdigest()

    def _checked_events(self, owner_id: str, owner_tag: bytes) -> tuple[AuditEvent, ...]:
        rows = self._db.execute(
            "SELECT seq, review_id, kind, evidence_sha256, occurred_at, previous_mac, mac "
            "FROM audit_events WHERE owner_tag=? ORDER BY seq", (owner_tag,)
        ).fetchall()
        events = []
        previous = "0" * 64
        for seq, review_id, kind, digest, when, claimed_previous, mac in rows:
            event = AuditEvent(seq, owner_id, review_id, kind, digest, when, claimed_previous, mac)
            if (seq != len(events) + 1 or kind not in self.EVENTS
                    or not self._HEX.fullmatch(review_id) or not self._HEX.fullmatch(digest)
                    or claimed_previous != previous
                    or not hmac.compare_digest(self._event_mac(owner_tag, event), mac)):
                raise AuditIntegrityError("Audit chain authentication failed")
            events.append(event)
            previous = mac
        head = self._db.execute(
            "SELECT seq, mac FROM audit_heads WHERE owner_tag=?", (owner_tag,)
        ).fetchone()
        if head is None:
            if events:
                raise AuditIntegrityError("Missing audit head")
        elif head != (len(events), previous):
            raise AuditIntegrityError("Audit head diverges from event chain")
        return tuple(events)

    def append(self, owner_id: str, review_id: str, kind: str,
               evidence_sha256: str) -> AuditEvent:
        if (not isinstance(review_id, str) or not self._HEX.fullmatch(review_id)
                or not isinstance(evidence_sha256, str)
                or not self._HEX.fullmatch(evidence_sha256)
                or kind not in self.EVENTS):
            raise ValueError("Invalid audit event metadata")
        tag = self._tag(owner_id)
        self._db.execute("BEGIN IMMEDIATE")
        try:
            existing = self._checked_events(owner_id, tag)
            previous = existing[-1].mac if existing else "0" * 64
            event = AuditEvent(
                sequence=len(existing) + 1, owner_id=owner_id,
                review_id=review_id, kind=kind,
                evidence_sha256=evidence_sha256,
                occurred_at=datetime.now(timezone.utc).isoformat(),
                previous_mac=previous, mac="",
            )
            from dataclasses import replace
            event = replace(event, mac=self._event_mac(tag, event))
            self._db.execute(
                "INSERT INTO audit_events(owner_tag,seq,review_id,kind,evidence_sha256,"
                "occurred_at,previous_mac,mac) VALUES(?,?,?,?,?,?,?,?)",
                (tag, event.sequence, event.review_id, event.kind,
                 event.evidence_sha256, event.occurred_at,
                 event.previous_mac, event.mac),
            )
            self._db.execute(
                "INSERT INTO audit_heads(owner_tag,seq,mac) VALUES(?,?,?) "
                "ON CONFLICT(owner_tag) DO UPDATE SET seq=excluded.seq,mac=excluded.mac",
                (tag, event.sequence, event.mac),
            )
            self._db.commit()
            return event
        except Exception:
            self._db.rollback()
            raise

    def history(self, owner_id: str) -> tuple[AuditEvent, ...]:
        return self._checked_events(owner_id, self._tag(owner_id))

    def verify(self, owner_id: str) -> AuditVerification:
        events = self.history(owner_id)
        return AuditVerification(
            owner_id, len(events), events[-1].mac if events else "0" * 64,
            datetime.now(timezone.utc).isoformat(),
        )

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> SQLiteCodeAuditTrail:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()
