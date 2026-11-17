#!/usr/bin/env python3
"""C120 owner cPanel existing backup catalog probe: metadata only, ZERO writes.

Calls only cPanel's documented UAPI Backup list_backups; never creates,
restores, downloads or lists archive contents. Does not assert backups are
independent, encrypted, complete, usable or already restored. Does not print
backup filenames/paths, database credentials, domains or customer details.
Official read-only operation: uapi --user=zomorod2 Backup list_backups.
"""
from __future__ import annotations

import json
import os
import pwd
import stat
import subprocess

USERNAME = "zomorod2"
UAPI_BINARY = "/usr/bin/uapi"
MAX_API_BYTES = 32768
MAX_BACKUP_ENTRIES = 100


def classify_backup_catalog(result: object) -> dict:
    """Accept only supported UAPI response schema; never emit provider data."""
    out = {"catalog_schema_recognized": False,
           "backup_entries_reported": 0,
           "completed_archive_metadata_entries": 0,
           "possible_local_account_archive_present": False}
    if type(result) is not dict:
        return out
    envelope = result.get("result")
    if (type(envelope) is not dict
            or type(envelope.get("status")) is not int
            or envelope["status"] != 1):
        return out
    data = envelope.get("data")
    if type(data) is not list or len(data) > MAX_BACKUP_ENTRIES:
        return out
    for item in data:
        if type(item) is not dict:
            return out
    completed = sum(
        1 for item in data if item.get("status") in ("complete", "completed")
        and type(item.get("file")) is str
        and 1 <= len(item["file"]) <= 255
    )
    return {
        "catalog_schema_recognized": True,
        "backup_entries_reported": len(data),
        "completed_archive_metadata_entries": completed,
        "possible_local_account_archive_present": completed > 0,
    }


def inspect() -> dict:
    result = {
        "schema": "mojprop.owner_backup_catalog.readonly.c120.v1",
        "read_only": True,
        "owner_identity_verified": False,
        "uapi_program_safe": False,
        "uapi_query_completed": False,
        "catalog_schema_recognized": False,
        "backup_entries_reported": 0,
        "completed_archive_metadata_entries": 0,
        "possible_local_account_archive_present": False,
        "backup_files_opened_or_downloaded": False,
        "customer_records_accessed": False,
        "database_accessed": False,
        "provider_offhost_backup_verified": False,
        "independent_encrypted_full_restore_proven": False,
        "production_release_authorized": False,
        "cost_incurred": False,
    }
    try:
        if pwd.getpwuid(os.geteuid()).pw_name != USERNAME:
            return result
        result["owner_identity_verified"] = True
        info = os.lstat(UAPI_BINARY)
        if (not stat.S_ISREG(info.st_mode)
                or info.st_mode & 0o022
                or info.st_uid not in (0, os.geteuid())):
            return result
        result["uapi_program_safe"] = True
        # On some cPanel installations --user is permitted only for WHM
        # administrative contexts. We have already authenticated the fixed
        # *same account* via getpwuid; retry exactly once without --user.
        # Both variants invoke only the documented read-only UAPI method.
        env = {"LC_ALL": "C", "PATH": "/usr/bin:/bin:/usr/local/bin",
               "HOME": "/home/zomorod2", "USER": USERNAME,
               "LOGNAME": USERNAME}
        for args in (
            [UAPI_BINARY, "--output=json", "--user=" + USERNAME,
             "Backup", "list_backups"],
            [UAPI_BINARY, "--output=json", "Backup", "list_backups"],
        ):
            try:
                process = subprocess.run(
                    args, capture_output=True, timeout=14,
                    check=False, env=env,
                )
            except (OSError, subprocess.SubprocessError):
                result["uapi_outcome"] = "cli_unavailable_or_failed"
                continue
            if process.returncode != 0:
                result["uapi_outcome"] = "cli_nonzero_or_feature_unavailable"
                continue
            if not 0 < len(process.stdout) <= MAX_API_BYTES:
                result["uapi_outcome"] = "cli_output_size_invalid"
                continue
            result["uapi_query_completed"] = True
            try:
                parsed = json.loads(process.stdout)
            except (UnicodeError, ValueError, TypeError):
                result["uapi_outcome"] = "cli_json_invalid"
                continue
            summary = classify_backup_catalog(parsed)
            if not summary["catalog_schema_recognized"]:
                result["uapi_outcome"] = "api_denied_or_schema_unknown"
                continue
            result.update(summary)
            result["uapi_outcome"] = "catalog_recognized"
            break
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        # Never expose subprocess stderr, backup names, private paths, IDs,
        # command output or API credentials, even on unexpected provider error.
        pass
    return result


if __name__ == "__main__":
    print("MOJPROP_C120_BACKUP_CATALOG_READONLY=" +
          json.dumps(inspect(), sort_keys=True, separators=(",", ":")))
