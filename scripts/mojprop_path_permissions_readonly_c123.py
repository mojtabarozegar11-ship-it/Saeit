#!/usr/bin/env python3
"""C123: read-only ownership/mode classification for fixed MojProp path ancestors."""
from __future__ import annotations
import json, os, pwd, stat
from pathlib import Path

PATHS = {
    "home_parent": Path("/home"),
    "owner_home": Path("/home/zomorod2"),
    "public_webroot": Path("/home/zomorod2/mojplaywin.com"),
    "public_core": Path("/home/zomorod2/mojplaywin.com/core"),
    "public_core_management": Path("/home/zomorod2/mojplaywin.com/core/management"),
    "public_core_commands": Path("/home/zomorod2/mojplaywin.com/core/management/commands"),
    "public_config": Path("/home/zomorod2/mojplaywin.com/config"),
    "staging_root": Path("/home/zomorod2/Saeit-staging"),
    "staging_core": Path("/home/zomorod2/Saeit-staging/core"),
    "staging_config": Path("/home/zomorod2/Saeit-staging/config"),
}

def classify(path: Path, euid: int) -> dict:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {"state":"missing"}
    except OSError:
        return {"state":"unavailable"}
    is_dir = stat.S_ISDIR(info.st_mode)
    symlink = stat.S_ISLNK(info.st_mode)
    writable = bool(info.st_mode & 0o022)
    owner = info.st_uid == euid
    reasons=[]
    if symlink: reasons.append("symlink")
    if not is_dir: reasons.append("not_directory")
    if not owner: reasons.append("owner_differs")
    if writable: reasons.append("group_or_world_writable")
    return {
        "state":"inspected",
        "directory":is_dir,
        "symlink":symlink,
        "owner_matches_effective_user":owner,
        "group_or_world_writable":writable,
        "mode_octal":format(stat.S_IMODE(info.st_mode),"04o"),
        "safe_for_existing_c118_policy":bool(is_dir and not symlink and owner and not writable),
        "reasons":reasons,
    }

def report() -> dict:
    out={"schema":"mojprop.path_permissions.readonly.c123.v1","read_only":True,
         "owner_identity_verified":False,"effective_user_is_zomorod2":False,
         "paths":{},"customer_data_accessed":False,"file_contents_read":False,
         "database_accessed":False,"files_modified":False,"payment_created":False,
         "email_sent":False,"deployment_authorized":False}
    try:
        name=pwd.getpwuid(os.geteuid()).pw_name
        out["effective_user_is_zomorod2"]=(name=="zomorod2")
        out["owner_identity_verified"]=out["effective_user_is_zomorod2"]
        if not out["owner_identity_verified"]: return out
        out["paths"]={key:classify(path,os.geteuid()) for key,path in PATHS.items()}
    except (OSError,KeyError):
        pass
    return out

if __name__=="__main__":
    print("MOJPROP_C123_PATH_PERMISSIONS_READONLY="+json.dumps(report(),sort_keys=True,separators=(",",":")))
