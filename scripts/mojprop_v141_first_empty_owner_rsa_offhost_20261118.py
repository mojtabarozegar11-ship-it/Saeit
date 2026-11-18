#!/usr/bin/env python3
"""Real bounded ZERO-CUSTOMER off-cPanel encrypted archive on owner runner.

Source is a separate first-install SQLite snapshot, never production MariaDB.
ONLY RSA-3072 owner-public-key-encrypted data persists. No key escrow is stored
on runner, public GitHub, Actions artifact, Drive, or this backup directory.
All source bytes are held in RAM except a disposable 0700 local SQLite
verification file, always unlinked when the context exits.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3
import stat
import sys
import tempfile
import zipfile
import zlib

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding, rsa

LIMIT = 8 * 1024 * 1024
SCHEMA = "mojprop.v141.initial-zero-customer.owner-rsa3072-aes256gcm.v1"
EXPECTED_RECIPIENT_SHA = "a7b3ef1995681d3963d56570ce68b2c4cf9785e99163f66795592cb907632d74"
PUBLIC_KEY = Path("security/factory_recovery_public_20261030.pem")
REQUIRED = (
    "prop_firm_propv141nativeorder",
    "prop_firm_propv141nativereceipt",
    "prop_firm_propglobaltrxsettlement",
    "prop_firm_propv141simstate",
    "prop_firm_propv141virtualbook",
)
HOME = Path.home()
BASE = HOME / ".mojprop-rsa3072-offhost-backups"

def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()

def _canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")

def _isolate_verify(raw: bytes) -> None:
    if not raw.startswith(b"SQLite format 3\x00") or len(raw) > LIMIT:
        raise ValueError("NOT_BOUNDED_SQLITE")
    private_tmp = Path(os.environ.get("RUNNER_TEMP", str(HOME)))
    if not private_tmp.is_dir() or private_tmp.is_symlink():
        raise ValueError("UNTRUSTED_TEMP_PARENT")
    with tempfile.TemporaryDirectory(prefix=".mojprop-isolate-", dir=private_tmp) as d:
        os.chmod(d, 0o700)
        path = Path(d) / "snapshot.sqlite3"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
        uri = path.as_uri() + "?mode=ro&immutable=1"
        with sqlite3.connect(uri, uri=True, timeout=4) as db:
            rows = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if not set(REQUIRED).issubset(rows):
                raise ValueError("UNEXPECTED_PRIVATE_SCHEMA")
            if db.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise ValueError("SQLITE_FULL_INTEGRITY_FAILURE")
            for t in REQUIRED:
                if db.execute('SELECT COUNT(*) FROM "' + t + '"').fetchone()[0] != 0:
                    raise ValueError("PAID_ROW_PRESENT")
            for t in ("auth_user", "django_session"):
                if t in rows and db.execute('SELECT COUNT(*) FROM "' + t + '"').fetchone()[0] != 0:
                    raise ValueError("AUTH_OR_SESSION_ROW_PRESENT")

def _public_key():
    if PUBLIC_KEY.is_symlink() or not PUBLIC_KEY.is_file() or PUBLIC_KEY.stat().st_size > 16384:
        raise ValueError("PINNED_RECOVERY_PUBLIC_KEY_ABSENT")
    pub = serialization.load_pem_public_key(PUBLIC_KEY.read_bytes(), backend=default_backend())
    if not isinstance(pub, rsa.RSAPublicKey) or pub.key_size != 3072:
        raise ValueError("PINNED_RECOVERY_KEY_NOT_RSA3072")
    der = pub.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    if _sha(der) != EXPECTED_RECIPIENT_SHA:
        raise ValueError("RECOVERY_KEY_FINGERPRINT_MISMATCH")
    return pub

def _private_dir() -> None:
    if os.geteuid() == 0 or not HOME.is_absolute():
        raise ValueError("NONROOT_OWNER_RUNNER_REQUIRED")
    st = HOME.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid():
        raise ValueError("UNTRUSTED_OWNER_HOME")
    if BASE.is_symlink():
        raise ValueError("SYMLINK_DESTINATION")
    try:
        BASE.mkdir(mode=0o700)
    except FileExistsError:
        pass
    bs = BASE.lstat()
    if (not stat.S_ISDIR(bs.st_mode) or bs.st_uid != os.geteuid()
            or (bs.st_mode & 0o077)):
        raise ValueError("OWNER_PRIVATE_BACKUP_DIRECTORY_REQUIRED")

def _durable(path: Path, value: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(value)
        f.flush()
        os.fsync(f.fileno())

def main() -> dict:
    _private_dir()
    pub = _public_key()
    raw = sys.stdin.buffer.read(LIMIT + 1)
    if not raw or len(raw) > LIMIT:
        raise ValueError("SOURCE_EMPTY_OR_EXCEEDS_8MIB")
    _isolate_verify(raw)
    source_sha = _sha(raw)
    compressed = zlib.compress(raw, level=6)
    session_key = secrets.token_bytes(32)
    nonce = secrets.token_bytes(12)
    aad = _canonical({"schema":SCHEMA, "source_sha256":source_sha, "source_bytes":len(raw)})
    ciphertext = AESGCM(session_key).encrypt(nonce, compressed, aad)
    wrapped = pub.encrypt(session_key, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    # Actually prove authenticated AEAD round trip, decompression and full SQLite integrity.
    recovered = zlib.decompress(AESGCM(session_key).decrypt(nonce, ciphertext, aad))
    if recovered != raw:
        raise ValueError("ENCRYPTED_ROUNDTRIP_MISMATCH")
    _isolate_verify(recovered)
    manifest = {
        "schema": SCHEMA,
        "recipient_spki_sha256": EXPECTED_RECIPIENT_SHA,
        "wrapped_session_key_rsa_oaep_sha256_b64": base64.b64encode(wrapped).decode("ascii"),
        "aes256gcm_nonce_b64": base64.b64encode(nonce).decode("ascii"),
        "aes256gcm_aad_b64": base64.b64encode(aad).decode("ascii"),
        "cipher_sha256": _sha(ciphertext),
        "source_sha256": source_sha,
        "source_bytes":len(raw),
        "compressed_bytes":len(compressed),
        "cipher_bytes":len(ciphertext),
        "source": "owner-cpanel-immutable-initial-private-zero-customer-sqlite",
        "scope": "isolated_initial_zero_customer_only_not_current_mariadb",
        "independent_private_key_restore_proven": False,
        "cloud_dual_mirror_proven": False,
        "production_payments_enabled": False,
    }
    run = "initial-" + secrets.token_hex(12)
    directory = BASE / run
    directory.mkdir(mode=0o700)
    package = directory / "mojprop-first-empty-merchant-OWNER-RSA3072-AES256GCM.zip"
    with tempfile.TemporaryFile(dir=directory) as scratch:
        with zipfile.ZipFile(scratch, mode="w", compression=zipfile.ZIP_STORED) as z:
            z.writestr("encrypted-snapshot.bin", ciphertext)
            z.writestr("manifest.json", _canonical(manifest))
        scratch.flush()
        scratch.seek(0)
        package_bytes = scratch.read(LIMIT + 1024 * 1024)
    _durable(package, package_bytes)
    with zipfile.ZipFile(package, "r") as z:
        got = z.read("encrypted-snapshot.bin")
        saved = json.loads(z.read("manifest.json"))
        if _sha(got) != manifest["cipher_sha256"] or saved != manifest:
            raise ValueError("PERSISTED_CIPHER_PACKAGE_READBACK_MISMATCH")
    dir_fd = os.open(directory, os.O_RDONLY | getattr(os,"O_DIRECTORY",0) | getattr(os,"O_NOFOLLOW",0))
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)
    return {
        "schema": "mojprop.v141.owner-offhost-rsa-backup-receipt.v1",
        "source_bytes":len(raw),
        "source_sha256":source_sha,
        "cipher_bytes":len(ciphertext),
        "saved_package_bytes":len(package_bytes),
        "saved_package_sha256":_sha(package_bytes),
        "backup_saved_private_vps_owner":True,
        "local_encrypted_roundtrip_verified":True,
        "local_sqlite_integrity_and_empty_paid_rows_verified":True,
        "owner_rsa3072_recovery_public_key_pinned":True,
        "private_key_present_on_runner":False,
        "independent_owner_private_key_restore_proven":False,
        "two_google_drive_mirrors_uploaded":False,
        "factory_started":False,
        "production_mariadb_accessed":False,
        "public_site_deployed":False,
        "tron_funds_received":False,
        "original_source_deleted":False,
    }

if __name__ == "__main__":
    try:
        report = main()
        print("MOJPROP_OWNER_OFFHOST_RSA_BACKUP="+json.dumps(report,sort_keys=True),flush=True)
    except Exception as e:
        print("MOJPROP_OWNER_OFFHOST_RSA_BACKUP_HOLD="+type(e).__name__, flush=True)
        raise SystemExit(2)
