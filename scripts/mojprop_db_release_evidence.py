"""Fail-closed, read-only verification of an independent DB restore rehearsal.

A file snapshot does NOT establish schema rollback. Deployers must furnish a
private database snapshot and a separately signed, non-production restore
rehearsal receipt bound to the exact run/commit. This module does not produce
signatures, backups, migrations, network traffic, or any customer operation.
The authorized operator must independently establish that the rehearsal ran.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import re
import stat
from pathlib import Path

_SHA = re.compile(r"[a-f0-9]{64}\Z")
_COMMIT = re.compile(r"[a-f0-9]{40}\Z")
_RUN = re.compile(r"[0-9]{1,20}\Z")
_RESTORE_NAME = re.compile(r"mojprop_restore_[a-z0-9_]{8,60}\Z")
_FIELDS = (
    "run_id", "source_commit", "snapshot_sha256", "database_identity_sha256",
    "restore_target", "restored_at", "schema_check", "row_check",
)


class MissingDatabaseRestoreEvidence(RuntimeError):
    """A live schema migration is denied until independently proven reversible."""


def _private_directory(path: Path) -> None:
    # A private file is not safe if another user can replace it by renaming
    # entries inside a group/world-writable parent directory. Also reject
    # symlink ancestors to prevent implicit redirection of the backup root.
    if path.is_symlink() or not path.is_dir():
        raise MissingDatabaseRestoreEvidence("unsafe database backup directory")
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise MissingDatabaseRestoreEvidence("database backup directory is not private")
    if any(parent.is_symlink() for parent in path.parents):
        raise MissingDatabaseRestoreEvidence("database backup has symlink ancestor")


def _private_regular(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise MissingDatabaseRestoreEvidence("private database backup/receipt not found")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise MissingDatabaseRestoreEvidence("private backup is readable by other users")


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise MissingDatabaseRestoreEvidence("invalid restore rehearsal timestamp")
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise MissingDatabaseRestoreEvidence("invalid restore rehearsal timestamp") from exc
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise MissingDatabaseRestoreEvidence("timezone-aware restore timestamp required")
    return moment.astimezone(timezone.utc)


def verify_database_restore_evidence(
    *, root: Path, run_id: str, source_commit: str,
    database_identity_sha256: str, verifier_key: bytes,
    now: datetime | None = None,
) -> dict:
    """Return proof metadata only after verifying a private backup + signed receipt.

    The secret is supplied solely at runtime by the authorized separate
    reviewer; it is never committed to GitHub, logged, or embedded in URLs.
    """
    if not (type(run_id) is str and _RUN.fullmatch(run_id)
            and type(source_commit) is str and _COMMIT.fullmatch(source_commit)
            and type(database_identity_sha256) is str
            and _SHA.fullmatch(database_identity_sha256)
            and database_identity_sha256 != "0" * 64
            and type(verifier_key) is bytes and len(verifier_key) >= 32):
        raise MissingDatabaseRestoreEvidence("missing pinned release and reviewer identity")
    if not isinstance(root, Path):
        raise MissingDatabaseRestoreEvidence("unsafe database backup directory")
    _private_directory(root)
    case = root / run_id
    _private_directory(case)
    sql = case / "full-database.sql.gz"
    proof = case / "isolated-restore-evidence.json"
    _private_regular(sql)
    _private_regular(proof)
    if not 1024 <= sql.stat().st_size <= 10_000_000_000:
        raise MissingDatabaseRestoreEvidence("backup size outside safe limits")
    with sql.open("rb") as file:
        if file.read(2) != b"\x1f\x8b":
            raise MissingDatabaseRestoreEvidence("backup is not gzip-compressed")
        file.seek(0)
        sha = hashlib.sha256()
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha.update(chunk)
    if proof.stat().st_size > 8192:
        raise MissingDatabaseRestoreEvidence("restore evidence file is too large")
    try:
        receipt = json.loads(proof.read_text("utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise MissingDatabaseRestoreEvidence("invalid restore evidence JSON") from exc
    if type(receipt) is not dict or set(receipt) != set(_FIELDS) | {"mac"}:
        raise MissingDatabaseRestoreEvidence("restore evidence fields do not match contract")
    if (receipt["run_id"] != run_id or receipt["source_commit"] != source_commit
            or receipt["snapshot_sha256"] != sha.hexdigest()
            or receipt["database_identity_sha256"] != database_identity_sha256
            or type(receipt["restore_target"]) is not str
            or _RESTORE_NAME.fullmatch(receipt["restore_target"]) is None
            or receipt["schema_check"] is not True or receipt["row_check"] is not True):
        raise MissingDatabaseRestoreEvidence("backup or independent rehearsal is not verified")
    if type(receipt["mac"]) is not str or _SHA.fullmatch(receipt["mac"]) is None:
        raise MissingDatabaseRestoreEvidence("signed restore evidence missing")
    canonical = json.dumps(
        {k: receipt[k] for k in _FIELDS},
        sort_keys=True, ensure_ascii=True, separators=(",", ":"),
    ).encode("ascii")
    expected_mac = hmac.new(verifier_key, canonical, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(receipt["mac"], expected_mac):
        raise MissingDatabaseRestoreEvidence("restore evidence signature mismatch")
    moment = datetime.now(timezone.utc) if now is None else now
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise MissingDatabaseRestoreEvidence("timezone-aware current time required")
    restored = _parse_time(receipt["restored_at"])
    age = moment.astimezone(timezone.utc) - restored
    if not timedelta(0) <= age <= timedelta(hours=24):
        raise MissingDatabaseRestoreEvidence("independent restore evidence expired or future")
    return {
        "run_id": run_id,
        "snapshot_sha256": sha.hexdigest(),
        "database_identity_sha256": database_identity_sha256,
        "restore_target": receipt["restore_target"],
        "restore_verified_at": restored.isoformat(),
        "rehearsal_receipt_verified": True,
        # Does not claim that the operator really executed the external restore.
    }
