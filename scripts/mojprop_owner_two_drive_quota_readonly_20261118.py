"""Owner-only read-only two-Drive OAuth identity / capacity preflight.

No backup transfer, no upload, no SQL, no customer records. Reads owner-private
rclone configuration only when a secure file exists, verifies BOTH private
historical proof objects and uses provider API rclone about to observe quotas.
Actual backup admission remains separate: this merely probes a SMALL fixed
1 MiB reference stream and must never imply capacity for a real backup.

The rclone client may refresh its own OAuth token when reading provider data;
that does NOT mutate customer records or any cloud backup object. No token,
proof content, filenames, OAuth response, secret, or provider error is printed.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil

from factory_rclone_dual_parts import (
    RcloneDualStore, TransferHold, _mode_secure_file,
)

_ROOT_A = "191sAkv4A01S9o6zhx-vM5xM7WO31qHPn"
_ROOT_B = "1e6D3Ek4k-4JT_oyEoiY_JejErZFssrC_"
_PROOF_PATH = "F-01 Factory VPS encrypted recovery 2026-10-30/manifest.json"
_PROOF_SHA256 = "753365e1584a228d4a4b60b1f7bc21dabdf9514dfc1fe362b5257326768233da"
# Fixed *small* diagnostic upper bound. This is NOT the live DB+media
# capacity requirement; each real stream needs a separately vetted bound.
_DIAGNOSTIC_SOURCE_BYTES = 1 * 1024 * 1024
_DIAGNOSTIC_RESERVE_BYTES = 1 * 1024 * 1024
_REASON_CODES = frozenset({
    "UNSAFE_OR_MISSING_OWNER_CONFIG", "OWNER_CONFIG_CHANGED",
    "OWNER_CONFIG_UNREADABLE", "OWNER_DRIVE_REMOTE_CONFIG_UNVERIFIED",
    "SAME_OAUTH_CREDENTIALS_REJECTED", "PRIVATE_OWNER_PROOF_MISMATCH",
    "DRIVE_FREE_QUOTA_NOT_PROVEN", "INSUFFICIENT_PROVIDER_VERIFIED_FREE_BYTES",
    "RCLONE_NOT_INSTALLED", "RCLONE_TIMEOUT", "RCLONE_EXECUTABLE_MISSING",
    "RCLONE_PIPELINE_FAILURE", "RCLONE_PROVIDER_OPERATION_FAILED",
    "RCLONE_OUTPUT_OVERSIZE", "UNTRUSTED_REMOTE_IDENTITY_OR_PROOF",
})


def readiness(*, config: Path | None = None, rclone_exe: str | None = None) -> dict:
    result = {
        "schema": "mojprop.owner-two-drive-metadata-readonly.v1",
        "config_present_private": False,
        "rclone_verified_executable_available": False,
        "distinct_oauth_and_private_owner_proofs": False,
        "provider_quota_observed": False,
        "diagnostic_1mib_source_bound_admitted": False,
        "full_current_backup_capacity_admitted": False,
        "current_db_media_backup_created": False,
        "independent_restore_performed": False,
        "cloud_objects_written_or_deleted": False,
        "customer_data_queried": False,
        "oauth_tokens_printed": False,
        "real_payment_created": False,
        "status": "MISSING_OWNER_AUTH",
    }
    path = config or (Path.home() / ".config/rclone/rclone.conf")
    if not _mode_secure_file(path):
        return result
    result["config_present_private"] = True
    exe = rclone_exe or shutil.which("rclone")
    if not exe or not Path(exe).is_absolute() or not Path(exe).is_file():
        result["status"] = "NO_PINNED_RCLONE_BINARY"
        return result
    result["rclone_verified_executable_available"] = True

    # Caller/CI must have verified a pinned rclone ZIP SHA256 before invoking.
    try:
        store = RcloneDualStore(
            path, remote_a="factory_a", remote_b="factory_b",
            expected_root_a=_ROOT_A, expected_root_b=_ROOT_B,
            proof_path=_PROOF_PATH, proof_sha256=_PROOF_SHA256,
            max_source_bytes=_DIAGNOSTIC_SOURCE_BYTES,
            chunk_bytes=_DIAGNOSTIC_SOURCE_BYTES,
            free_reserve_bytes=_DIAGNOSTIC_RESERVE_BYTES,
            rclone_exe=exe,
        )
        record = store.preflight()
        result["distinct_oauth_and_private_owner_proofs"] = (
            record.proof_readbacks_verified and record.distinct_private_roots
        )
        result["provider_quota_observed"] = (
            type(record.free_a_before) is int and
            type(record.free_b_before) is int
        )
        result["diagnostic_1mib_source_bound_admitted"] = True
        # Those values are metadata, not secrets, but avoid leaking account
        # utilization to public GitHub logs. The manager may securely inspect
        # private auth/quota on their own host; our pass/fail is sufficient.
        result["status"] = "READONLY_PROVIDER_DIAGNOSTIC_OK"
    except TransferHold as exc:
        code = str(exc)
        result["status"] = code if code in _REASON_CODES else "READONLY_PROVIDER_PROBE_FAILED"
    except Exception:
        result["status"] = "UNEXPECTED_METADATA_PROBE_FAILURE"
    return result


if __name__ == "__main__":
    print("MOJPROP_OWNER_TWO_DRIVE_READONLY=" +
          json.dumps(readiness(
              rclone_exe=os.environ.get("MOJPROP_READONLY_RCLONE_EXE"),
          ), sort_keys=True, separators=(",", ":")))
