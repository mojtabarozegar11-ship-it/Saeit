#!/usr/bin/env python3
"""Recover byte-exact AES256GCM/RSA3072 encrypted ZIP from owner Google Doc text.

The Google Doc stores ONLY an already encrypted, initial ZERO-CUSTOMER backup
as Base64; never contains plain SQLite or owner private key. Export the owner's
Google Doc as plain text, then use this script with --input and --output.
Refuses existing output, symlinks, malformed Base64 and wrong hashes.
No network, no application migration, no live restore, no SQL key access.
"""
from __future__ import annotations
import argparse
import base64
import binascii
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import zipfile

BEGIN="MOJPROP_ZERO_CUSTOMER_BASE64_BEGIN"
END="MOJPROP_ZERO_CUSTOMER_BASE64_END"
EXPECTED_SHA="e7b5f860c7cfbe221928d5c8b863fb905119339deb819ffba90cfb8b49f69e2f"
EXPECTED_LENGTH=15545
EXPECTED_SCHEMA="mojprop.v141.initial-zero-customer.owner-rsa3072-aes256gcm.v1"
OWNER_KEY_FINGERPRINT="a7b3ef1995681d3963d56570ce68b2c4cf9785e99163f66795592cb907632d74"

def _read_private_file(p:Path,maxsize:int)->bytes:
    if not p.is_absolute():
        raise ValueError("ABSOLUTE_PATH_REQUIRED")
    st=p.lstat()
    if (not stat.S_ISREG(st.st_mode) or st.st_nlink!=1
            or st.st_uid!=os.geteuid() or st.st_mode&0o077 or st.st_size>maxsize):
        raise ValueError("PRIVATE_REGULAR_INPUT_REQUIRED")
    fd=os.open(p,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    try:
        current=os.fstat(fd)
        if (current.st_ino,current.st_size)!=(st.st_ino,st.st_size):
            raise ValueError("SOURCE_CHANGED")
        raw=os.read(fd,maxsize+1)
        if len(raw)!=st.st_size:
            raise ValueError("SOURCE_SIZE_CHANGED")
        return raw
    finally:
        os.close(fd)

def recover(text_bytes:bytes)->bytes:
    text=text_bytes.decode("utf8-sig")
    if text.count(BEGIN)!=1 or text.count(END)!=1:
        raise ValueError("BACKUP_MARKERS_NOT_UNIQUE")
    chunk=text.split(BEGIN,1)[1].split(END,1)[0]
    data=re.sub(r"\s+","",chunk)
    if len(data)!=20728 or not re.fullmatch(r"[A-Za-z0-9+/]+={1,2}",data):
        raise ValueError("INVALID_ENCRYPTED_ARCHIVE_BASE64")
    try:
        blob=base64.b64decode(data,validate=True)
    except binascii.Error:
        raise ValueError("BASE64_DECODE_FAILED") from None
    if len(blob)!=EXPECTED_LENGTH or hashlib.sha256(blob).hexdigest()!=EXPECTED_SHA:
        raise ValueError("ENCRYPTED_ARCHIVE_BYTES_NOT_AUTHENTIC")
    with zipfile.ZipFile(io.BytesIO(blob),"r") as z:
        if sorted(z.namelist())!=["encrypted-snapshot.bin","manifest.json"]:
            raise ValueError("UNEXPECTED_ENCRYPTED_ARCHIVE_MEMBERS")
        for item in z.infolist():
            if item.compress_type!=zipfile.ZIP_STORED or item.file_size>65536:
                raise ValueError("ZIP_MEMBER_UNSAFE")
        manifest=json.loads(z.read("manifest.json"))
        cipher=z.read("encrypted-snapshot.bin")
    if (manifest.get("schema")!=EXPECTED_SCHEMA
            or manifest.get("recipient_spki_sha256")!=OWNER_KEY_FINGERPRINT
            or manifest.get("scope")!="isolated_initial_zero_customer_only_not_current_mariadb"
            or manifest.get("source_bytes")!=446464
            or manifest.get("source_sha256")!="c10113de0442f170121f36a37192a2337e47fff1d3b6636681d2246e73685f82"
            or hashlib.sha256(cipher).hexdigest()!=manifest.get("cipher_sha256")):
        raise ValueError("OWNER_RECOVERY_MANIFEST_INVALID")
    return blob

def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--input",type=Path,required=True,help="owner-private exported Google Doc TXT")
    ap.add_argument("--output",type=Path,required=True,help="NEW output encrypted ZIP, private folder")
    args=ap.parse_args()
    if os.geteuid()==0:
        raise ValueError("OWNER_NONROOT_ONLY")
    raw=_read_private_file(args.input,65536)
    blob=recover(raw)
    dest=args.output
    if not dest.is_absolute() or dest.exists() or dest.is_symlink() or not dest.parent.is_dir():
        raise ValueError("NEW_PRIVATE_ABSOLUTE_OUTPUT_REQUIRED")
    st=dest.parent.lstat()
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid!=os.geteuid()
            or st.st_mode&0o077 or dest.parent.is_symlink()):
        raise ValueError("PRIVATE_OUTPUT_DIRECTORY_REQUIRED")
    fd=os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,"O_NOFOLLOW",0),0o600)
    with os.fdopen(fd,"wb") as o:
        o.write(blob)
        o.flush()
        os.fsync(o.fileno())
    print("MOJPROP_DRIVE_TEXT_ENCRYPTED_ZIP_RECOVERED="+json.dumps({
        "encrypted_archive_bytes":len(blob),"sha256":EXPECTED_SHA,
        "private_output_only":True,"current_mariadb_restored":False,
        "sqlite_decrypted":False,"factory_started":False,
        "production_modified":False},sort_keys=True))

if __name__=="__main__":
    try:
        main()
    except (OSError,ValueError,zipfile.BadZipFile,UnicodeDecodeError,TypeError):
        print("MOJPROP_DRIVE_TEXT_ENCRYPTED_ZIP_RECOVERY_HOLD=INVALID_OR_UNTRUSTED_INPUT")
        sys.exit(2)
