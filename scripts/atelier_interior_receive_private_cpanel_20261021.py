#!/usr/bin/env python3
"""Receive exact SHA-verified Atelier private ZIP on cPanel without site writes."""
import base64
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import pwd
import stat
import sys
import zipfile

FILE_HASHES={
 "index.html":"2950456f4ba3071d00b861767ceda50252aff9579252875addb0acd5969b9cd2",
 "styles.css":"bc8f9ab0be977088c92f1633ba970df33d4bb5933e7d076b27df34f122732f93",
 "app.js":"0045283de195bc3f5410fba58ec2e97de69a1c147d96b748bc3ff134559b4a58",
 "config.js":"577effc087437708550b585a77270b61ab1959c77a17f0858d85ca41b0853129",
 "README.md":"5c403edd6fd7a320cc66dc9c5bc7e6bde32872e707d2a02c248c376fcd746e88",
 "robots.txt":"16ceb5ee3e0dc13aa9adf31a3ebbe45a1d965b8c2b9f72eaf84e5911e140ed95",
 "assets/hero.jpg":"3360ede9e80d057131f8d9ddef260a5a4af8eecd3b0f28ee7d9ae2a1ed1cbdbc",
 "assets/tile-0.jpg":"91ec8bcdd2fd8e2b43cb55702fa3a38ef4b5ef85c31c2df08123cdc898f49c7b",
 "assets/tile-1.jpg":"6db5973a18c38b7c1726e9cf4093468b8ccfa8b317a780ab79089bc3505c62fb",
 "assets/tile-2.jpg":"8b6c33eb06026ddc83331b908c663d53ac34f27fee75edfdbd3ffa49f3c78506",
 "assets/tile-3.jpg":"e4917ecb05a728fd404ac498955d7044d3b0ad7302bfcbeac634e065b8060b90",
}
SHA="98bffad4ccf36f84c7924ca77e4a8b473b42f33a8fce4d85cefe2367afc097aa"
ROOT=Path("/home/zomorod2")
PRIVATE=ROOT/".private_mojplaywin_digital_products"
TARGET=PRIVATE/"atelier-interior-kit-v1-repacked.zip"
RECEIPT=PRIVATE/"atelier-interior-kit-v1-repacked.json"

def digest(data):
    return hashlib.sha256(data).hexdigest()

def verify(blob):
    if len(blob)<1_000 or len(blob)>15_000_000 or digest(blob)!=SHA:
        raise ValueError("ATELIER_CROSS_HOST_EXACT_SHA_MISMATCH")
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names=z.namelist()
        if len(names)!=len(FILE_HASHES) or set(names)!=set(FILE_HASHES) or z.testzip():
            raise ValueError("ATELIER_CROSS_HOST_ZIP_LAYOUT_INVALID")
        for item in z.infolist():
            if item.flag_bits&1 or item.is_dir() or item.file_size>12_000_000:
                raise ValueError("ATELIER_CROSS_HOST_ZIP_ENTRY_UNSAFE")
            if (item.external_attr>>16)&0o170000==stat.S_IFLNK:
                raise ValueError("ATELIER_CROSS_HOST_ZIP_SYMLINK")
        for name,wanted in FILE_HASHES.items():
            if digest(z.read(name))!=wanted:
                raise ValueError("ATELIER_CROSS_HOST_SOURCE_MEMBER_CHANGED")
    return True

def receive(blob):
    verify(blob)
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":
        raise PermissionError("WRONG_CPANEL_ACCOUNT")
    if ROOT.is_symlink() or PRIVATE.is_symlink():
        raise RuntimeError("PRIVATE_CATALOG_PATH_UNSAFE")
    PRIVATE.mkdir(mode=0o700,exist_ok=True)
    if stat.S_IMODE(PRIVATE.stat().st_mode)&0o077:
        raise PermissionError("PRIVATE_CATALOG_PERMISSIONS")
    lock=PRIVATE/".atelier-stock.lock"
    if lock.is_symlink():
        raise RuntimeError("PRIVATE_CATALOG_LOCK_SYMLINK")
    with lock.open("a+b") as held:
        os.fchmod(held.fileno(),0o600)
        fcntl.flock(held.fileno(),fcntl.LOCK_EX)
        info={"schema":"saeit.atelier-cpanel-private-stock.v1",
              "sku":"atelier-interior-kit-v1",
              "sha256":SHA,"members":len(FILE_HASHES),
              "origin":"saeit_vps_exact_verified",
              "status":"private_qa_hold_payment_disabled"}
        if TARGET.exists() or RECEIPT.exists() or TARGET.is_symlink() or RECEIPT.is_symlink():
            if TARGET.is_symlink() or RECEIPT.is_symlink() or not TARGET.is_file() or not RECEIPT.is_file():
                raise RuntimeError("PRIVATE_CATALOG_STOCK_COLLISION")
            if digest(TARGET.read_bytes())!=SHA or json.loads(RECEIPT.read_text())!=info:
                raise RuntimeError("PRIVATE_CATALOG_EXISTING_DIFFERENT")
            print("ATELIER_PRIVATE_CPANEL_STOCK=already_matching")
        else:
            with TARGET.open("xb") as fh:
                os.fchmod(fh.fileno(),0o600)
                fh.write(blob);fh.flush();os.fsync(fh.fileno())
            with RECEIPT.open("x",encoding="utf8") as fh:
                os.fchmod(fh.fileno(),0o600)
                json.dump(info,fh,sort_keys=True)
                fh.flush();os.fsync(fh.fileno())
            print("ATELIER_PRIVATE_CPANEL_STOCK=created")
        print("ATELIER_PRIVATE_CPANEL_STOCK_SHA256="+SHA)
        print("ATELIER_PRIVATE_CPANEL_STOCK_MEMBERS="+str(len(FILE_HASHES)))
        print("ATELIER_PUBLIC_PAID_DOWNLOAD_ENABLED=false")

def relay_program():
    # Read only a bounded base64 encoding of the trusted VPS stock from SSH.
    b64=sys.stdin.buffer.read(20_000_001).strip()
    if len(b64)>20_000_000:
        raise ValueError("ATELIER_RELAY_SOURCE_OVERSIZE")
    blob=base64.b64decode(b64,validate=True)
    verify(blob)
    source=Path(__file__).read_text(encoding="utf8")
    marker='\nif __name__=="__main__":'
    if source.count(marker)!=1:
        raise ValueError("ATELIER_RELAY_SOURCE_DRIFT")
    sys.stdout.write(source.split(marker,1)[0])
    sys.stdout.write('\nif __name__=="__main__":\n    receive(base64.b64decode("'+base64.b64encode(blob).decode("ascii")+'"))\n')
    sys.stdout.flush()

if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1]=="selftest":
        try:
            verify(b"not a valid kit")
        except ValueError:
            pass
        else:
            raise AssertionError("Unverified stock accepted")
        print("ATELIER_PRIVATE_CPANEL_RECEIVER_SELFTEST=PASS")
    elif len(sys.argv)==2 and sys.argv[1]=="relay_program":
        relay_program()
    else:
        raise SystemExit("selftest|relay_program")
