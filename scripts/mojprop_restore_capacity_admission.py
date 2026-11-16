"""Conservative, source-only capacity admission for an isolated Moj Prop restore.

This check NEVER performs a backup, restore, deployment or storage reservation.
Only fresh, independently measured bytes from the exact destination are valid.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import stat
import time


class CapacityAdmissionDenied(RuntimeError):
    """No verified independent restore capacity."""


@dataclass(frozen=True)
class CapacityEvidence:
    source_database_bytes: int
    source_application_bytes: int
    source_media_bytes: int
    destination_free_bytes: int
    destination_total_bytes: int
    independent_destination: bool
    encrypted_at_rest: bool
    owner_authorized: bool
    measured_at_epoch: int
    now_epoch: int
    tenant_quota_free_bytes: int | None = None
    tenant_quota_total_bytes: int | None = None
    destination_free_inodes: int | None = None
    required_restore_inodes: int | None = None
    tenant_quota_free_inodes: int | None = None
    tenant_quota_total_inodes: int | None = None


def require_restore_capacity(evidence: CapacityEvidence) -> int:
    """Return minimum required bytes; fail closed on stale or unsafe evidence.

    Budget is two full source copies plus 25% headroom, rounded up.
    Filesystem free space is not a substitute for tenant quota verification.
    This pure function validates operator-provided evidence; it does NOT
    independently attest measurement, tenancy, remote storage or backup.
    Separate signed full DB+application+media restore evidence remains mandatory.
    """
    if not isinstance(evidence, CapacityEvidence):
        raise CapacityAdmissionDenied("capacity evidence required")
    values = (
        evidence.source_database_bytes, evidence.source_application_bytes,
        evidence.source_media_bytes, evidence.destination_free_bytes,
        evidence.destination_total_bytes, evidence.measured_at_epoch,
        evidence.now_epoch,
        evidence.tenant_quota_free_bytes, evidence.tenant_quota_total_bytes,
        evidence.destination_free_inodes, evidence.required_restore_inodes,
        evidence.tenant_quota_free_inodes, evidence.tenant_quota_total_inodes,
    )
    if any(type(value) is not int or value < 0 for value in values):
        raise CapacityAdmissionDenied("invalid or unknown capacity evidence")
    if any(type(value) is not bool for value in (
        evidence.independent_destination, evidence.encrypted_at_rest,
        evidence.owner_authorized,
    )):
        raise CapacityAdmissionDenied("invalid destination attestations")
    if not all((
        evidence.independent_destination, evidence.encrypted_at_rest,
        evidence.owner_authorized,
    )):
        raise CapacityAdmissionDenied("independent authorized encrypted destination required")
    if not 0 <= evidence.now_epoch - evidence.measured_at_epoch <= 3600:
        raise CapacityAdmissionDenied("destination measurement is stale or future")
    if evidence.tenant_quota_free_bytes > evidence.tenant_quota_total_bytes:
        raise CapacityAdmissionDenied("tenant quota free exceeds quota total")
    if evidence.tenant_quota_free_inodes > evidence.tenant_quota_total_inodes:
        raise CapacityAdmissionDenied("tenant free inodes exceed tenant inode quota")
    if (evidence.required_restore_inodes == 0 or
            evidence.tenant_quota_total_inodes == 0 or
            min(evidence.destination_free_inodes, evidence.tenant_quota_free_inodes)
            < evidence.required_restore_inodes):
        raise CapacityAdmissionDenied("insufficient independently measured restore inodes and tenant inode quota")
    if (evidence.destination_total_bytes == 0 or
            evidence.tenant_quota_total_bytes == 0):
        raise CapacityAdmissionDenied("unknown destination size or tenant byte quota")
    if evidence.destination_free_bytes > evidence.destination_total_bytes:
        raise CapacityAdmissionDenied("free bytes exceed destination size")
    source = sum(values[:3])
    if source <= 0 or evidence.source_database_bytes <= 0 or evidence.source_application_bytes <= 0:
        raise CapacityAdmissionDenied("complete source inventory required")
    required = (source * 9 + 3) // 4  # 2 copies + 25% source headroom
    if min(evidence.destination_free_bytes, evidence.tenant_quota_free_bytes) < required:
        raise CapacityAdmissionDenied("insufficient verified independent restore capacity")
    return required


# A separately authorized reviewer may sign these observations AFTER
# performing a real external inventory and a successful isolated DB/app/media
# restore. A valid signature proves integrity of the *statement*, not that
# the operator honestly performed or independently witnessed the restore.
_HEX64 = re.compile(r"[a-f0-9]{64}\Z")
_COMMIT40 = re.compile(r"[a-f0-9]{40}\Z")
_RUN_ID = re.compile(r"[0-9]{1,20}\Z")
_SCHEMA = "mojprop.independent.capacity.v1"
_PROOF_KEYS = frozenset({
    "schema", "run_id", "source_commit", "database_identity_sha256",
    "snapshot_sha256", "offhost_database_sha256",
    "offhost_application_sha256", "offhost_media_sha256",
    "isolated_db_restore_verified", "isolated_app_restore_verified",
    "isolated_media_restore_verified", "capacity", "mac",
})
_CAPACITY_FIELDS = frozenset(CapacityEvidence.__dataclass_fields__) - {"now_epoch"}


def _unique_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise CapacityAdmissionDenied("duplicate capacity receipt key")
        obj[key] = value
    return obj


def require_signed_capacity_receipt(
    *, path: Path, run_id: str, source_commit: str,
    database_identity_sha256: str, snapshot_sha256: str,
    verifier_key: bytes, now_epoch: int | None = None,
) -> dict:
    """Validate separately signed complete-restore capacity proof before writes.

    The receipt belongs in the same already-verified private restore case
    directory as the full DB backup. No automatic attestation, host access,
    DB write, restoration or deployment occurs in this pure read-only gate.
    """
    if (type(run_id) is not str or _RUN_ID.fullmatch(run_id) is None
            or type(source_commit) is not str or _COMMIT40.fullmatch(source_commit) is None
            or type(database_identity_sha256) is not str
            or _HEX64.fullmatch(database_identity_sha256) is None
            or type(snapshot_sha256) is not str or _HEX64.fullmatch(snapshot_sha256) is None
            or type(verifier_key) is not bytes or len(verifier_key) < 32):
        raise CapacityAdmissionDenied("missing pinned reviewer, case or database identity")
    if not isinstance(path, Path) or path.name != "independent-restore-capacity.json":
        raise CapacityAdmissionDenied("unapproved capacity receipt pathname")
    # The outer DB proof verifier independently checks the private case root.
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise CapacityAdmissionDenied("unsafe receipt symlink")
    try:
        fd = os.open(str(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as exc:
        raise CapacityAdmissionDenied("capacity receipt unavailable") from exc
    try:
        metadata = os.fstat(fd)
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                or metadata.st_uid != os.geteuid()
                or stat.S_IMODE(metadata.st_mode) & 0o077
                or metadata.st_size < 20 or metadata.st_size > 8192):
            raise CapacityAdmissionDenied("capacity receipt is not owner-private and bounded")
        with os.fdopen(fd, "rb", closefd=False) as reader:
            raw = reader.read(8193)
        if len(raw) > 8192:
            raise CapacityAdmissionDenied("oversized capacity receipt")
    finally:
        os.close(fd)
    try:
        receipt = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs)
    except (UnicodeError, ValueError, TypeError) as exc:
        raise CapacityAdmissionDenied("invalid capacity receipt JSON") from exc
    if type(receipt) is not dict or set(receipt) != _PROOF_KEYS:
        raise CapacityAdmissionDenied("capacity receipt schema mismatch")
    if (receipt["schema"] != _SCHEMA
            or receipt["run_id"] != run_id
            or receipt["source_commit"] != source_commit
            or receipt["database_identity_sha256"] != database_identity_sha256
            or receipt["snapshot_sha256"] != snapshot_sha256
            or receipt["offhost_database_sha256"] != snapshot_sha256):
        raise CapacityAdmissionDenied("capacity receipt not bound to restored case")
    if any(
        type(receipt[field]) is not str or _HEX64.fullmatch(receipt[field]) is None
        or receipt[field] == "0" * 64
        for field in ("offhost_application_sha256", "offhost_media_sha256")
    ):
        raise CapacityAdmissionDenied("complete external app/media inventory missing")
    for field in (
        "isolated_db_restore_verified", "isolated_app_restore_verified",
        "isolated_media_restore_verified",
    ):
        if receipt[field] is not True:
            raise CapacityAdmissionDenied("isolated restoration attestation is incomplete")
    signature = receipt["mac"]
    if type(signature) is not str or _HEX64.fullmatch(signature) is None:
        raise CapacityAdmissionDenied("invalid independent reviewer signature")
    canonical = json.dumps(
        {key: receipt[key] for key in _PROOF_KEYS - {"mac"}},
        sort_keys=True, ensure_ascii=True, separators=(",", ":"),
    ).encode("ascii")
    expected = hmac.new(verifier_key, canonical, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise CapacityAdmissionDenied("capacity receipt signature mismatch")
    values = receipt["capacity"]
    if type(values) is not dict or set(values) != _CAPACITY_FIELDS:
        raise CapacityAdmissionDenied("capacity inventory is missing required evidence")
    actual_now = int(time.time()) if now_epoch is None else now_epoch
    if type(actual_now) is not int or actual_now < 1:
        raise CapacityAdmissionDenied("invalid trusted clock")
    try:
        evidence = CapacityEvidence(**values, now_epoch=actual_now)
    except (ValueError, TypeError) as exc:
        raise CapacityAdmissionDenied("capacity inventory is invalid") from exc
    required_bytes = require_restore_capacity(evidence)
    return {
        "capacity_receipt_verified": True,
        "reviewer_signed": True,
        "required_restore_bytes": required_bytes,
        "isolation_claimed_by_reviewer": True,
        # These booleans do NOT prove the operator actually restored off-host.
        "actual_remote_restore_independently_observed_by_this_code": False,
        "release_authorized": False,
    }
