#!/usr/bin/env python3
"""Manual owner-local disaster recovery for an encrypted first empty merchant ledger.

Private key and passphrase must stay on an owner-controlled, isolated machine.
Default verifies decrypted bytes and SQLite without restoring any output.
--restore-file ONLY writes a new, private non-production file; never overwrites.
NO network, no shell tools, no migrations, no live server interaction.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import zlib
import zipfile

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from scripts.mojprop_v141_first_empty_owner_rsa_offhost_20261118 import (
    SCHEMA, LIMIT, EXPECTED_RECIPIENT_SHA, _canonical, _isolate_verify, _sha,
)

def _safe_regular(path: Path, cap: int) -> bytes:
    if not path.is_absolute():
        raise ValueError("MUST_USE_ABSOLUTE_OWNER_PRIVATE_PATH")
    st=path.lstat()
    if (not stat.S_ISREG(st.st_mode) or st.st_uid!=os.geteuid()
            or st.st_nlink!=1 or st.st_mode & 0o077
            or not 0<st.st_size<=cap):
        raise ValueError("UNTRUSTED_RECOVERY_INPUT")
    fd=os.open(path,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0))
    try:
        now=os.fstat(fd)
        if now.st_ino!=st.st_ino or now.st_size!=st.st_size:
            raise ValueError("RECOVERY_INPUT_RACE")
        raw=os.read(fd,cap+1)
        if len(raw)!=st.st_size:
            raise ValueError("RECOVERY_INPUT_SIZE_CHANGED")
        return raw
    finally:
        os.close(fd)

def verify(package: Path, key_path: Path, password_path: Path | None) -> tuple[bytes,dict]:
    from io import BytesIO
    outer=_safe_regular(package,LIMIT+1024*1024)
    with zipfile.ZipFile(BytesIO(outer),"r") as z:
        if sorted(z.namelist())!=["encrypted-snapshot.bin","manifest.json"]:
            raise ValueError("UNEXPECTED_BACKUP_MEMBERS")
        for item in z.infolist():
            if item.compress_type != zipfile.ZIP_STORED or item.file_size > LIMIT + 16384:
                raise ValueError("UNSUPPORTED_OR_EXPANDING_PACKAGE")
        mraw=z.read("manifest.json")
        if len(mraw)>16384:
            raise ValueError("OVERSIZED_MANIFEST")
        doc=json.loads(mraw)
        if _canonical(doc)!=mraw:
            raise ValueError("NONCANONICAL_MANIFEST")
        cipher=z.read("encrypted-snapshot.bin")
    if not isinstance(doc,dict) or doc.get("schema")!=SCHEMA:
        raise ValueError("WRONG_BACKUP_SCHEMA")
    if doc.get("recipient_spki_sha256")!=EXPECTED_RECIPIENT_SHA:
        raise ValueError("WRONG_OWNER_RECIPIENT")
    if doc.get("scope")!="isolated_initial_zero_customer_only_not_current_mariadb":
        raise ValueError("UNAPPROVED_BACKUP_SCOPE")
    if type(doc.get("source_bytes")) is not int or not 1<=doc["source_bytes"]<=LIMIT:
        raise ValueError("INVALID_DECLARED_SOURCE_SIZE")
    if type(doc.get("cipher_bytes")) is not int or len(cipher)!=doc["cipher_bytes"] or _sha(cipher)!=doc.get("cipher_sha256"):
        raise ValueError("CIPHERTEXT_INTEGRITY_FAILURE")
    pwd=None
    if password_path is not None:
        pwd=_safe_regular(password_path,4096).rstrip(b"\r\n")
        if not pwd:
            raise ValueError("EMPTY_KEY_PASSPHRASE")
    pem=_safe_regular(key_path,16384)
    key=serialization.load_pem_private_key(pem,password=pwd,backend=default_backend())
    if not isinstance(key,rsa.RSAPrivateKey) or key.key_size!=3072:
        raise ValueError("WRONG_RECOVERY_KEY_TYPE")
    der=key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
    if not hmac.compare_digest(_sha(der),EXPECTED_RECIPIENT_SHA):
        raise ValueError("WRONG_RECOVERY_PRIVATE_KEY")
    def d64(name: str, limit:int) -> bytes:
        value=doc.get(name)
        if type(value) is not str or len(value)>limit:
            raise ValueError("BAD_ENCRYPTION_ENCODING")
        return base64.b64decode(value,validate=True)
    wrapped=d64("wrapped_session_key_rsa_oaep_sha256_b64",8192)
    nonce=d64("aes256gcm_nonce_b64",64)
    aad=d64("aes256gcm_aad_b64",1024)
    expected_aad=_canonical({"schema":SCHEMA,"source_sha256":doc["source_sha256"],"source_bytes":doc["source_bytes"]})
    if len(nonce)!=12 or not hmac.compare_digest(aad,expected_aad):
        raise ValueError("NONCE_OR_AAD_TAMPER")
    secret=key.decrypt(wrapped,padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),algorithm=hashes.SHA256(),label=None))
    if len(secret)!=32:
        raise ValueError("BAD_WRAPPED_AES_KEY")
    compressed=AESGCM(secret).decrypt(nonce,cipher,aad)
    if type(doc.get("compressed_bytes")) is not int or len(compressed)!=doc["compressed_bytes"]:
        raise ValueError("COMPRESSED_SIZE_MISMATCH")
    dec=zlib.decompressobj()
    plain=dec.decompress(compressed,LIMIT+1)
    if len(plain)>LIMIT or dec.unconsumed_tail:
        raise ValueError("COMPRESSED_PAYLOAD_EXCEEDS_BOUNDED_OUTPUT")
    plain+=dec.flush()
    if len(plain)>LIMIT:
        raise ValueError("DECOMPRESSION_EXCEEDS_LIMIT")
    if len(plain)!=doc["source_bytes"] or _sha(plain)!=doc["source_sha256"] or not dec.eof or dec.unused_data or dec.unconsumed_tail:
        raise ValueError("PLAINTEXT_RECOVERY_MISMATCH")
    _isolate_verify(plain)
    return plain,doc

def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--package",type=Path,required=True)
    ap.add_argument("--private-key",type=Path,required=True)
    ap.add_argument("--password-file",type=Path)
    ap.add_argument("--restore-file",type=Path,help="Requires existing owner-private destination directory and new file")
    args=ap.parse_args()
    if os.geteuid()==0:
        raise ValueError("OWNER_NONROOT_ONLY")
    plain,doc=verify(args.package,args.private_key,args.password_file)
    restored=False
    if args.restore_file is not None:
        dest=args.restore_file
        if not dest.is_absolute() or dest.exists() or dest.is_symlink():
            raise ValueError("INVALID_OR_EXISTING_RESTORE_DESTINATION")
        parent=dest.parent
        s=parent.lstat()
        if (not stat.S_ISDIR(s.st_mode) or s.st_uid!=os.geteuid()
                or s.st_mode & 0o077 or parent.is_symlink()):
            raise ValueError("RESTORE_PARENT_MUST_BE_OWNER_PRIVATE")
        if any(x in str(dest).lower() for x in ("/public_html/", "/mojplaywin.com/", "/production/")):
            raise ValueError("LIVE_APPLICATION_RESTORE_FORBIDDEN")
        fd=os.open(dest,os.O_CREAT|os.O_EXCL|os.O_WRONLY|getattr(os,"O_NOFOLLOW",0),0o600)
        with os.fdopen(fd,"wb") as f:
            f.write(plain)
            f.flush()
            os.fsync(f.fileno())
        restored=True
    print("MOJPROP_OWNER_ISOLATED_PRIVATE_KEY_RECOVERY="+json.dumps({
        "schema":"mojprop.v141.owner-rsa3072-recovery-receipt.v1",
        "verified":True,"sqlite_integrity":True,"paid_tables_empty":True,
        "source_bytes":len(plain),"source_sha256":doc["source_sha256"],
        "private_owner_restore_file_written":restored,
        "production_deployed":False,"customer_payment_enabled":False,
        "google_drive_mirrors_verified_by_this_tool":False,
    },sort_keys=True))

if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        print("MOJPROP_OWNER_ISOLATED_PRIVATE_KEY_RECOVERY_HOLD="+type(exc).__name__)
        raise SystemExit(2)
