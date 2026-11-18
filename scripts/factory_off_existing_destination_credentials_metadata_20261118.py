#!/usr/bin/env python3
"""Owner-only READ-ONLY backup destination admission audit — FACTORY REMAINS OFF.

Never read secrets, token payloads, backups, app databases, or passphrases.
Does not query providers or run any factory code. Does not write files.
No sensitive path/owner identity, auth value, remote listing or secret names
are copied to public CI logs. Output only stable fixed-name booleans.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import sys


CANDIDATE_CONFIGS = {
    "rclone": ".config/rclone/rclone.conf",
    "gh": ".config/gh/hosts.yml",
    "docker": ".docker/config.json",
    "gcloud": ".config/gcloud/application_default_credentials.json",
    "aws": ".aws/credentials",
}
EXECUTABLES = ("rclone", "gh", "docker", "podman", "oras", "crane",
               "gcloud", "gsutil", "curl", "gzip", "openssl", "ssh")


def classify_secret_path(home: Path, relative: str, uid: int) -> str:
    """Metadata only. Return no path contents or source identities."""
    if not home.is_absolute() or relative not in CANDIDATE_CONFIGS.values():
        return "UNAPPROVED_PATH"
    root = home
    try:
        h = root.lstat()
        if not stat.S_ISDIR(h.st_mode) or h.st_uid != uid:
            return "OWNER_HOME_UNTRUSTED"
        target = home
        for part in Path(relative).parts:
            target = target / part
            st = target.lstat()
            if stat.S_ISLNK(st.st_mode) or st.st_uid != uid:
                return "UNTRUSTED"
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1:
            return "UNTRUSTED"
        if st.st_mode & 0o077:
            return "PERMISSIONS_UNSAFE"
        if not 0 < st.st_size < 1024 * 1024:
            return "UNTRUSTED"
        return "OWNER_ONLY_PRESENT"
    except FileNotFoundError:
        return "NOT_PRESENT"
    except OSError:
        return "INACCESSIBLE"


def audit_home(home: Path, uid: int, *, has_binary=shutil.which) -> dict:
    return {
        "schema": "factory.off.remote-credential-presence.metadata.v1",
        "home_is_absolute": home.is_absolute(),
        "non_root_account": uid != 0,
        "tools": {n: bool(has_binary(n)) for n in EXECUTABLES},
        "owner_only_config_presence": {
            n: classify_secret_path(home, relative, uid)
            for n, relative in CANDIDATE_CONFIGS.items()
        },
        "OAuth_working": False,
        "provider_quota_verified": False,
        "provider_private_visibility_verified": False,
        "backup_bytes_read": 0,
        "backup_bytes_uploaded": 0,
        "source_deleted": False,
        "factory_started": False,
        "cron_changed": False,
        "production_modified": False,
        "paid_services_created": False,
    }


def main() -> int:
    # local runner or owner-approved authenticated SSH-only githubops identity.
    if os.geteuid() == 0:
        print("FACTORY_OFF_DESTINATION_CREDENTIAL_AUDIT_HOLD=NON_ROOT_REQUIRED")
        return 2
    home = Path.home()
    data = audit_home(home, os.geteuid())
    print("FACTORY_OFF_DESTINATION_CREDENTIAL_AUDIT="
          + json.dumps(data, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
