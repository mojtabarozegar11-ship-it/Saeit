#!/usr/bin/env python3
"""Build exact-member Atelier source ZIP privately on the VPS factory only.

All 11 file bodies must equal the previously verified owner's original ZIP members.
Ten bodies are downloaded from the existing public demo. The exact homepage is
recovered from the original owner's ZIP into a compressed literal, because Sites
rewrites the public index response. No paid ZIP is checked into GitHub.
No cPanel site, payment, Product, or order is changed here.
"""
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
import urllib.request
import zipfile
import zlib

ORIGIN="https://atelier-interior-kit-demo.mojtaba-rozegar11.chatgpt.site/"
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
INDEX_ZLIB_B64="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"
DEST_DIR=Path("/home/githubops/.private-factory-products")
ARCHIVE=DEST_DIR/"atelier-interior-kit-v1-repacked.zip"
RECEIPT=DEST_DIR/"atelier-interior-kit-v1-repacked.json"

def digest(blob):
    return hashlib.sha256(blob).hexdigest()

def source_bytes(fetch=True):
    objects={}
    raw=zlib.decompress(base64.b64decode(INDEX_ZLIB_B64))
    if digest(raw)!=FILE_HASHES["index.html"]:
        raise ValueError("HOMEPAGE_INTEGRITY_MISMATCH")
    objects["index.html"]=raw
    if not fetch:
        return objects
    for filename, expected in FILE_HASHES.items():
        if filename=="index.html":
            continue
        req=urllib.request.Request(ORIGIN+filename,headers={"User-Agent":"AtelierOwnerPrivateStock/1.0"})
        with urllib.request.urlopen(req,timeout=20) as res:
            if res.status!=200 or not res.geturl().startswith(ORIGIN):
                raise ValueError("SOURCE_RESPONSE_NOT_PINNED")
            raw=res.read(12_000_001)
        if len(raw)>12_000_000 or digest(raw)!=expected:
            raise ValueError("DEMO_MEMBER_SHA_MISMATCH:"+filename)
        objects[filename]=raw
    if set(objects)!=set(FILE_HASHES):
        raise ValueError("INCOMPLETE_PRODUCT_SOURCE")
    return objects

def build(objects):
    output=io.BytesIO()
    with zipfile.ZipFile(output,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as pack:
        for filename in FILE_HASHES:
            raw=objects[filename]
            if digest(raw)!=FILE_HASHES[filename]:
                raise ValueError("WRONG_PRODUCT_MEMBER:"+filename)
            member=zipfile.ZipInfo(filename,date_time=(2026,10,21,9,42,0))
            member.compress_type=zipfile.ZIP_DEFLATED
            member.external_attr=(0o100644 <<16)
            pack.writestr(member,raw,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    blob=output.getvalue()
    with zipfile.ZipFile(io.BytesIO(blob)) as pack:
        if pack.testzip() or set(pack.namelist())!=set(FILE_HASHES):
            raise ValueError("REBUILT_ARCHIVE_UNSAFE")
        for name,expected in FILE_HASHES.items():
            if digest(pack.read(name))!=expected:
                raise ValueError("REBUILT_ARCHIVE_MEMBER_CHANGED")
    return blob

def verify_streamed_archive(blob):
    if not 1_000 <= len(blob) <= 15_000_000:
        raise ValueError("RELAY_PACKAGE_SIZE_INVALID")
    with zipfile.ZipFile(io.BytesIO(blob)) as pack:
        if set(pack.namelist())!=set(FILE_HASHES) or pack.testzip():
            raise ValueError("RELAY_PACKAGE_STRUCTURE_INVALID")
        objects={name:pack.read(name) for name in FILE_HASHES}
    # Canonical replay proves no member substitution, no ZIP tricks.
    if build(objects)!=blob:
        raise ValueError("RELAY_PACKAGE_HASH_OR_ZIP_MISMATCH")
    return blob


def relay_program():
    """Runner uses its HTTPS connectivity; VPS revalidates and privately stocks."""
    payload=base64.b64encode(build(source_bytes(fetch=True))).decode("ascii")
    original=Path(__file__).read_text(encoding="utf8")
    marker='\nif __name__=="__main__":'
    if original.count(marker)!=1:
        raise RuntimeError("RELAY_PROGRAM_SOURCE_INVALID")
    sys.stdout.write(original.split(marker,1)[0])
    sys.stdout.write('\nif __name__=="__main__":\n    stage(base64.b64decode("'+payload+'"))\n')
    sys.stdout.flush()


def stage(input_zip=None):
    if pwd.getpwuid(os.getuid()).pw_name!="githubops":
        raise PermissionError("WRONG_PRIVATE_VPS_ACCOUNT")
    if DEST_DIR.is_symlink() or DEST_DIR.parent.is_symlink():
        raise RuntimeError("PRIVATE_STOCK_DIRECTORY_SYMLINK")
    DEST_DIR.mkdir(mode=0o700,exist_ok=True)
    if stat.S_IMODE(DEST_DIR.stat().st_mode)&0o077:
        raise PermissionError("PRIVATE_STOCK_PERMISSIONS")
    lock=DEST_DIR/".atelier-interior.lock"
    if lock.is_symlink():
        raise RuntimeError("PRIVATE_STOCK_LOCK_SYMLINK")
    with lock.open("a+b") as handle:
        os.fchmod(handle.fileno(),0o600)
        fcntl.flock(handle.fileno(),fcntl.LOCK_EX)
        blob=build(source_bytes(fetch=True)) if input_zip is None else verify_streamed_archive(input_zip)
        checksum=digest(blob)
        info={"schema":"saeit.atelier-private-stock.v1","sku":"atelier-interior-kit-v1",
              "sha256":checksum,"size":len(blob),"member_hashes":FILE_HASHES,
              "source_archive_sha256":"f17eb13a5e546c5ca9974885b30b6d8b5bc44ecf5474edf75b544f8f7d254d3d",
              "status":"private_qa_hold_no_paid_release"}
        if ARCHIVE.exists() or RECEIPT.exists() or ARCHIVE.is_symlink() or RECEIPT.is_symlink():
            if ARCHIVE.is_symlink() or RECEIPT.is_symlink() or not ARCHIVE.is_file() or not RECEIPT.is_file():
                raise RuntimeError("STOCK_COLLISION")
            if digest(ARCHIVE.read_bytes())!=checksum or json.loads(RECEIPT.read_text())!=info:
                raise RuntimeError("EXISTING_STOCK_DIFFERENT_STOP")
            print("ATELIER_PRIVATE_VPS_STOCK=already_matching")
        else:
            with ARCHIVE.open("xb") as fh:
                os.fchmod(fh.fileno(),0o600)
                fh.write(blob);fh.flush();os.fsync(fh.fileno())
            with RECEIPT.open("x",encoding="utf8") as fh:
                os.fchmod(fh.fileno(),0o600)
                json.dump(info,fh,sort_keys=True)
                fh.flush();os.fsync(fh.fileno())
            print("ATELIER_PRIVATE_VPS_STOCK=created")
        print("ATELIER_PRIVATE_STOCK_SHA256="+checksum)
        print("ATELIER_PRIVATE_STOCK_MEMBERS="+str(len(FILE_HASHES)))
        print("ATELIER_CUSTOMER_CHECKOUT_ENABLED=false")

if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1]=="selftest":
        objects={name:b"selftest" for name in FILE_HASHES}
        objects["index.html"]=source_bytes(fetch=False)["index.html"]
        assert digest(objects["index.html"])==FILE_HASHES["index.html"]
        try:
            build(objects)
        except ValueError:
            pass
        else:
            raise AssertionError("wrong members not blocked")
        print("ATELIER_PRIVATE_VPS_BUILDER_SELFTEST=PASS")
    elif len(sys.argv)==2 and sys.argv[1]=="stage":
        stage()
    elif len(sys.argv)==2 and sys.argv[1]=="relay_program":
        relay_program()
    else:
        raise SystemExit("selftest|stage|relay_program")
