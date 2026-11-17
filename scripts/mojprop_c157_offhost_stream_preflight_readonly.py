#!/usr/bin/env python3
"""C157 owner-only metadata prerequisites for an offhost encrypted DB/media stream.

Never run a dump/encryption tool, open database/media content, create a temp
archive, make a remote call or expose paths. Strictly fixed CLI and media
directory metadata under the known cPanel owner, bounded to 64 *direct*
entries each. A media directory scan is NOT a recursive backup inventory.
Presence of tools is NOT consent or key custody, quota, backup or restore.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import pwd
import stat

OWNER="zomorod2"
BASE=Path("/home/zomorod2")
MAX_ENTRIES=64
TOOL_PATHS={
    "mariadb_dump":("/usr/bin/mariadb-dump","/usr/local/bin/mariadb-dump"),
    "mysqldump":("/usr/bin/mysqldump","/usr/local/bin/mysqldump"),
    "age":("/usr/bin/age","/usr/local/bin/age"),
    "gpg":("/usr/bin/gpg","/usr/local/bin/gpg"),
    "openssl":("/usr/bin/openssl","/usr/local/bin/openssl"),
    "gzip":("/usr/bin/gzip","/bin/gzip"),
}
ALLOWED_EXEC_PREFIX=("/usr/bin/","/usr/local/bin/","/usr/lib/",
                     "/usr/local/cpanel/","/bin/")
MEDIA_CANDIDATES={
    "staging_media": BASE/"Saeit-staging"/"media",
    "staging_uploads": BASE/"Saeit-staging"/"uploads",
    "webroot_media": BASE/"mojplaywin.com"/"media",
    "webroot_uploads": BASE/"mojplaywin.com"/"uploads",
    "public_html_media": BASE/"public_html"/"media",
}
# No names of files/dirs are emitted, including in exceptions.

def _safe_executable(path: str) -> bool:
    try:
        link=os.lstat(path)
        if stat.S_ISLNK(link.st_mode):
            canonical=os.path.realpath(path)
            if (link.st_uid!=0 or canonical==path or
                    not canonical.startswith(ALLOWED_EXEC_PREFIX)):
                return False
            info=os.stat(canonical)
        else:
            info=link
        return (stat.S_ISREG(info.st_mode) and info.st_uid==0 and
                not info.st_mode & 0o022 and os.access(path,os.X_OK))
    except OSError:
        return False


def check_tools():
    return {name:any(_safe_executable(path) for path in paths)
            for name,paths in TOOL_PATHS.items()}


def private_owner_dir(path: Path, uid: int) -> bool:
    try:
        info=path.lstat()
        return (stat.S_ISDIR(info.st_mode) and info.st_uid==uid
                and not info.st_mode & 0o022)
    except OSError:
        return False


def media_metadata(path: Path, uid: int):
    out={"owner_dir_safe":False,"direct_scan_complete":False,
         "direct_regular_files":0,"direct_subdirectories":0,
         "direct_regular_bytes_upper_observed":0,"recursive_media_scope_proven":False,
         "media_content_read":False}
    if not private_owner_dir(path,uid):
        return out
    out["owner_dir_safe"]=True
    num=0;files=0;dirs=0;size=0
    try:
        with os.scandir(path) as entries:
            for entry in entries:
                num+=1
                if num>MAX_ENTRIES:
                    return out
                try:
                    meta=entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                if meta.st_uid!=uid or meta.st_mode & 0o022:
                    continue
                if stat.S_ISREG(meta.st_mode) and meta.st_nlink==1:
                    files+=1
                    size+=max(meta.st_size,0)
                elif stat.S_ISDIR(meta.st_mode):
                    dirs+=1
    except OSError:
        return out
    out.update(direct_scan_complete=True,direct_regular_files=files,
               direct_subdirectories=dirs,
               direct_regular_bytes_upper_observed=size)
    return out


def report():
    empty={"owner_dir_safe":False,"direct_scan_complete":False,
           "direct_regular_files":0,"direct_subdirectories":0,
           "direct_regular_bytes_upper_observed":0,
           "recursive_media_scope_proven":False,"media_content_read":False}
    out={"schema":"mojprop.cpanel.offhost_stream_tools.readonly.c157.v1",
         "owner_identity_verified":False,"read_only":True,
         "installed_tool_capabilities":{name:False for name in TOOL_PATHS},
         "fixed_media_candidates":{name:dict(empty) for name in MEDIA_CANDIDATES},
         "source_only_offhost_exists_from_c153":True,
         "recipient_public_key_verified":False,
         "database_connection_and_consistent_snapshot_verified":False,
         "actual_live_media_root_verified":False,
         "account_quota_verified":False,
         "offhost_db_media_restore_proven":False,
         "db_dump_executed":False,"encryption_executed":False,
         "database_or_media_contents_read":False,
         "production_deployment_authorized":False,
         "cost_incurred":False}
    try:
        if pwd.getpwuid(os.geteuid()).pw_name!=OWNER:
            return out
        out["owner_identity_verified"]=True
        out["installed_tool_capabilities"]=check_tools()
        out["fixed_media_candidates"]={
            name:media_metadata(path,os.geteuid())
            for name,path in MEDIA_CANDIDATES.items()}
    except (OSError,ValueError,KeyError):
        pass
    return out

if __name__=="__main__":
    print("MOJPROP_C157_OFFHOST_STREAM_PREFLIGHT_READONLY="+
          json.dumps(report(),separators=(",",":"),sort_keys=True))
