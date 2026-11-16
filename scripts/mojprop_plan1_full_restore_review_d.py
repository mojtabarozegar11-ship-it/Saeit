"""D-only, read-only verifier for three-part MOJ-PROP-01 recovery evidence.

This checks private local backup bytes and an HMAC-bound independent review
receipt. A signed statement is NOT proof that this process observed a remote
restore. Never use this result alone to authorize a deployment or collect TRX.
No network, SQL, subprocess, file writes, or customer-record access.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import hmac
import json
import os
import re
import stat

SCHEMA = "mojprop.plan1.full-restore-review.d1"
DOMAIN = "mojplaywin.com"
FILES = {"db": "database.sql.gz", "app": "application.tar.gz", "media": "media.tar.gz"}
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
RUN = re.compile(r"[0-9]{1,20}\Z")
IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{3,63}\Z")
TARGET = re.compile(r"mojprop_iso_[a-z0-9_]{8,60}\Z")
TOP = {"schema", "run_id", "source_commit", "domain", "offsite_backup",
       "backups", "restore", "backup_operator", "restore_reviewer", "mac"}
RESTORE = {"target", "completed_at", "completed", "db_schema_verified",
           "db_rows_verified", "app_boot_verified", "media_files_verified",
           "tenant_isolation_verified", "production_modified"}


class FullRestoreEvidenceDenied(ValueError):
    """A non-production, independently reviewed recovery gate is not proven."""


def _check(condition: bool) -> None:
    if not condition:
        raise FullRestoreEvidenceDenied("MOJ-PROP-01 full restore evidence is incomplete or unsafe")


def _private_dir(path: Path) -> None:
    _check(path.is_absolute() and not path.is_symlink() and path.is_dir())
    _check(not any(p.is_symlink() for p in path.parents))
    info = path.stat()
    _check(info.st_uid == os.geteuid() and not stat.S_IMODE(info.st_mode) & 0o077)


def _private_file(path: Path) -> None:
    _check(not path.is_symlink() and path.is_file())
    info = path.stat()
    _check(info.st_uid == os.geteuid() and info.st_nlink == 1)
    _check(not stat.S_IMODE(info.st_mode) & 0o077)


def _moment(value: object) -> datetime:
    _check(type(value) is str and len(value) <= 40)
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise FullRestoreEvidenceDenied("invalid independent restore time") from exc
    _check(dt.tzinfo is not None and dt.utcoffset() is not None)
    return dt.astimezone(timezone.utc)


def _artifact(path: Path, entry: object) -> None:
    _check(type(entry) is dict and set(entry) == {"name", "sha256", "bytes"})
    _check(entry["name"] == path.name)
    _check(type(entry["sha256"]) is str and bool(SHA64.fullmatch(entry["sha256"])))
    _check(type(entry["bytes"]) is int and 64 <= entry["bytes"] <= 20_000_000_000)
    _private_file(path)
    _check(path.stat().st_size == entry["bytes"])
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        _check(handle.read(2) == b"\x1f\x8b")
        handle.seek(0)
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    _check(hmac.compare_digest(digest.hexdigest(), entry["sha256"]))


def verify_full_restore_review(*, root: Path, run_id: str,
                               source_commit: str, reviewer_key: bytes,
                               now: datetime | None = None) -> dict:
    """Check all three backup bytes and a reviewer-signed restore assertion.

    Runtime operator must independently inspect the isolated restoration.
    The gate ALWAYS returns deployment_authorized=False.
    """
    _check(type(run_id) is str and bool(RUN.fullmatch(run_id)))
    _check(type(source_commit) is str and bool(SHA40.fullmatch(source_commit)))
    _check(type(reviewer_key) is bytes and len(reviewer_key) >= 32)
    _check(type(root) is Path)
    _private_dir(root)
    case = root / run_id
    _private_dir(case)
    proof = case / "full-restore-review.json"
    _private_file(proof)
    _check(0 < proof.stat().st_size <= 8192)
    try:
        receipt = json.loads(proof.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise FullRestoreEvidenceDenied("invalid restore receipt") from exc
    _check(type(receipt) is dict and set(receipt) == TOP)
    _check(receipt["schema"] == SCHEMA and receipt["run_id"] == run_id
           and receipt["source_commit"] == source_commit
           and receipt["domain"] == DOMAIN and receipt["offsite_backup"] is True)
    a, b = receipt["backup_operator"], receipt["restore_reviewer"]
    _check(type(a) is str and bool(IDENTITY.fullmatch(a)))
    _check(type(b) is str and bool(IDENTITY.fullmatch(b)) and a != b)
    _check(type(receipt["mac"]) is str and bool(SHA64.fullmatch(receipt["mac"])))
    serialized = json.dumps({k: receipt[k] for k in TOP if k != "mac"},
                            sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")
    expected = hmac.new(reviewer_key, serialized, hashlib.sha256).hexdigest()
    _check(hmac.compare_digest(expected, receipt["mac"]))
    evidence = receipt["restore"]
    _check(type(evidence) is dict and set(evidence) == RESTORE)
    _check(type(evidence["target"]) is str and bool(TARGET.fullmatch(evidence["target"])))
    for field in (RESTORE - {"target", "completed_at", "production_modified"}):
        _check(evidence[field] is True)
    _check(evidence["production_modified"] is False)
    timestamp = _moment(evidence["completed_at"])
    clock = datetime.now(timezone.utc) if now is None else now
    _check(isinstance(clock, datetime) and clock.tzinfo is not None
           and clock.utcoffset() is not None)
    _check(timedelta(0) <= clock.astimezone(timezone.utc) - timestamp <= timedelta(hours=24))
    backups = receipt["backups"]
    _check(type(backups) is dict and set(backups) == set(FILES))
    for kind, name in FILES.items():
        _artifact(case / name, backups[kind])
    return {
        "schema": SCHEMA,
        "source_commit": source_commit,
        "all_three_backup_bytes_verified": True,
        "independent_reviewer_signature_verified": True,
        "remote_restore_independently_observed_by_this_process": False,
        "production_modified": False,
        "deployment_authorized": False,
        "payment_authorized": False,
    }
