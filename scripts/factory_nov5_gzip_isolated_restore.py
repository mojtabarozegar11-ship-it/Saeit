#!/usr/bin/env python3
"""Independent owner-machine restore of a downloaded F01V2 historical gzip.

Only local private ciphertext inputs and NEW isolated output files. No Drive
writes, live SQL, source deletion or service activation. An exact historical
catalog match and SQLite integrity check are required after F01V2 authentication.
"""
from __future__ import annotations
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import tempfile
import zlib

from scripts import factory_nov5_gzip_direct_dual_drive as direct
from scripts.factory_dual_stream_v2 import decrypt_to_isolated_file
from scripts.factory_rclone_dual_parts import MAX_CIPHER_PART_BYTES, MAX_MANIFEST_BYTES

OWNER_SPKI = "a7b3ef1995681d3963d56570ce68b2c4cf9785e99163f66795592cb907632d74"
RESERVE = 1024**3


def private_directory(path):
    path=Path(path)
    if not path.is_absolute() or path.resolve(strict=True)!=path:
        raise ValueError("PRIVATE_ABSOLUTE_DIRECTORY_REQUIRED")
    s=path.lstat()
    if not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.geteuid() or s.st_mode&0o077:
        raise ValueError("PRIVATE_OWNER_DIRECTORY_REQUIRED")
    return path


def read_exact_private(path,maximum):
    path=Path(path)
    if path.resolve(strict=True)!=path:
        raise ValueError("SYMLINK_INPUT_DENIED")
    st=path.lstat()
    if (not stat.S_ISREG(st.st_mode) or st.st_uid!=os.geteuid() or
        st.st_nlink!=1 or st.st_mode&0o077 or not 0<st.st_size<=maximum):
        raise ValueError("PRIVATE_INPUT_FILE_REQUIRED")
    ident=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    fd=os.open(path,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    with os.fdopen(fd,"rb") as f:
        if ident(os.fstat(f.fileno()))!=ident(st):
            raise ValueError("INPUT_CHANGED")
        data=f.read(maximum+1)
        if len(data)!=st.st_size or ident(os.fstat(f.fileno()))!=ident(st):
            raise ValueError("INPUT_CHANGED")
    return data


def verify_and_expand(gzip_path, raw_path, snapshot):
    gz_size,gz_sha=direct.SOURCES[snapshot]
    raw_size=direct.legacy.SOURCE_BYTES
    raw_sha=direct.legacy.SOURCES[snapshot][1]
    dec=zlib.decompressobj(31)
    gh=hashlib.sha256();rh=hashlib.sha256()
    gn=rn=0;header=b""
    fd=os.open(raw_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"wb") as out, gzip_path.open("rb") as source:
        while True:
            blob=source.read(1048576)
            if not blob:break
            gn+=len(blob);gh.update(blob)
            if gn>gz_size or dec.eof:
                raise ValueError("GZIP_SIZE_OR_TRAILING_DATA")
            more=blob
            while more:
                plain=dec.decompress(more,1048576)
                rn+=len(plain)
                if rn>raw_size or dec.unused_data:
                    raise ValueError("ORIGINAL_SIZE_OR_TRAILING_DATA")
                header=(header+plain[:16])[:16]
                rh.update(plain);out.write(plain)
                tail=dec.unconsumed_tail
                if (dec.eof and tail) or (tail==more and not plain):
                    raise ValueError("INVALID_GZIP_STREAM")
                more=tail
        if (not dec.eof or dec.unused_data or dec.unconsumed_tail or
            gn!=gz_size or gh.hexdigest()!=gz_sha or rn!=raw_size or
            rh.hexdigest()!=raw_sha or header!=b"SQLite format 3\x00"):
            raise ValueError("HISTORICAL_CATALOG_MISMATCH")
        out.flush();os.fsync(out.fileno())
    uri=raw_path.as_uri()+"?mode=ro&immutable=1"
    with sqlite3.connect(uri,uri=True) as conn:
        conn.execute("PRAGMA query_only=ON")
        if conn.execute("PRAGMA quick_check").fetchall()!=[("ok",)]:
            raise ValueError("SQLITE_QUICK_CHECK_FAILED")
        if conn.execute("PRAGMA integrity_check").fetchall()!=[("ok",)]:
            raise ValueError("SQLITE_INTEGRITY_CHECK_FAILED")
    # Verify the final on-disk output, not only the decompressor's memory.
    digest=hashlib.sha256()
    with raw_path.open("rb") as f:
        for block in iter(lambda:f.read(1048576),b""):
            digest.update(block)
    if raw_path.stat().st_size!=raw_size or digest.hexdigest()!=raw_sha:
        raise ValueError("FINAL_OUTPUT_READBACK_MISMATCH")
    return raw_size,raw_sha


def restore(snapshot, manifest_path, manifest_sha, input_dir, output_parent,
            pem, password, *, expected_spki=OWNER_SPKI):
    """Create a fresh isolated output; preserve all existing files on failure."""
    if snapshot not in direct.SOURCES or not re.fullmatch(r"[0-9a-f]{64}",manifest_sha):
        raise ValueError("EXACT_SNAPSHOT_AND_MANIFEST_PIN_REQUIRED")
    input_dir=private_directory(input_dir)
    output_parent=private_directory(output_parent)
    if (input_dir==output_parent or input_dir in output_parent.parents
            or output_parent in input_dir.parents):
        raise ValueError("SEPARATE_INPUT_AND_OUTPUT_DIRECTORIES_REQUIRED")
    path=Path(manifest_path)
    if path.parent!=input_dir or not re.fullmatch(r"f01v2-[0-9a-f]{32}-manifest\.json",path.name):
        raise ValueError("EXACT_LOCAL_MANIFEST_REQUIRED")
    data=read_exact_private(path,MAX_MANIFEST_BYTES)
    if hashlib.sha256(data).hexdigest()!=manifest_sha:
        raise ValueError("MANIFEST_PIN_MISMATCH")
    document=json.loads(data)
    gz_size=direct.SOURCES[snapshot][0]
    if (type(document) is not dict or document.get("plain_total")!=gz_size or
        path.name!="f01v2-"+str(document.get("run_id"))+"-manifest.json"):
        raise ValueError("COMPRESSED_DECLARED_SIZE_OR_RUN_MISMATCH")
    fs=os.statvfs(output_parent)
    if fs.f_bavail*fs.f_frsize<gz_size+direct.legacy.SOURCE_BYTES+RESERVE:
        raise ValueError("INSUFFICIENT_ISOLATED_RESTORE_CAPACITY")
    def part(name):
        if not re.fullmatch(r"f01v2-[0-9a-f]{32}-[0-9]{6}\.enc",name):
            raise ValueError("UNSAFE_PART_NAME")
        return read_exact_private(input_dir/name,MAX_CIPHER_PART_BYTES)
    # TemporaryDirectory removes only files created within this new recovery
    # workspace. Successful raw recovery is published by exclusive hard link.
    with tempfile.TemporaryDirectory(prefix=".nov5-restore-",dir=output_parent) as tmp:
        work=Path(tmp)
        compressed=work/"snapshot.sqlite3.gz"
        raw=work/"restored.sqlite3"
        recovered=decrypt_to_isolated_file(data,read_chunk=part,private_pem=pem,
            private_password=password,expected_public_spki_sha256=expected_spki,
            output_path=compressed,minimum_free_reserve_bytes=direct.legacy.SOURCE_BYTES+RESERVE)
        if recovered!=gz_size:
            raise ValueError("COMPRESSED_RECOVERY_LENGTH_MISMATCH")
        n,digest=verify_and_expand(compressed,raw,snapshot)
        # Unique deterministic final basename prevents overwriting any prior output.
        final=output_parent/(snapshot+"-"+manifest_sha[:16]+".sqlite3")
        os.link(raw,final,follow_symlinks=False)
    return {"schema":"factory.nov5.gzip.isolated.recovery.v1",
        "snapshot_id":snapshot,"manifest_sha256":manifest_sha,
        "gzip_sha256_verified":True,"restored_bytes":n,"restored_sha256":digest,
        "rsa_aes_manifest_and_parts_authenticated":True,"sqlite_quick_check":"ok",
        "sqlite_integrity_check":"ok","isolated_output":final.name,
        "current_mariadb_restore":False,"source_deleted":False,"factory_started":False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot",choices=tuple(direct.SOURCES),required=True)
    for name in ("manifest","manifest-sha256","input-dir","output-parent","private-pem"):
        p.add_argument("--"+name,required=True)
    p.add_argument("--encrypted-key",action="store_true")
    args=p.parse_args()
    if os.geteuid()==0 or os.environ.get("GITHUB_ACTIONS") or not sys.stdin.isatty():
        raise ValueError("TRUSTED_NONROOT_OWNER_INTERACTIVE_RESTORE_REQUIRED")
    if any(Path(v).resolve().is_relative_to(Path("/home/zomorod2")) for v in
           (args.input_dir,args.output_parent,args.private_pem)):
        raise ValueError("PRODUCTION_HOST_PATH_DENIED")
    pem=read_exact_private(Path(args.private_pem),16384)
    password=getpass.getpass("Private recovery key passphrase: ").encode() if args.encrypted_key else None
    print(json.dumps(restore(args.snapshot,Path(args.manifest),args.manifest_sha256,
        Path(args.input_dir),Path(args.output_parent),pem,password),sort_keys=True),flush=True)


if __name__=="__main__":
    try:main()
    except Exception:raise SystemExit("HOLD: INDEPENDENT_RECOVERY_NOT_COMPLETED")
