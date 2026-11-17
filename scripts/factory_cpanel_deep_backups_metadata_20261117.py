#!/usr/bin/env python3
"""Bounded metadata-only recursive census of cPanel .backups.

No file content, no path/name disclosure, no symlink traversal,
no writes or restoration. A file named backup is NOT recoverability proof.
"""
import json,os,pwd,stat,sys,time
from pathlib import Path
ROOT=Path("/home/zomorod2/.backups")
MAX_ENTRIES=60000
MAX_DEPTH=7
MAX_SECONDS=70
SUFFIXES=(".sql.gz",".sql.zst",".sql.xz",".sql",".sqlite3",".sqlite",".tar.gz",
          ".tgz",".zip",".zst",".gz",".f01enc",".bak",".dump")

def classified(name):
    s=name.lower()
    for suffix in SUFFIXES:
        if s.endswith(suffix):return suffix
    return "other"

def census():
    t0=time.monotonic()
    rst=ROOT.lstat()
    if not stat.S_ISDIR(rst.st_mode) or rst.st_uid!=os.geteuid() or ROOT.is_symlink():
        raise RuntimeError("BACKUP_DIR_UNSAFE")
    pending=[(str(ROOT),0)]
    data={"files":0,"directories":0,"symlinks":0,"other":0,
          "unreadable":0,"total_logical_file_bytes":0,
          "extension_counts":{},"extension_bytes":{},"largest_files_unnamed":[],
          "potential_database_archive_files":0,"potential_database_archive_bytes":0}
    top=[]
    complete=True
    while pending:
        if time.monotonic()-t0>MAX_SECONDS:
            complete=False;data["stop_reason"]="TIME_BUDGET";break
        parent,depth=pending.pop()
        if depth>=MAX_DEPTH:
            complete=False;data["stop_reason"]="DEPTH_BUDGET";break
        try:
            entries=os.scandir(parent)
            with entries as stream:
                for child in stream:
                    if (sum(data[k] for k in ("files","directories","symlinks","other","unreadable"))>=MAX_ENTRIES
                            or time.monotonic()-t0>MAX_SECONDS):
                        complete=False;data["stop_reason"]="ENTRY_OR_TIME_BUDGET";break
                    try:s=child.stat(follow_symlinks=False)
                    except OSError:data["unreadable"]+=1;continue
                    if stat.S_ISLNK(s.st_mode):
                        data["symlinks"]+=1;continue
                    if stat.S_ISDIR(s.st_mode):
                        data["directories"]+=1
                        if s.st_uid==os.geteuid():
                            pending.append((child.path,depth+1))
                        else:data["unreadable"]+=1
                        continue
                    if not stat.S_ISREG(s.st_mode):
                        data["other"]+=1;continue
                    data["files"]+=1
                    data["total_logical_file_bytes"]+=s.st_size
                    typ=classified(child.name)
                    data["extension_counts"][typ]=data["extension_counts"].get(typ,0)+1
                    data["extension_bytes"][typ]=data["extension_bytes"].get(typ,0)+s.st_size
                    if typ in (".sql.gz",".sql.zst",".sql.xz",".sql",".sqlite3",".sqlite",".dump"):
                        data["potential_database_archive_files"]+=1
                        data["potential_database_archive_bytes"]+=s.st_size
                    # Type and timestamp only; no identifiers or filenames.
                    top.append((s.st_size,int(s.st_mtime),typ))
                if not complete:break
        except OSError:
            data["unreadable"]+=1
    top.sort(reverse=True)
    data["top_twelve_unnamed"]=[{"size_bytes":s,"mtime_unix":tm,"suffix":ty}
         for s,tm,ty in top[:12]]
    del data["largest_files_unnamed"]
    data["complete"]=complete and not pending
    data["elapsed_seconds"]=round(time.monotonic()-t0,2)
    data["no_file_content_read"]=True
    data["database_integrity_proven"]=False
    data["offline_restore_proven"]=False
    data["offhost_copy_proven"]=False
    return data

def main():
    if pwd.getpwuid(os.geteuid()).pw_name!="zomorod2":raise RuntimeError("WRONG_ACCOUNT")
    print("MOJ_FACTORY_CPANEL_DEEP_BACKUP_CENSUS="+json.dumps({
      "schema":"moj.factory.cpanel.deep-backups.metadata-only.v1",
      "inventory":census(),
      "readonly":True,"safe_to_delete":False,
      "files_created":0,"files_deleted":0
    },sort_keys=True),flush=True)

if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("MOJ_FACTORY_CPANEL_DEEP_BACKUP_CENSUS_FAILED="+type(exc).__name__+
              ":"+str(exc)[:70],file=sys.stderr,flush=True)
        sys.exit(1)
