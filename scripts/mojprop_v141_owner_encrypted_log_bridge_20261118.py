#!/usr/bin/env python3
"""One-time ENCRYPTED-ONLY transport of initial zero-customer merchant SQLite.

Only RSA3072 + AES256GCM ciphertext (15.5KB) may enter public GitHub Actions
logs. The public log is an untrusted TRANSFER CHANNEL, not a permanent backup.
Never use for current customer/payment data. No keys, raw SQL, directory
names, or credentials are printed. Never delete source or change services.
"""
from __future__ import annotations
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import zipfile

ROOT = Path.home() / ".mojprop-rsa3072-offhost-backups"
ARCHIVE_NAME = "mojprop-first-empty-merchant-OWNER-RSA3072-AES256GCM.zip"
EXACT_SHA256 = "e7b5f860c7cfbe221928d5c8b863fb905119339deb819ffba90cfb8b49f69e2f"
EXACT_BYTES = 15545
SOURCE_BYTES = 446464
SOURCE_SHA256 = "c10113de0442f170121f36a37192a2337e47fff1d3b6636681d2246e73685f82"
RECIPIENT = "a7b3ef1995681d3963d56570ce68b2c4cf9785e99163f66795592cb907632d74"
SCHEMA = "mojprop.v141.initial-zero-customer.owner-rsa3072-aes256gcm.v1"

def hold(name: str) -> None:
    print("MOJPROP_BRIDGE_HOLD="+name, flush=True)
    raise SystemExit(2)

def secured_dir(p:Path)->None:
    st=p.lstat()
    if (not stat.S_ISDIR(st.st_mode) or st.st_uid!=os.geteuid()
            or st.st_mode & 0o077 or p.is_symlink()):
        hold("UNTRUSTED_PRIVATE_FOLDER")

def main() -> None:
    if os.geteuid() == 0:
        hold("NONROOT_REQUIRED")
    secured_dir(ROOT)
    verified=[]
    for p in ROOT.iterdir():
        if not p.name.startswith("initial-") or p.is_symlink() or not p.is_dir():
            continue
        secured_dir(p)
        f=p/ARCHIVE_NAME
        if not f.exists() or f.is_symlink():
            continue
        st=f.lstat()
        if (not stat.S_ISREG(st.st_mode) or st.st_uid!=os.geteuid()
                or st.st_nlink!=1 or st.st_mode & 0o077
                or st.st_size!=EXACT_BYTES):
            continue
        with f.open("rb") as zf:
            raw=zf.read(EXACT_BYTES+1)
        if len(raw)==EXACT_BYTES and hashlib.sha256(raw).hexdigest()==EXACT_SHA256:
            verified.append(raw)
    if len(verified)!=1:
        hold("EXPECTED_EXACTLY_ONE_PINNED_ARCHIVE")
    raw=verified[0]
    with zipfile.ZipFile(io.BytesIO(raw),"r") as archive:
        if sorted(archive.namelist())!=["encrypted-snapshot.bin","manifest.json"]:
            hold("UNKNOWN_ARCHIVE_MEMBERS")
        for info in archive.infolist():
            if info.compress_type!=zipfile.ZIP_STORED or info.file_size>65536:
                hold("UNEXPECTED_ARCHIVE_COMPRESSION")
        manifest=json.loads(archive.read("manifest.json"))
        cipher=archive.read("encrypted-snapshot.bin")
    if (type(manifest)!=dict or manifest.get("schema")!=SCHEMA
            or manifest.get("recipient_spki_sha256")!=RECIPIENT
            or manifest.get("source_sha256")!=SOURCE_SHA256
            or manifest.get("source_bytes")!=SOURCE_BYTES
            or manifest.get("scope")!="isolated_initial_zero_customer_only_not_current_mariadb"
            or manifest.get("cloud_dual_mirror_proven") is not False
            or len(cipher)!=manifest.get("cipher_bytes")
            or hashlib.sha256(cipher).hexdigest()!=manifest.get("cipher_sha256")):
        hold("CIPHER_MANIFEST_VALIDATION_FAILED")
    if manifest.get("source")!="owner-cpanel-immutable-initial-private-zero-customer-sqlite":
        hold("SOURCE_SCOPE_NOT_PERMITTED")
    data=base64.b64encode(raw).decode("ascii")
    # 7K character chunks, well below log line limits.
    chunks=[data[i:i+7000] for i in range(0,len(data),7000)]
    if len(chunks)!=3 or len(data)!=20728:
        hold("BASE64_SIZE_MISMATCH")
    print("MOJPROP_ZERO_CUSTOMER_RSA_BRIDGE_META="+json.dumps({
        "ciphertext_only":True,"source_is_initial_zero_customer":True,
        "full_current_mariadb":False,"private_key_exported":False,
        "archive_sha256":EXACT_SHA256,"archive_bytes":len(raw),
        "base64_chars":len(data),"parts":len(chunks),
        "public_actions_log_transport":True,
        "google_drive_uploaded":False,
        "factory_started":False,"source_deleted":False,
        "new_artifact_storage_created":False,
    },sort_keys=True),flush=True)
    for i,part in enumerate(chunks,1):
        print(f"MOJPROP_ZERO_CUSTOMER_RSA_BRIDGE_PART_{i}_OF_{len(chunks)}={part}",flush=True)
    print("MOJPROP_ZERO_CUSTOMER_RSA_BRIDGE_END="+EXACT_SHA256,flush=True)

if __name__=="__main__":
    try:
        main()
    except (OSError,ValueError,KeyError,zipfile.BadZipFile,TypeError):
        hold("NON_SECRET_VALIDATION_FAILURE")
