"""MOJ-PROP-01 fail-closed fresh-backup destination *screen*, not backup execution.

Consumes sanitized, externally authenticated VPS inventory JSON and NEVER uses
provided fields as proof of live authentication. Reports mechanical blockers;
never deletes, decrypts, contacts network, receives TRX or approves production.

Existing source streamer (scripts/mojplaywin_backup_encrypt_vps_gpg.py) requires
10 GiB free BEFORE starting and retains a 3 GiB runtime hard floor. Do not
relax either threshold to pass a check. An alternate filesystem is only a
CANDIDATE: the actual streamer is fixed to the owner's home and must be
independently reviewed and authorized before any changed destination.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

GIB = 1024**3
MIN_START = 10 * GIB
MAX_SNAPSHOT_BYTES = 128 * 1024
REQUIRED = ("backend_user_authenticated", "existing_key_metadata_owner_private_32_bytes",
            "private_archive_root_owner_only", "gpg_available",
            "measured_filesystem_free_bytes", "requires_minimum_free_bytes",
            "fresh_backup_capacity_gate_passed", "candidate_locations",
            "private_archive_four_part_pair_count",
            "private_archive_partial_names_count",
            "files_deleted", "database_bytes_read", "secret_key_bytes_read",
            "backup_written", "isolated_restore_performed", "release_authorized")
CATEGORY = "READONLY_VPS_CAPACITY_FRESH_BACKUP_GATE"


class AdmissionEvidenceRejected(ValueError):
    """Malformed, fabricated or wrong-release inventory cannot unlock anything."""


def _integer(data: dict, name: str, maximum: int = 1 << 50) -> int:
    value = data.get(name)
    if type(value) is not int or value < 0 or value > maximum:
        raise AdmissionEvidenceRejected("invalid integer field: " + name)
    return value


def _boolean(data: dict, name: str) -> bool:
    value = data.get(name)
    if type(value) is not bool:
        raise AdmissionEvidenceRejected("invalid boolean field: " + name)
    return value


def inspect(snapshot: dict) -> dict:
    """Read-only screen, ALWAYS denies sales and production release.

    An inventory is evidence only if independently linked to the actual
    authenticated Actions job (the JSON cannot authenticate itself).
    """
    if type(snapshot) is not dict or snapshot.get("classification") != CATEGORY:
        raise AdmissionEvidenceRejected("expected audited backup capacity snapshot")
    if any(key not in snapshot for key in REQUIRED):
        raise AdmissionEvidenceRejected("incomplete authenticated report")
    if _boolean(snapshot, "files_deleted") or _boolean(snapshot, "database_bytes_read"):
        raise AdmissionEvidenceRejected("not a metadata-only operation")
    if _boolean(snapshot, "secret_key_bytes_read") or _boolean(snapshot, "backup_written"):
        raise AdmissionEvidenceRejected("unexpected privileged write/read")
    if _boolean(snapshot, "isolated_restore_performed") or _boolean(snapshot, "release_authorized"):
        raise AdmissionEvidenceRejected("false release claim in read-only snapshot")
    if _integer(snapshot, "requires_minimum_free_bytes") != MIN_START:
        raise AdmissionEvidenceRejected("unapproved 10 GiB threshold alteration")

    free = _integer(snapshot, "measured_filesystem_free_bytes")
    count = _integer(snapshot, "private_archive_four_part_pair_count", 10000)
    partial = _integer(snapshot, "private_archive_partial_names_count", 10000)
    identity = _boolean(snapshot, "backend_user_authenticated")
    key = _boolean(snapshot, "existing_key_metadata_owner_private_32_bytes")
    directory = _boolean(snapshot, "private_archive_root_owner_only")
    gpg = _boolean(snapshot, "gpg_available")
    claimed_capacity = _boolean(snapshot, "fresh_backup_capacity_gate_passed")
    if claimed_capacity != (free >= MIN_START):
        raise AdmissionEvidenceRejected("self-inconsistent free-capacity report")
    locations = snapshot["candidate_locations"]
    if type(locations) is not dict or len(locations) > 25:
        raise AdmissionEvidenceRejected("unsafe alternate-disk inventory")
    alternative = []
    for label, item in locations.items():
        if type(label) is not str or re.fullmatch(r"[a-z_]{1,32}", label) is None:
            raise AdmissionEvidenceRejected("invalid disk label")
        if type(item) is not dict:
            raise AdmissionEvidenceRejected("invalid mount metadata")
        actual_free = _integer(item, "free_bytes")
        same_fs = _boolean(item, "distinct_from_home_device")
        owner_private = _boolean(item, "private_existing_target")
        if _boolean(item, "has_10gib_free") != (actual_free >= MIN_START):
            raise AdmissionEvidenceRejected("mount's free disk claim inconsistent")
        if label != "home" and same_fs and owner_private and actual_free >= MIN_START:
            alternative.append(label)

    safe_to_invoke_owner_backup_workflow = (
        identity and key and directory and gpg and free >= MIN_START
    )
    reasons = []
    if not identity:
        reasons.append("owner_ssh_identity_unverified")
    if not key:
        reasons.append("existing_recovery_key_metadata_invalid")
    if not directory:
        reasons.append("private_archive_folder_unverified")
    if not gpg:
        reasons.append("gpg_executable_missing")
    if free < MIN_START:
        reasons.append("not_enough_free_bytes_to_start_10gib_workflow")
    if partial:
        reasons.append("incomplete_ciphertext_present_review_before_attempt")
    return {
        "classification": "MOJPROP_UNTRUSTED_EVIDENCE_ONLY_SAFE_BACKUP_ADMISSION",
        "product": "MOJ-PROP-01",
        "snapshot_authentication_performed_by_this_code": False,
        "observed_existing_four_file_pairs_count": count,
        "partial_archive_names_need_owner_review_count": partial,
        "fresh_backup_10gib_threshold_passed": free >= MIN_START,
        "bytes_short_of_existing_10gib_requirement": max(0, MIN_START-free),
        "all_local_runtime_prerequisites_claimed_satisfied": safe_to_invoke_owner_backup_workflow,
        "independent_private_alternate_volume_candidates": sorted(alternative),
        "alternate_volume_automatically_usable_by_existing_streamer": False,
        "blockers": reasons,
        "backup_started": False,
        "fresh_backup_proven": False,
        "independent_restore_proven": False,
        "offsite_google_drive_uploaded_proven": False,
        "owner_case_specific_confirmation_required": True,
        "real_customer_enrollment_authorized": False,
        "payment_authorized": False,
        "production_deploy_authorized": False,
        "broker_real_trades_authorized": False,
        "files_deleted": 0,
    }


def main() -> int:
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("usage: backup_release_admission.py BOUNDED_SANITIZED_JOB_JSON")
    try:
        path = Path(sys.argv[1])
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_SNAPSHOT_BYTES:
            raise AdmissionEvidenceRejected("bounded regular JSON evidence only")
        data = json.loads(path.read_text("utf-8"))
        output = inspect(data)
    except (OSError, ValueError, UnicodeError) as e:
        print("MOJPROP_BACKUP_ADMISSION=INVALID_EVIDENCE_NO_RELEASE")
        return 1
    print("MOJPROP_BACKUP_ADMISSION=" + json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
