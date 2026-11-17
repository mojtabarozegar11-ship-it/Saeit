#!/usr/bin/env python3
"""Read-only inventory of preexisting 2026-10-28/11-04 SQL archives on VPS.

No source table access, file creation, DB writes, restores or deletion.
Verifies a *historically known* 2.98GB archive SHA-256 if it still exists.
Scans named legacy archive directories using metadata only.
No private file names (other than previously public fixed names) in logs.
"""
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
import sys
import time

ROOT=Path("/home/githubops/.db-backups")
KNOWN={
 "pre_page_compression_20261028":{
   "name":"zomorod2_sites_main-pre-page-compression-20261028.sql.gz",
   "expected_size":2981105692,
   "expected_sha256":"9f15e25b0b7ce21dfc4588fcf15712c43add276889f44343f3c46b257f6debf39",
 },
 "live_two_tables_20261104":{
   "name":"zomorod2_sites_main-archive-live-20261104.sql.gz",
 },
}
DIRS={
 "segmented_two_tables_20261104":"zomorod2_sites_main-segments-20261104",
 "relocated_cpanel_legacy_20261104":"relocated-cpanel-legacy-20261104",
}
MAX_CHECK_S=190
MAX_ENTRIES=4000

def read_stat(path):
    try:
        st=path.lstat()
    except FileNotFoundError:
        return None
    except OSError:
        return "denied"
    if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.geteuid():
        return "not_owned_regular"
    return st

def expected_digest(path,st,expected):
    import hashlib
    before=(st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)
    sha=hashlib.sha256()
    started=time.monotonic()
    n=0
    with path.open("rb",buffering=0) as f:
        while True:
            if time.monotonic()-started>MAX_CHECK_S:
                return {"status":"TIME_BUDGET_EXCEEDED","bytes_checked":n}
            b=f.read(4*1024*1024)
            if not b:break
            n+=len(b)
            sha.update(b)
    after=path.stat(follow_symlinks=False)
    unchanged=before==(after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns)
    return {
      "status":"MATCH" if n==st.st_size and unchanged and sha.hexdigest()==expected else "MISMATCH",
      "sha256_verified":sha.hexdigest()==expected,
      "bytes_checked":n,
      "file_unchanged":unchanged,
      "hash_seconds":round(time.monotonic()-started,1),
    }

def inventory_dir(path):
    try:s=path.lstat()
    except FileNotFoundError:return {"exists":False}
    except OSError:return {"exists":False,"reason":"DENIED"}
    if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.geteuid():
        return {"exists":True,"safe_directory":False}
    count=0
    size=0
    classed={"sql_gz":0,"metadata":0,"other":0}
    classbytes={"sql_gz":0,"metadata":0,"other":0}
    largest=[]
    with os.scandir(path) as items:
        for item in items:
            count+=1
            if count>MAX_ENTRIES:
                return {"exists":True,"complete":False,"reason":"COUNT_LIMIT"}
            try:st=item.stat(follow_symlinks=False)
            except OSError:continue
            if not stat.S_ISREG(st.st_mode) or st.st_uid!=os.geteuid():continue
            x=item.name
            typ="sql_gz" if x.endswith(".sql.gz") else ("metadata" if x.endswith(".meta") or x.endswith(".json") else "other")
            classed[typ]+=1
            classbytes[typ]+=st.st_size
            size+=st.st_size
            largest.append(st.st_size)
    largest.sort(reverse=True)
    return {"exists":True,"complete":True,"files":sum(classed.values()),
      "logical_bytes":size,"file_counts":classed,"file_bytes":classbytes,
      "largest_file_bytes":largest[:5], "contents_verified":False}

def main():
    if pwd.getpwuid(os.geteuid()).pw_name!="githubops":
        raise RuntimeError("WRONG_VPS_IDENTITY")
    started=time.monotonic()
    stats=os.statvfs("/home/githubops")
    free=stats.f_bavail*stats.f_frsize
    if not ROOT.is_dir() or ROOT.is_symlink():
        raise RuntimeError("LEGACY_BACKUP_DIRECTORY_ABSENT_OR_UNSAFE")
    found={}
    for key,entry in KNOWN.items():
        f=ROOT/entry["name"]
        st=read_stat(f)
        if st is None:
            found[key]={"exists":False}
            continue
        if isinstance(st,str):
            found[key]={"exists":True,"safe":False,"reason":st}
            continue
        info={"exists":True,"safe":True,
              "size_bytes":st.st_size,"mtime_ns":st.st_mtime_ns,
              "integrity_verified_by_this_run":False}
        if "expected_size" in entry:
            info["expected_size_match"]=st.st_size==entry["expected_size"]
            if st.st_size==entry["expected_size"]:
                read=expected_digest(f,st,entry["expected_sha256"])
                info["sha256_readback"]=read
                info["integrity_verified_by_this_run"]=read["status"]=="MATCH"
        found[key]=info
    folders={k:inventory_dir(ROOT/v) for k,v in DIRS.items()}
    print("MOJ_VPS_EXISTING_SQL_ARCHIVE_CENSUS="+json.dumps({
      "schema":"moj.factory.vps.existing-sql-archives.readonly.v1",
      "vps_free_bytes_before":free,
      "vps_free_bytes_after":os.statvfs("/home/githubops").f_bavail*stats.f_frsize,
      "known_archives":found,"known_directories":folders,
      "sql_restore_proven":False,"current_live_database_backup_proven":False,
      "independent_offsite_copy_proven":False,
      "delete_permitted":False,"files_deleted":0,"files_created":0,
      "read_only":True,"elapsed_seconds":round(time.monotonic()-started,2),
    },sort_keys=True),flush=True)

if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("MOJ_VPS_EXISTING_SQL_ARCHIVE_CENSUS_FAILED="+
          type(exc).__name__+":"+str(exc)[:60],file=sys.stderr,flush=True)
        sys.exit(1)
