#!/usr/bin/env python3
"""Guarded single-source cleanup: ONLY Nov5-A raw cPanel SQLite after valid .gz.

The owner delegated the scoped decision in the ongoing chat; GitHub execution
MUST still be separately gated on a fully successful owner-key / isolated
gzip restore receipt. Does not touch the Nov5-B source, VPS, SQL or factory.
"""
import argparse,hashlib,json,os,pathlib,pwd,sqlite3,stat,subprocess,sys,urllib.parse,zlib

ROOT=pathlib.Path("/home/zomorod2/restore-staging/factory")
RAW="master-before-20261105T154953Z.sqlite3"
RAW_SIZE=1408634880
RAW_SHA="a9fd2175f9ace1a81d67cf7145e54b8621fd44cc06b0b2739bdc9345e21750e2"
GZ_SIZE=279659980
GZ_SHA="591a0b10b2f782cb7cb8db3fa340f4b3827b8d1db2960ca89a507098ccc35c78"
APPROVAL="OWNER_DELEGATED_2026-11-18_EXACT_NOV5_A_AFTER_ISOLATED_RESTORE"


def id_of(st):
    return (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)


def secure(p,size,mode_private=False):
    s=p.lstat()
    if (not stat.S_ISREG(s.st_mode) or s.st_uid != os.geteuid()
        or s.st_nlink != 1 or s.st_size != size
        or (mode_private and s.st_mode & 0o077)):
        raise RuntimeError("UNTRUSTED_FIXED_FILE")
    return s


def hash_raw(path,baseline):
    fd=os.open(path,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    try:
        if id_of(os.fstat(fd))!=id_of(baseline):raise RuntimeError("RAW_RACE")
        hash_value=hashlib.sha256()
        n=0
        if os.read(fd,16)!=b"SQLite format 3\x00":raise RuntimeError("SQLITE_HEADER")
        os.lseek(fd,0,os.SEEK_SET)
        while True:
            block=os.read(fd,1024*1024)
            if not block:break
            n+=len(block)
            if n>RAW_SIZE:raise RuntimeError("RAW_TOO_BIG")
            hash_value.update(block)
        if (n!=RAW_SIZE or hash_value.hexdigest()!=RAW_SHA or
            id_of(os.fstat(fd))!=id_of(baseline)):raise RuntimeError("RAW_DIGEST_INVALID")
    finally:os.close(fd)
    if id_of(path.lstat())!=id_of(baseline):raise RuntimeError("RAW_CHANGED")
    uri="file:"+urllib.parse.quote(str(path),safe="/")+"?mode=ro&immutable=1"
    c=sqlite3.connect(uri,uri=True,timeout=90)
    try:
        c.execute("PRAGMA query_only=ON")
        if c.execute("PRAGMA quick_check").fetchone()[0]!="ok":raise RuntimeError("RAW_QUICK_CHECK")
        if c.execute("PRAGMA integrity_check").fetchone()[0]!="ok":raise RuntimeError("RAW_FULL_INTEGRITY")
    finally:c.close()
    if id_of(path.lstat())!=id_of(baseline):raise RuntimeError("RAW_CHANGED_DURING_PRAGMA")


def verify_gzip(path,baseline):
    fd=os.open(path,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    try:
        if id_of(os.fstat(fd))!=id_of(baseline):raise RuntimeError("GZIP_RACE")
        sha_gz=hashlib.sha256()
        sha_raw=hashlib.sha256()
        decoder=zlib.decompressobj(wbits=31)
        n_gz=n_raw=0
        while True:
            block=os.read(fd,1024*1024)
            if not block:break
            n_gz+=len(block)
            if n_gz>GZ_SIZE:raise RuntimeError("GZIP_TOO_BIG")
            sha_gz.update(block)
            rest=block
            while rest:
                unzipped=decoder.decompress(rest,1024*1024)
                n_raw+=len(unzipped)
                if n_raw>RAW_SIZE:raise RuntimeError("GZIP_EXPANDS_TOO_BIG")
                sha_raw.update(unzipped)
                rest=decoder.unconsumed_tail
                if decoder.eof and rest:raise RuntimeError("GZIP_TRAILING")
        trailing=decoder.flush()
        n_raw+=len(trailing);sha_raw.update(trailing)
        if (not decoder.eof or decoder.unused_data or n_gz!=GZ_SIZE or
            n_raw!=RAW_SIZE or sha_gz.hexdigest()!=GZ_SHA or
            sha_raw.hexdigest()!=RAW_SHA or id_of(os.fstat(fd))!=id_of(baseline)):
            raise RuntimeError("GZIP_RESTORE_INVALID")
    finally:os.close(fd)
    if id_of(path.lstat())!=id_of(baseline):raise RuntimeError("GZIP_CHANGED")
    return True


def quota():
    try:
        x=subprocess.run(["uapi","--output=json","Quota","get_quota_info"],
                         stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=45)
        if x.returncode or len(x.stdout)>32768:raise ValueError()
        res=json.loads(x.stdout).get("result",{})
        if res.get("status") not in (1,True):raise ValueError()
        free=res["data"]["megabytes_remain"]
        if type(free) not in (int,float) or free<0:raise ValueError()
        return round(float(free),2)
    except (OSError,ValueError,KeyError,TypeError,subprocess.TimeoutExpired):
        raise RuntimeError("LIVE_QUOTA_UNKNOWN") from None


def execute(approval):
    if approval!=APPROVAL:raise RuntimeError("EXACT_OWNER_DELEGATION_NOT_PRESENT")
    if pwd.getpwuid(os.geteuid()).pw_name!="zomorod2":raise RuntimeError("WRONG_ACCOUNT")
    for p in (pathlib.Path("/home/zomorod2"),ROOT.parent,ROOT):
        st=p.lstat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid!=os.geteuid() or st.st_mode&0o022:
            raise RuntimeError("UNTRUSTED_DIR")
    source=ROOT/RAW
    gzip_path=ROOT/(RAW+".gz")
    rawstat=secure(source,RAW_SIZE)
    gzstat=secure(gzip_path,GZ_SIZE,mode_private=True)
    for suffix in ("-wal","-shm","-journal"):
        aux=ROOT/(RAW+suffix)
        if aux.exists() or aux.is_symlink():raise RuntimeError("ACTIVE_SQLITE_SIDE_CAR")
    hash_raw(source,rawstat)
    verify_gzip(gzip_path,gzstat)
    before_quota=quota()
    if id_of(source.lstat())!=id_of(rawstat) or id_of(gzip_path.lstat())!=id_of(gzstat):
        raise RuntimeError("FILE_CHANGED_BEFORE_OWNER_APPROVED_UNLINK")
    # ONLY irreversible operation; no wildcard, recursive deletion, or second source.
    os.unlink(source)
    dfd=os.open(ROOT,os.O_RDONLY|getattr(os,"O_DIRECTORY",0))
    try:os.fsync(dfd)
    finally:os.close(dfd)
    if source.exists() or source.is_symlink():raise RuntimeError("RAW_PATH_REAPPEARED")
    verify_gzip(gzip_path,gzstat)
    try:
        after_quota=quota()
    except RuntimeError:
        # An account quota read can lag or fail after unlink; never erase
        # a valid successful destructive receipt merely because UAPI is stale.
        after_quota=None
    return {"schema":"factory.nov5-a.cpanel.raw-one-file-approved-cleanup.v1",
            "raw_snapshot":"nov5-a",
            "source_sha256":RAW_SHA,"source_original_bytes":RAW_SIZE,
            "source_file_unlinked":True,"source_file_allocated_bytes_before":rawstat.st_blocks*512,
            "valid_gzip_remaining":True,"gzip_bytes_remaining":GZ_SIZE,
            "gzip_original_sha256_restored_verified":True,
            "other_raw_snapshot_touched":False,
            "vps_originals_touched":False,"production_mysql_touched":False,
            "factory_started":False,"paid_service_created":False,
            "quota_mib_before":before_quota,"quota_mib_after":after_quota,
            "actual_account_quota_delta_mib":(round(after_quota-before_quota,2)
                                              if after_quota is not None else None),
            "quota_delta_may_be_cached":True}


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--approval",required=True)
    args=p.parse_args()
    try:
        print("FACTORY_CPANEL_NOV5_A_EXACT_CLEANUP="+json.dumps(execute(args.approval),sort_keys=True,separators=(",",":")),flush=True)
    except BaseException as e:
        code=str(e) if type(e) is RuntimeError else type(e).__name__
        print("FACTORY_CPANEL_NOV5_A_CLEANUP_HOLD="+code,flush=True,file=sys.stderr)
        sys.exit(2)
