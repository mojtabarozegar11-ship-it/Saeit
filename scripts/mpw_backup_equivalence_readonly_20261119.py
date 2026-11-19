"""Owner-local equivalence proof of two fixed, previously observed backup files.
No output of raw content, paths or digests. No writes, deletes or restore.
"""
import os, stat, time, hashlib, gzip, json, pwd
from pathlib import Path
HOME=Path("/home/zomorod2")
RAW_ID="631f2edc066491c2"
RAW_SIZE=17901606016
RAW_MTIME=1795033731
SECOND_GROUP="012feef8bce02780"
SECOND_ID="a0527a9d8e6018a2"
SECOND_SIZE=2314043690
SECOND_MTIME=1795077682

def token(p):
    return hashlib.sha256(os.fsencode(str(p))).hexdigest()[:16]

def ident(s):
    return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)

def find(root, wanted, size, mtime):
    if root.resolve()!=root or not root.is_dir() or root.lstat().st_uid!=os.geteuid():
        return None
    stack=[root]; n=0; matches=[]
    deadline=time.monotonic()+15
    while stack:
        parent=stack.pop()
        with os.scandir(parent) as it:
            for e in it:
                n+=1
                if n>20000 or time.monotonic()>deadline:
                    return None
                s=e.stat(follow_symlinks=False)
                if s.st_uid!=os.geteuid() or stat.S_ISLNK(s.st_mode):
                    continue
                p=Path(e.path)
                if stat.S_ISDIR(s.st_mode):
                    if s.st_dev==root.lstat().st_dev: stack.append(p)
                elif stat.S_ISREG(s.st_mode) and s.st_size==size and int(s.st_mtime)==mtime and token(p.relative_to(HOME))==wanted:
                    matches.append((p,s))
    return matches[0] if len(matches)==1 else None

def open_fixed(pair):
    p,s=pair
    f=os.fdopen(os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NOATIME),"rb")
    if ident(os.fstat(f.fileno()))!=ident(s) or not stat.S_ISREG(s.st_mode):
        f.close()
        raise ValueError("identity changed")
    return f

def digest_stream(f,limit,deadline):
    h=hashlib.sha256(); n=0
    while True:
        if time.monotonic()>deadline:
            raise TimeoutError("budget")
        b=f.read(1024*1024)
        if not b: break
        n+=len(b)
        if n>limit: raise ValueError("size bound")
        h.update(b)
    return n,h.digest()

def audit():
    out={"read_only":True,"raw_content_disclosed":False,"files_deleted":False,
         "restore_verified":False,"safe_to_delete":False,"equivalent":False}
    if pwd.getpwuid(os.geteuid()).pw_name!="zomorod2": return out
    roots=[p for p in HOME.iterdir() if token(p.name)==SECOND_GROUP and not p.is_symlink()]
    a=find(HOME/"Saeit-staging"/"backups",RAW_ID,RAW_SIZE,RAW_MTIME)
    b=find(roots[0],SECOND_ID,SECOND_SIZE,SECOND_MTIME) if len(roots)==1 else None
    out.update(raw_identified=a is not None,second_identified=b is not None)
    if not a or not b: return out
    deadline=time.monotonic()+160
    with open_fixed(b) as f:
        head=f.read(4096); f.seek(0)
        out["second_gzip_magic"]=head.startswith(b"\x1f\x8b")
        out["second_plain_sql_marker"]=b"-- MySQL dump" in head or b"-- MariaDB dump" in head
        if not out["second_gzip_magic"]: return out
        try:
            with gzip.GzipFile(fileobj=f) as z:
                n,h=digest_stream(z,RAW_SIZE,deadline)
            out["decompressed_size"]=n
            if n!=RAW_SIZE:return out
            with open_fixed(a) as raw:
                m,g=digest_stream(raw,RAW_SIZE,deadline)
                unchanged=ident(os.fstat(raw.fileno()))==ident(a[1])==ident(a[0].lstat())
            unchanged=unchanged and ident(os.fstat(f.fileno()))==ident(b[1])==ident(b[0].lstat())
            out["unchanged"]=unchanged
            out["equivalent"]=unchanged and m==n and g==h
        except (OSError,EOFError,ValueError,TimeoutError) as e:
            out["error_type"]=type(e).__name__
    return out
if __name__=="__main__":
    try: print("MPW_BACKUP_EQUIVALENCE_READONLY="+json.dumps(audit(),sort_keys=True))
    except Exception as e: print("MPW_BACKUP_EQUIVALENCE_READONLY="+json.dumps({"read_only":True,"files_deleted":False,"raw_content_disclosed":False,"safe_to_delete":False,"equivalent":False,"error_type":type(e).__name__}))
