#!/usr/bin/env python3
"""Read-only Nov5 A/B inventory: accept raw SQLite OR authenticated gzip copy.

Allows a safe transition from raw+gzip -> gzip-only per historical timestamp;
never claims a compressed file is a CURRENT production backup or newly-restored
SQLite. No writes, deletion, factory launch or MySQL connection.
"""
import hashlib,json,os,pathlib,pwd,sqlite3,stat,sys,time,urllib.parse,zlib

ROOT=pathlib.Path("/home/zomorod2/restore-staging/factory")
ITEMS=(
 ("nov5-a","master-before-20261105T154953Z.sqlite3",1408634880,
  "a9fd2175f9ace1a81d67cf7145e54b8621fd44cc06b0b2739bdc9345e21750e2",
  279659980,"591a0b10b2f782cb7cb8db3fa340f4b3827b8d1db2960ca89a507098ccc35c78"),
 ("nov5-b","master-before-20261105T210434Z.sqlite3",1408634880,
  "402c16b67d430132701435eb4b3f79de88cd5c2479bb07c741c6674708a931be",
  279659148,"4d416f38744023293864d051b511d2ce957004b5c91ebc9882722f5486e31811"))
def ident(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)

def check_path(p,expected_size,private):
    s=p.lstat()
    if (not stat.S_ISREG(s.st_mode) or s.st_uid!=os.geteuid()
        or s.st_nlink!=1 or s.st_size!=expected_size or
        (private and s.st_mode&0o077)):
        raise RuntimeError("SNAPSHOT_UNTRUSTED")
    return s

def check_raw(path,size,digest):
    s=check_path(path,size,False)
    for suff in ("-wal","-shm","-journal"):
        p=path.with_name(path.name+suff)
        if p.exists() or p.is_symlink():raise RuntimeError("SQLITE_SIDECAR")
    fd=os.open(path,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    try:
        if ident(os.fstat(fd))!=ident(s):raise RuntimeError("SNAPSHOT_CHANGED")
        if os.read(fd,16)!=b"SQLite format 3\x00":raise RuntimeError("NOT_SQLITE")
        os.lseek(fd,0,os.SEEK_SET)
        h=hashlib.sha256();n=0
        while True:
            b=os.read(fd,1048576)
            if not b:break
            n+=len(b)
            if n>size:raise RuntimeError("RAW_OVERSIZE")
            h.update(b)
        if n!=size or h.hexdigest()!=digest or ident(os.fstat(fd))!=ident(s):
            raise RuntimeError("RAW_SHA_OR_MUTATION")
    finally:os.close(fd)
    uri="file:"+urllib.parse.quote(str(path),safe="/")+"?mode=ro&immutable=1"
    c=sqlite3.connect(uri,uri=True,timeout=40)
    try:
        c.execute("PRAGMA query_only=ON")
        quick=c.execute("PRAGMA quick_check").fetchone()[0]
        full=c.execute("PRAGMA integrity_check").fetchone()[0]
    finally:c.close()
    if quick!="ok" or full!="ok" or ident(path.lstat())!=ident(s):
        raise RuntimeError("SQLITE_RAW_INTEGRITY")
    return {"full_raw_sha_verified":True,"quick_check":"ok","integrity_check":"ok","raw_original_unchanged":True}

def check_gzip(path,size,digest,orig_size,orig_sha):
    s=check_path(path,size,True)
    fd=os.open(path,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    try:
        if ident(os.fstat(fd))!=ident(s):raise RuntimeError("GZIP_CHANGED")
        gz_hash=hashlib.sha256();raw_hash=hashlib.sha256()
        dec=zlib.decompressobj(wbits=31)
        n_zip=n_raw=0
        while True:
            packet=os.read(fd,1048576)
            if not packet:break
            n_zip+=len(packet)
            if n_zip>size:raise RuntimeError("GZIP_OVERSIZE")
            gz_hash.update(packet)
            rem=packet
            while rem:
                plain=dec.decompress(rem,1048576)
                n_raw+=len(plain)
                if n_raw>orig_size:raise RuntimeError("GZIP_DECOMPRESS_BOUND")
                raw_hash.update(plain)
                rem=dec.unconsumed_tail
                if dec.eof and rem:raise RuntimeError("GZIP_TRAILING")
        extra=dec.flush()
        n_raw+=len(extra);raw_hash.update(extra)
        if (not dec.eof or dec.unused_data or n_zip!=size or n_raw!=orig_size
            or gz_hash.hexdigest()!=digest or raw_hash.hexdigest()!=orig_sha
            or ident(os.fstat(fd))!=ident(s)):
            raise RuntimeError("GZIP_OR_RESTORED_SHA_INVALID")
    finally:os.close(fd)
    if ident(path.lstat())!=ident(s):raise RuntimeError("GZIP_MUTATION")
    return {"gzip_sha256_verified":True,"gzip_crc_verified":True,
            "restored_source_sha256_verified":True,
            "gzip_bytes":size,"restored_bytes":orig_size}

def main():
    started=time.monotonic()
    if pwd.getpwuid(os.geteuid()).pw_name!="zomorod2":raise RuntimeError("UNTRUSTED_ACCOUNT")
    for p in (pathlib.Path("/home/zomorod2"),ROOT.parent,ROOT):
        s=p.lstat()
        if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.geteuid() or s.st_mode&0o022:
            raise RuntimeError("UNTRUSTED_PARENT")
    records=[]
    for key,name,rawsize,rawsha,zipsize,zipsha in ITEMS:
        raw=ROOT/name
        gz=ROOT/(name+".gz")
        has_raw=raw.exists() or raw.is_symlink()
        has_gzip=gz.exists() or gz.is_symlink()
        if not has_raw and not has_gzip:raise RuntimeError("SNAPSHOT_MISSING_"+key)
        record={"snapshot":key,"raw_present":has_raw,"gzip_present":has_gzip}
        if has_raw:record["raw_integrity"]=check_raw(raw,rawsize,rawsha)
        if has_gzip:record["gzip_integrity"]=check_gzip(gz,zipsize,zipsha,rawsize,rawsha)
        records.append(record)
    report={"schema":"factory.cpanel.nov5.hybrid-gzip-raw-inventory.v1",
            "snapshots":records,"historical_point_in_time_count":len(records),
            "factory_started":False,"source_files_deleted":0,"files_written":0,
            "production_mysql_accessed":False,"live_current_factory_backup_claimed":False,
            "elapsed_seconds":round(time.monotonic()-started,2)}
    print("FACTORY_CPANEL_NOV5_HYBRID_INTEGRITY="+json.dumps(report,sort_keys=True,separators=(",",":")),flush=True)

if __name__=="__main__":
    try:main()
    except BaseException as err:
        code=str(err) if type(err) is RuntimeError else type(err).__name__
        print("FACTORY_CPANEL_NOV5_HYBRID_HOLD="+code,flush=True,file=sys.stderr)
        sys.exit(2)
