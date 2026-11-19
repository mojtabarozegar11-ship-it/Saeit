"""Bounded, metadata-only classification of the cPanel account disk growth.
No file contents, no deletion candidates certified, no writes to the host.
"""
import hashlib
import heapq
import json
import os
from pathlib import Path
import pwd
import stat
import time

ROOT=Path("/home/zomorod2")
KNOWN={"Saeit","Saeit-staging","restore-staging","mail","etc","logs","tmp","public_html","mojplaywin.com","zomorodmelal.ir","virtualenv","separated-backups","backups",".backups",".trash",".cache",".cpanel","softaculous_backups","backup",".git"}
MAX_ENTRIES=200000
MAX_SECONDS=55
MAX_DEPTH=40
SUFFIXES=((".sql.gz",".sql.xz",".sql.zst",".sql",".dump"),(".sqlite3",".sqlite",".db"),(".tar.gz",".tar.zst",".tgz",".tar",".zip",".7z",".bak",".gz",".zst",".enc"),(".log",".log.1"),(".py",".pyc",".html",".css",".js"),(".pdf",".epub",".docx",".png",".jpg",".jpeg",".webp",".mp4"))
LABELS=("sql_dump","database_file","archive","log","code","document_media")

def classify(name):
    lower=name.lower()
    for label,suffixes in zip(LABELS,SUFFIXES):
        if lower.endswith(suffixes):
            return label
    return "other"

def token(name):
    return hashlib.sha256(os.fsencode(name)).hexdigest()[:16]

def census(root=ROOT, *, max_entries=MAX_ENTRIES,max_seconds=MAX_SECONDS):
    root=Path(root)
    initial=root.lstat()
    uid=os.geteuid()
    if root.resolve()!=root or not stat.S_ISDIR(initial.st_mode) or initial.st_uid!=uid:
        raise ValueError("unsafe root")
    start=time.monotonic()
    cutoff=time.time()-48*3600
    pending=[(root,0)]
    seen=set()
    groups={}
    kinds={}
    largest=[]
    entries=0
    errors=0
    skipped_links=0
    skipped_mounts=0
    repeated_links=0
    depth_limited=False
    stop=None
    while pending and not stop:
        parent,depth=pending.pop()
        if depth>MAX_DEPTH:
            depth_limited=True
            continue
        try:
            with os.scandir(parent) as stream:
                for child in stream:
                    if entries>=max_entries or time.monotonic()-start>max_seconds:
                        stop="budget"
                        break
                    entries+=1
                    try:
                        s=child.stat(follow_symlinks=False)
                    except OSError:
                        errors+=1
                        continue
                    if stat.S_ISLNK(s.st_mode):
                        skipped_links+=1
                        continue
                    if s.st_dev!=initial.st_dev:
                        skipped_mounts+=1
                        continue
                    if s.st_uid!=uid:
                        errors+=1
                        continue
                    p=Path(child.path)
                    rel=p.relative_to(root)
                    first=rel.parts[0]
                    group=first if first in KNOWN else "other_"+token(first)
                    if stat.S_ISDIR(s.st_mode):
                        pending.append((p,depth+1))
                        continue
                    if not stat.S_ISREG(s.st_mode):
                        continue
                    key=(s.st_dev,s.st_ino)
                    if s.st_nlink>1:
                        if key in seen:
                            repeated_links+=1
                            continue
                        seen.add(key)
                    allocated=s.st_blocks*512
                    kind=classify(child.name)
                    for mapping,label in ((groups,group),(kinds,kind)):
                        row=mapping.setdefault(label,{"files":0,"allocated_bytes":0,"logical_bytes":0,"recently_modified_allocated_bytes":0})
                        row["files"]+=1
                        row["allocated_bytes"]+=allocated
                        row["logical_bytes"]+=s.st_size
                        if s.st_mtime>=cutoff:
                            row["recently_modified_allocated_bytes"]+=allocated
                    candidate=(allocated,token(str(rel)),kind,group,s.st_size,int(s.st_mtime),s.st_nlink)
                    if len(largest)<20:
                        heapq.heappush(largest,candidate)
                    elif candidate>largest[0]:
                        heapq.heapreplace(largest,candidate)
        except OSError:
            errors+=1
    return {"schema":"mpw.account_growth.metadata.readonly.v1","read_only":True,
            "complete":not (stop or pending or errors or skipped_mounts or depth_limited),
            "entries":entries,"errors":errors,"symlinks_skipped":skipped_links,
            "other_mounts_skipped":skipped_mounts,"hardlinks_deduplicated":repeated_links,
            "depth_limited":depth_limited,"stop_reason":stop,
            "allocated_regular_file_bytes":sum(r["allocated_bytes"] for r in kinds.values()),
            "types":kinds,"top_groups":sorted(groups.items(),key=lambda x:x[1]["allocated_bytes"],reverse=True)[:20],
            "largest_files":[{"allocated_bytes":a,"id":i,"type":k,"group":g,"logical_bytes":l,
                              "mtime_unix":m,"link_count":n} for a,i,k,g,l,m,n in sorted(largest,reverse=True)],
            "elapsed_seconds":round(time.monotonic()-start,2),
            "recent_window_hours":48,"recent_mtime_is_not_growth_proof":True,
            "contents_read":False,"files_deleted":False,"dependency_proven":False,
            "safe_to_delete":False,"release_authorized":False}

if __name__=="__main__":
    if pwd.getpwuid(os.geteuid()).pw_name!="zomorod2":
        raise SystemExit("WRONG_ACCOUNT")
    try:
        print("MPW_ACCOUNT_GROWTH_READONLY="+json.dumps(census(),sort_keys=True),flush=True)
    except Exception as exc:
        raise SystemExit("MPW_STAGING_GROWTH_FAILED="+type(exc).__name__) from None
