"""Read-only byte-stream comparison of the fixed raw and gzip backup pair.
Reports only lengths, offsets and booleans; never emits content or creates files.
"""
import hashlib
import json
import os
import pwd
import stat
import subprocess
import time
from pathlib import Path

HOME=Path("/home/zomorod2")
RAW_ROOT=HOME/"Saeit-staging"/"backups"
RAW_ID="631f2edc066491c2"
RAW_SIZE=17901606016
RAW_MTIME=1795033731
SECOND_GROUP="012feef8bce02780"
SECOND_ID="a0527a9d8e6018a2"
SECOND_SIZE=2314043690
SECOND_MTIME=1795077682
MAX_SECONDS=420
BLOCK=1024*1024


def token(value):
    return hashlib.sha256(os.fsencode(str(value))).hexdigest()[:16]


def ident(st):
    return (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)


def locate(root,wanted,size,mtime,deadline):
    root=Path(root)
    if root.is_symlink() or not root.is_dir() or root.resolve()!=root:
        return None
    rs=root.lstat()
    if rs.st_uid!=os.geteuid():
        return None
    stack=[root]
    matches=[]
    seen=0
    while stack and time.monotonic()<deadline:
        parent=stack.pop()
        try:
            with os.scandir(parent) as entries:
                for entry in entries:
                    seen+=1
                    if seen>60000 or time.monotonic()>=deadline:
                        return None
                    s=entry.stat(follow_symlinks=False)
                    if s.st_uid!=os.geteuid() or stat.S_ISLNK(s.st_mode):
                        continue
                    p=Path(entry.path)
                    if stat.S_ISDIR(s.st_mode):
                        if s.st_dev==rs.st_dev:
                            stack.append(p)
                    elif (stat.S_ISREG(s.st_mode) and s.st_size==size
                          and int(s.st_mtime)==mtime
                          and token(p.relative_to(HOME))==wanted):
                        matches.append((p,s))
        except OSError:
            return None
    return matches[0] if len(matches)==1 else None


def base():
    return {
        "schema":"mpw.backup.pair_compare.readonly.v4",
        "read_only":True,"raw_content_disclosed":False,
        "temporary_files_created":False,"files_deleted":False,
        "safe_to_delete":False,"restore_verified":False,
        "equal_full_stream":False,"error_category":None,
    }


def main():
    out=base()
    if pwd.getpwuid(os.geteuid()).pw_name!="zomorod2":
        out["error_category"]="WRONG_ACCOUNT"; return out
    deadline=time.monotonic()+MAX_SECONDS
    roots=[p for p in HOME.iterdir() if token(p.name)==SECOND_GROUP and not p.is_symlink()]
    raw=locate(RAW_ROOT,RAW_ID,RAW_SIZE,RAW_MTIME,deadline)
    second=locate(roots[0],SECOND_ID,SECOND_SIZE,SECOND_MTIME,deadline) if len(roots)==1 else None
    out["raw_identified"]=raw is not None
    out["second_identified"]=second is not None
    if not raw or not second:
        out["error_category"]="FIXED_PAIR_NOT_IDENTIFIED"; return out
    raw_path,raw_expected=raw
    second_path,second_expected=second
    try:
        raw_file=raw_path.open("rb")
        raw_before=os.fstat(raw_file.fileno())
    except OSError:
        out["error_category"]="RAW_OPEN_FAILED"; return out
    proc=None
    try:
        proc=subprocess.Popen(["gzip","-cd","--",str(second_path)],
                              stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=0)
        assert proc.stdout is not None
        offset=0
        first_mismatch=None
        raw_extra=0
        gzip_extra=0
        while time.monotonic()<deadline:
            a=raw_file.read(BLOCK)
            b=proc.stdout.read(BLOCK)
            common=min(len(a),len(b))
            if common and a[:common]!=b[:common]:
                for i,(x,y) in enumerate(zip(a[:common],b[:common])):
                    if x!=y:
                        first_mismatch=offset+i
                        break
                out["common_prefix_bytes"]=offset+(first_mismatch-offset if first_mismatch is not None else 0)
                break
            offset+=common
            if len(a)!=len(b):
                if len(a)<len(b):
                    gzip_extra=len(b)-len(a)
                    while time.monotonic()<deadline:
                        tail=proc.stdout.read(BLOCK)
                        if not tail: break
                        gzip_extra+=len(tail)
                    out["raw_ended_first"]=True
                    out["gzip_extra_bytes"]=gzip_extra
                else:
                    raw_extra=len(a)-len(b)
                    while time.monotonic()<deadline:
                        tail=raw_file.read(BLOCK)
                        if not tail: break
                        raw_extra+=len(tail)
                    out["gzip_ended_first"]=True
                    out["raw_extra_bytes"]=raw_extra
                break
            if not a and not b:
                out["equal_full_stream"]=True
                break
        else:
            out["error_category"]="COMPARE_TIME_BUDGET"
            return out
        rc=proc.wait(timeout=30)
        out["gzip_returncode"]=rc
        out["raw_bytes_observed"]=offset
        out["first_mismatch_offset"]=first_mismatch
        out["file_sizes_fixed"]={"raw":raw_expected.st_size,"gzip":second_expected.st_size}
        out["decompressed_bytes_observed"]=offset+gzip_extra+raw_extra
        out["raw_unchanged"]=ident(os.fstat(raw_file.fileno()))==ident(raw_expected)
        out["gzip_unchanged"]=ident(second_path.stat())==ident(second_expected)
        if rc!=0:
            out["error_category"]="GZIP_STREAM_FAILED"
        elif not out["raw_unchanged"] or not out["gzip_unchanged"]:
            out["error_category"]="IDENTITY_CHANGED_DURING_COMPARE"
        elif out["equal_full_stream"]:
            out["error_category"]="NONE"
        elif first_mismatch is not None:
            out["error_category"]="CONTENT_MISMATCH_AT_OFFSET"
        elif out.get("raw_ended_first"):
            out["error_category"]="RAW_IS_PREFIX_GZIP_HAS_EXTRA_BYTES"
        elif out.get("gzip_ended_first"):
            out["error_category"]="GZIP_IS_PREFIX_RAW_HAS_EXTRA_BYTES"
        else:
            out["error_category"]="COMPARE_INCOMPLETE"
        return out
    except subprocess.TimeoutExpired:
        if proc is not None:
            proc.kill(); proc.wait()
        out["error_category"]="GZIP_WAIT_TIMEOUT"; return out
    except OSError:
        out["error_category"]="COMPARE_OS_ERROR"; return out
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill(); proc.wait()
        raw_file.close()


if __name__=="__main__":
    print("MPW_BACKUP_PAIR_COMPARE_READONLY="+json.dumps(main(),sort_keys=True),flush=True)
