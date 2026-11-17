#!/usr/bin/env python3
"""cPanel backup inventory without reading file contents or exporting private names.

Lists only numeric/status attributes from cPanel UAPI Backup::list_backups
and top-level stat() of the known .backups directory. Does NOT create,
validate, migrate or restore any backup. A listed backup is NOT recoverability.
"""
import json, os, pwd, stat, subprocess, sys, time
from pathlib import Path
USER="zomorod2"
TARGET=Path("/home/zomorod2/.backups")
MAX_ITEMS=2000

def suffix(name):
    if not isinstance(name,str):return "unknown"
    lower=name.lower()
    for ending in (".tar.gz",".sql.gz",".zip",".tar",".gz",".sql",".bak"):
        if lower.endswith(ending):return ending
    return "other"

def uapi_backup():
    try:
        p=subprocess.run(["uapi","--output=json","Backup","list_backups"],
            stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=45,check=False)
    except (OSError,subprocess.TimeoutExpired):
        return {"available":False,"reason":"UAPI_TIMEOUT_OR_EXEC_ERROR"}
    if p.returncode or len(p.stdout)>2000000:
        return {"available":False,"reason":"UAPI_NOT_AVAILABLE"}
    try:
        v=json.loads(p.stdout).get("result",{})
        if not isinstance(v,dict) or v.get("status")!=1:
            return {"available":False,"reason":"UAPI_NO_SUCCESS_STATUS"}
        data=v.get("data")
        # Different cPanel versions may use object or array representations.
        if isinstance(data,dict):
            groups=list(data.values())
            entries=[]
            for val in groups:
                if isinstance(val,list):
                    entries.extend(val)
                elif isinstance(val,dict):
                    entries.append(val)
            rows=entries
        elif isinstance(data,list):rows=data
        else:
            return {"available":False,"reason":"UAPI_BACKUP_SCHEMA_UNRECOGNIZED"}
        if len(rows)>MAX_ITEMS:
            return {"available":False,"reason":"UAPI_TOO_MANY_ENTRIES"}
        flags={"complete":0,"pending":0,"unknown":0}
        types={}
        timestamps=[]
        for row in rows:
            if not isinstance(row,dict):
                flags["unknown"]+=1;continue
            state=str(row.get("status","unknown")).lower()
            if state not in flags:state="unknown"
            flags[state]+=1
            ext=suffix(row.get("file") or row.get("filename") or row.get("name"))
            types[ext]=types.get(ext,0)+1
            stamp=row.get("time") or row.get("timestamp")
            if isinstance(stamp,(int,float)) and stamp>1000000000 and stamp<3000000000:
                timestamps.append(int(stamp))
        return {"available":True,"entries":len(rows),"states":flags,
                "filetype_counts":types,
                "earliest_unix_time":min(timestamps) if timestamps else None,
                "latest_unix_time":max(timestamps) if timestamps else None,
                "remote_backup_proven":False,"restore_proven":False,
                "raw_filenames_not_disclosed":True}
    except (ValueError,TypeError,KeyError):
        return {"available":False,"reason":"UAPI_PARSE_ERROR"}

def disk_inventory():
    try:s=TARGET.lstat()
    except OSError:
        return {"available":False,"reason":"DIRECTORY_MISSING_OR_DENIED"}
    if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.geteuid() or TARGET.is_symlink():
        return {"available":False,"reason":"DIRECTORY_NOT_OWNED_OR_UNSAFE"}
    counts={"regular_files":0,"directories":0,"symlinks":0,"other":0}
    ext_counts={}
    total_regular_bytes=0
    top_sizes=[]
    entries=0
    try:
        with os.scandir(TARGET) as iterator:
            for entry in iterator:
                entries+=1
                if entries>MAX_ITEMS:
                    return {"available":False,"reason":"TOO_MANY_TOP_LEVEL_ITEMS"}
                try:st=entry.stat(follow_symlinks=False)
                except OSError:continue
                if stat.S_ISREG(st.st_mode):
                    counts["regular_files"]+=1
                    total_regular_bytes+=st.st_size
                    kind=suffix(entry.name)
                    ext_counts[kind]=ext_counts.get(kind,0)+1
                    top_sizes.append((st.st_size,int(st.st_mtime)))
                elif stat.S_ISDIR(st.st_mode):counts["directories"]+=1
                elif stat.S_ISLNK(st.st_mode):counts["symlinks"]+=1
                else:counts["other"]+=1
    except OSError:
        return {"available":False,"reason":"DIRECTORY_ACCESS_FAILED"}
    top_sizes.sort(reverse=True)
    return {"available":True,"top_level_entries":entries,
            "counts":counts,"filetype_counts":ext_counts,
            "regular_files_logical_bytes":total_regular_bytes,
            "top_five_file_size_and_mtime":top_sizes[:5],
            "directory_contents_scanned_recursively":False,
            "backup_integrity_verified":False,
            "filenames_disclosed":False}

def main():
    if pwd.getpwuid(os.geteuid()).pw_name!=USER:
        raise RuntimeError("WRONG_ACCOUNT")
    started=time.monotonic()
    backup=uapi_backup()
    disk=disk_inventory()
    print("MOJ_FACTORY_CPANEL_EXISTING_BACKUPS="+json.dumps({
        "schema":"moj.factory.cpanel.backup-availability.readonly.v1",
        "official_backup_list":backup,
        "account_backups_directory":disk,
        "read_only":True,
        "any_backup_restorable_proven":False,
        "offhost_copy_proven_by_this_check":False,
        "safe_to_delete":False,"files_deleted":0,"files_created":0,
        "elapsed_seconds":round(time.monotonic()-started,2)
    },sort_keys=True),flush=True)

if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("MOJ_FACTORY_CPANEL_EXISTING_BACKUPS_FAILED="+type(exc).__name__+
              ":"+str(exc)[:60],file=sys.stderr,flush=True)
        sys.exit(1)
