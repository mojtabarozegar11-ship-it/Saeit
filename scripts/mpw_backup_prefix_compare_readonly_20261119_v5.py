"""Bounded, read-only prefix proof that the fixed raw and gzip files differ.
Stops and kills only the local gzip reader after a mismatch; never changes cPanel data.
"""
import hashlib,json,os,pwd,stat,subprocess,time
from pathlib import Path
HOME=Path("/home/zomorod2")
RAW_ROOT=HOME/"Saeit-staging"/"backups"
RAW_ID="631f2edc066491c2"; RAW_SIZE=17901606016; RAW_MTIME=1795033731
SECOND_GROUP="012feef8bce02780"; SECOND_ID="a0527a9d8e6018a2"; SECOND_SIZE=2314043690; SECOND_MTIME=1795077682
WINDOW=8*1024*1024; BLOCK=1024*1024; MAX_SECONDS=60

def token(v): return hashlib.sha256(os.fsencode(str(v))).hexdigest()[:16]
def ident(s): return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
def locate(root,wanted,size,mtime,deadline):
    root=Path(root)
    if root.is_symlink() or not root.is_dir() or root.resolve()!=root: return None
    rs=root.lstat()
    if rs.st_uid!=os.geteuid(): return None
    stack=[root]; found=[]; seen=0
    while stack and time.monotonic()<deadline:
        parent=stack.pop()
        try:
            with os.scandir(parent) as entries:
                for e in entries:
                    seen+=1
                    if seen>60000 or time.monotonic()>=deadline: return None
                    s=e.stat(follow_symlinks=False)
                    if s.st_uid!=os.geteuid() or stat.S_ISLNK(s.st_mode): continue
                    p=Path(e.path)
                    if stat.S_ISDIR(s.st_mode):
                        if s.st_dev==rs.st_dev: stack.append(p)
                    elif stat.S_ISREG(s.st_mode) and s.st_size==size and int(s.st_mtime)==mtime and token(p.relative_to(HOME))==wanted:
                        found.append((p,s))
        except OSError: return None
    return found[0] if len(found)==1 else None

def main():
    out={"schema":"mpw.backup.prefix_compare.readonly.v5","read_only":True,"raw_content_disclosed":False,
         "temporary_files_created":False,"files_deleted":False,"safe_to_delete":False,
         "restore_verified":False,"prefix_equal":False,"error_category":None}
    if pwd.getpwuid(os.geteuid()).pw_name!="zomorod2":
        out["error_category"]="WRONG_ACCOUNT"; return out
    deadline=time.monotonic()+MAX_SECONDS
    roots=[p for p in HOME.iterdir() if token(p.name)==SECOND_GROUP and not p.is_symlink()]
    raw=locate(RAW_ROOT,RAW_ID,RAW_SIZE,RAW_MTIME,deadline)
    second=locate(roots[0],SECOND_ID,SECOND_SIZE,SECOND_MTIME,deadline) if len(roots)==1 else None
    out["raw_identified"]=raw is not None; out["second_identified"]=second is not None
    if not raw or not second:
        out["error_category"]="FIXED_PAIR_NOT_IDENTIFIED"; return out
    raw_path,raw_expected=raw; second_path,second_expected=second
    proc=None; raw_file=None
    try:
        raw_file=raw_path.open("rb")
        raw_before=os.fstat(raw_file.fileno())
        proc=subprocess.Popen(["gzip","-cd","--",str(second_path)],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=0)
        assert proc.stdout is not None
        offset=0
        while offset<WINDOW and time.monotonic()<deadline:
            a=raw_file.read(BLOCK); b=proc.stdout.read(BLOCK)
            n=min(len(a),len(b))
            if n and a[:n]!=b[:n]:
                for i,(x,y) in enumerate(zip(a[:n],b[:n])):
                    if x!=y:
                        out["first_mismatch_offset"]=offset+i
                        out["common_prefix_bytes"]=offset+i
                        out["error_category"]="CONTENT_MISMATCH_AT_OFFSET"
                        return out
            offset+=n
            if len(a)!=len(b):
                out["first_length_difference_offset"]=offset
                out["error_category"]="LENGTH_DIFFERENCE_IN_WINDOW"
                return out
            if not a and not b: break
        out["window_bytes_compared"]=offset
        out["prefix_equal"]=True
        out["error_category"]="NO_MISMATCH_IN_BOUNDED_WINDOW"
        return out
    except OSError:
        out["error_category"]="COMPARE_OS_ERROR"; return out
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
            try: proc.wait(timeout=10)
            except Exception: pass
        if raw_file is not None: raw_file.close()

if __name__=="__main__":
    print("MPW_BACKUP_PREFIX_COMPARE_READONLY="+json.dumps(main(),sort_keys=True),flush=True)
