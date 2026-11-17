#!/usr/bin/env python3
"""Read-only, fail-closed offsite-storage and isolated MySQL-restore admission.

Inspects VPS filesystem capacity, available backup CLIs, and existence/mode
of preselected, local account-owned configuration files ONLY. Does NOT read
credentials, environment secrets, file contents, network locations, backup
data, MySQL records, or change anything. No temp files, no writes or uploads.

A mounted filesystem is not automatically independent offsite storage.
A configured tool is not proof of a working authenticated backup destination.
"""
import json
import os
import pwd
import shutil
import stat
import sys
import time
from pathlib import Path

HOME = Path("/home/githubops")
KNOWN_DB_BYTES = 16679239680
RESTORE_OVERHEAD_FACTOR = 1.30
MIN_RESTORE_BYTES = int(KNOWN_DB_BYTES * RESTORE_OVERHEAD_FACTOR) + 2 * 1024**3
MIN_NEW_OFFSITE_BYTES = KNOWN_DB_BYTES + 2 * 1024**3
CANDIDATES = (
    ("home", HOME),
    ("known_archives", HOME / ".db-backups"),
    ("srv_backup", Path("/srv/backup")),
    ("mnt", Path("/mnt")),
    ("media", Path("/media")),
    ("tmp", Path("/tmp")),
    ("var_tmp", Path("/var/tmp")),
)
BINARIES = (
    "rclone","restic","borg","age","gpg","openssl","aws","gsutil",
    "gcloud","s3cmd","mariadb","mysql","mariadb-dump","mysqldump",
    "gzip","pigz","zstd","ssh","tar","docker","podman",
)
CONFIGS = (
    ("rclone_local_config", HOME / ".config/rclone/rclone.conf", "file"),
    ("aws_local_config", HOME / ".aws/credentials", "file"),
    ("gcloud_local_config", HOME / ".config/gcloud", "dir"),
    ("restic_local_config", HOME / ".config/restic", "dir"),
    ("ssh_local_config", HOME / ".ssh/config", "file"),
)

def existing_dir(label, p):
    try:
        st=p.lstat()
    except (FileNotFoundError,PermissionError,OSError):
        return {"present":False}
    if not stat.S_ISDIR(st.st_mode):
        return {"present":False,"reason":"NOT_REGULAR_DIRECTORY"}
    try:
        v=os.statvfs(p)
        return {
            "present":True,
            "device_id_internal":st.st_dev,
            "free_bytes_unprivileged":v.f_bavail*v.f_frsize,
            "total_bytes":v.f_blocks*v.f_frsize,
            "f_bavail_blocks":v.f_bavail,
            "readable_by_account":os.access(p,os.R_OK|os.X_OK),
            "writable_by_account":os.access(p,os.W_OK|os.X_OK),
            "read_only_fs_flag":bool(v.f_flag & getattr(os,"ST_RDONLY",1)),
        }
    except OSError:
        return {"present":True,"capacity_available":False}

def config_status(p,typ):
    try:
        st=p.lstat()
    except (FileNotFoundError,PermissionError,OSError):
        return {"exists":False}
    valid=(stat.S_ISDIR(st.st_mode) if typ=="dir" else stat.S_ISREG(st.st_mode))
    owned=(st.st_uid==os.geteuid())
    mode=stat.S_IMODE(st.st_mode)
    return {
        "exists":True,
        "regular_expected_type_and_not_symlink":valid,
        "owned_by_vps_account":owned,
        "has_world_or_group_access":bool(mode & 0o077),
        "credentials_not_read":True,
        "service_configuration_verified":False,
    }

def main():
    if pwd.getpwuid(os.geteuid()).pw_name!="githubops":
        raise RuntimeError("WRONG_VPS_ACCOUNT")
    t=time.monotonic()
    roots={}
    for label,path in CANDIDATES:
        roots[label]=existing_dir(label,path)
    home=roots["home"]
    if not home.get("present") or "device_id_internal" not in home:
        raise RuntimeError("VPS_HOME_FS_UNAVAILABLE")
    home_dev=home["device_id_internal"]
    # Expose boolean device relationships only: not actual device IDs,
    # mount paths, hostname, user info, mount options or storage tokens.
    for item in roots.values():
        dev=item.pop("device_id_internal",None)
        if dev is not None:
            item["same_filesystem_as_home"]=(dev==home_dev)
    tools={binary:bool(shutil.which(binary)) for binary in BINARIES}
    configs={label:config_status(p,typ) for label,p,typ in CONFIGS}
    destinations={
        label: {
            "plausible_separate_restore_volume":
                data.get("present",False) and
                data.get("same_filesystem_as_home") is False and
                data.get("free_bytes_unprivileged",0)>=MIN_RESTORE_BYTES and
                data.get("writable_by_account",False) and
                not data.get("read_only_fs_flag",True),
        }
        for label,data in roots.items() if label!="home"
    }
    ready=[x for x,y in destinations.items() if y["plausible_separate_restore_volume"]]
    # No provider quota, cloud connectivity, custody or restore evidence can
    # be proven from filesystem stats and installed program names alone.
    print("MOJ_FACTORY_RECOVERY_DESTINATION_ADMISSION="+json.dumps({
       "schema":"moj.factory.vps.restore-destination.readonly.v1",
       "known_live_mysql_bytes_from_prior_uapi":KNOWN_DB_BYTES,
       "conservative_isolated_restore_capacity_required_bytes":MIN_RESTORE_BYTES,
       "raw_uncompressed_offsite_admission_lower_bound_bytes":MIN_NEW_OFFSITE_BYTES,
       "filesystems":roots,
       "potential_separate_restore_volume_labels":ready,
       "backup_client_binaries_present":tools,
       "local_configuration_presence_only":configs,
       "cloud_provider_quota_authenticated":False,
       "cloud_transfer_credentials_verified":False,
       "encrypted_backup_recipient_key_recoverable":False,
       "actual_isolated_mysql_restore_verified":False,
       "complete_current_mysql_backup_verified":False,
       "source_free_space_claims_not_cpanel":True,
       "ready_to_export_live_data":False,
       "ready_to_clean_live_database":False,
       "files_created":0,"files_deleted":0,"database_rows_read":0,
       "elapsed_seconds":round(time.monotonic()-t,3),
    },sort_keys=True),flush=True)

if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("MOJ_FACTORY_RECOVERY_DESTINATION_ADMISSION_FAILED="+
              type(exc).__name__+":"+str(exc)[:65],file=sys.stderr,flush=True)
        sys.exit(1)
