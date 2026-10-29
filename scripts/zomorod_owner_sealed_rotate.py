#!/usr/bin/env python3
"""Private one-use owner password rotation. Ciphertext in STDIN; plaintext never logged.

Intended for authorized cPanel user only, behind pinned GitHub Actions -> VPS -> cPanel.
No passwords, private keys, SQLite rows, hashes or backup contents go to stdout.
"""
from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import sys
import time

PRIVATE = Path("/home/zomorod2/.private/zomorod-business")
LEDGER = PRIVATE / "management.sqlite3"
KEY = PRIVATE / ".chat-command-rsa.key"
TOOL = PRIVATE / ".owner-rotation-tools/zomorod_owner_password_rotate.php"
CONSUMED = PRIVATE / ".owner-password-rotation-v1.consumed"
MAX_CIPHERTEXT = 2048
PURPOSE = "zomorod-owner-credential-rotation-v1"


def blocked(reason: str) -> None:
    print("OWNER_ROTATION=BLOCKED_" + reason, file=sys.stderr)
    raise SystemExit(3)


def private_metadata_ok() -> None:
    if not PRIVATE.is_dir() or PRIVATE.is_symlink():
        blocked("PRIVATE_DIRECTORY")
    if PRIVATE.stat().st_uid != os.geteuid() or PRIVATE.stat().st_mode & 0o077:
        blocked("PRIVATE_DIRECTORY_ACCESS")
    if not LEDGER.is_file() or LEDGER.is_symlink():
        blocked("DATABASE_MISSING")
    if LEDGER.stat().st_uid != os.geteuid() or LEDGER.stat().st_mode & 0o077:
        blocked("DATABASE_PERMISSIONS")
    if not KEY.is_file() or KEY.is_symlink() or KEY.stat().st_mode & 0o077:
        blocked("RECIPIENT_KEY_PERMISSIONS")


def owner_account() -> str:
    db = sqlite3.connect("file:" + str(LEDGER) + "?mode=ro", uri=True, timeout=12)
    try:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            blocked("DATABASE_INTEGRITY")
        admins = db.execute("SELECT username FROM users WHERE role='admin' AND active=1").fetchall()
        if len(admins) != 1 or not isinstance(admins[0][0], str):
            blocked("ADMIN_ACCOUNT_AMBIGUOUS")
        username = admins[0][0]
        if re.fullmatch(r"[A-Za-z0-9_]{5,40}", username) is None:
            blocked("ADMIN_USERNAME_POLICY")
        return username
    finally:
        db.close()


def php_with_sqlite() -> str:
    candidates = [
        "/opt/cpanel/ea-php83/root/usr/bin/php",
        "/opt/cpanel/ea-php82/root/usr/bin/php",
        shutil.which("php"),
    ]
    for candidate in candidates:
        if not candidate or not os.path.isfile(candidate):
            continue
        try:
            process = subprocess.run(
                [candidate, "-r", "exit(extension_loaded('pdo_sqlite')?0:1);"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if process.returncode == 0:
            return candidate
    blocked("PHP_PDO_SQLITE_MISSING")


def validate_payload(obj: object, now: int | None = None) -> tuple[str, str]:
    if not isinstance(obj, dict) or set(obj) != {"v", "purpose", "nonce", "issued_at", "password"}:
        raise ValueError("ENVELOPE_KEYS")
    if obj.get("v") != 1 or obj.get("purpose") != PURPOSE:
        raise ValueError("ENVELOPE_SCOPE")
    issued = obj.get("issued_at")
    if type(issued) is not int or abs((int(time.time()) if now is None else now) - issued) > 3600:
        raise ValueError("ENVELOPE_EXPIRED")
    nonce = obj.get("nonce")
    if not isinstance(nonce, str) or re.fullmatch(r"[a-f0-9]{32}", nonce) is None:
        raise ValueError("ENVELOPE_NONCE")
    password = obj.get("password")
    if not isinstance(password, str) or not 16 <= len(password.encode("utf-8")) <= 200:
        raise ValueError("PASSWORD_LENGTH")
    if any(ord(char) < 32 or ord(char) == 127 for char in password):
        raise ValueError("PASSWORD_CONTROL")
    return nonce, password


def decrypt_payload(encoded: bytes) -> dict:
    if len(encoded) > MAX_CIPHERTEXT:
        blocked("ENVELOPE_SIZE")
    try:
        ciphertext = base64.b64decode(encoded.strip(), validate=True)
    except (binascii.Error, ValueError):
        blocked("ENVELOPE_ENCODING")
    if not 256 <= len(ciphertext) <= 512:
        blocked("RSA_CIPHERTEXT_LENGTH")
    openssl = shutil.which("openssl")
    if not openssl:
        blocked("OPENSSL_MISSING")
    command = [
        openssl, "pkeyutl", "-decrypt", "-inkey", str(KEY),
        "-pkeyopt", "rsa_padding_mode:oaep",
        "-pkeyopt", "rsa_oaep_md:sha256",
        "-pkeyopt", "rsa_mgf1_md:sha256",
    ]
    try:
        process = subprocess.run(
            command, input=ciphertext, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=15, check=False,
        )
        if process.returncode != 0 or len(process.stdout) > 512:
            blocked("DECRYPT_FAILED")
        return json.loads(process.stdout)
    except (OSError, subprocess.TimeoutExpired, UnicodeError, ValueError):
        blocked("DECRYPT_FAILED")


def private_backup(nonce: str) -> None:
    backup_dir = PRIVATE / ".owner-rotation-backups"
    if not backup_dir.exists():
        backup_dir.mkdir(mode=0o700)
    if backup_dir.is_symlink() or backup_dir.stat().st_uid != os.geteuid() or backup_dir.stat().st_mode & 0o077:
        blocked("BACKUP_DIRECTORY")
    dest = backup_dir / ("pre-rotation-" + nonce + ".sqlite3")
    if dest.exists() or dest.is_symlink():
        blocked("BACKUP_COLLISION")
    previous_umask = os.umask(0o077)
    try:
        source = sqlite3.connect("file:" + str(LEDGER) + "?mode=ro", uri=True, timeout=12)
        target = sqlite3.connect(str(dest), timeout=12)
        try:
            source.backup(target)
            if target.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                blocked("BACKUP_INTEGRITY")
        finally:
            target.close()
            source.close()
    except (OSError, sqlite3.Error):
        blocked("BACKUP_FAILED")
    finally:
        os.umask(previous_umask)
    if not dest.is_file() or dest.stat().st_mode & 0o077:
        blocked("BACKUP_PERMISSIONS")


def inspect() -> None:
    private_metadata_ok()
    _username = owner_account()
    _php = php_with_sqlite()
    if not shutil.which("openssl"):
        blocked("OPENSSL_MISSING")
    if not TOOL.is_file() or TOOL.is_symlink() or TOOL.stat().st_uid != os.geteuid() or TOOL.stat().st_mode & 0o077:
        blocked("ROTATION_TOOL_PERMISSIONS")
    if CONSUMED.exists():
        blocked("ALREADY_CONSUMED")
    print("OWNER_PRIVATE_DB=VERIFIED")
    print("OWNER_ACTIVE_ADMIN=ONE")
    print("OWNER_PHP_SQLITE=AVAILABLE")
    print("OWNER_RSA_DECRYPTION=AVAILABLE")
    print("OWNER_ROTATION_PREFLIGHT=PASS")


def rotate() -> None:
    private_metadata_ok()
    username = owner_account()
    php = php_with_sqlite()
    if CONSUMED.exists() or CONSUMED.is_symlink():
        blocked("ALREADY_CONSUMED")
    if not TOOL.is_file() or TOOL.is_symlink() or TOOL.stat().st_mode & 0o077:
        blocked("ROTATION_TOOL_PERMISSIONS")
    raw = sys.stdin.buffer.read(MAX_CIPHERTEXT + 1)
    obj = decrypt_payload(raw)
    try:
        nonce, password = validate_payload(obj)
    except ValueError:
        blocked("ENVELOPE_POLICY")
    private_backup(nonce)
    process = subprocess.run(
        [php, str(TOOL), "rotate", str(PRIVATE), username],
        input=(password + "\n").encode("utf-8"),
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        timeout=25, check=False,
    )
    password = ""
    if process.returncode != 0 or b"OWNER_CREDENTIAL_ROTATION=SUCCESS" not in process.stdout:
        blocked("PHP_ROTATION_FAILED")
    previous_umask = os.umask(0o077)
    try:
        with CONSUMED.open("x", encoding="utf-8") as f:
            f.write("rotation_completed_utc=" + datetime.now(timezone.utc).isoformat() + "\n")
        os.chmod(CONSUMED, 0o600)
    except (OSError, FileExistsError):
        blocked("POST_ROTATION_MARKER_FAILED")
    finally:
        os.umask(previous_umask)
    print("OWNER_PASSWORD_ROTATION=SUCCESS")
    print("PRIVATE_SQLITE_BACKUP=VERIFIED")
    print("PASSWORD_OR_HASH_LOGGED=NO")
    print("SESSION_REVOCATION=NOT_VERIFIED")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"inspect", "rotate"}:
        blocked("ARGUMENTS")
    try:
        if sys.argv[1] == "inspect":
            inspect()
        else:
            rotate()
    except (OSError, sqlite3.Error, subprocess.TimeoutExpired):
        blocked("PRIVATE_EXECUTION_ERROR")


if __name__ == "__main__":
    main()
