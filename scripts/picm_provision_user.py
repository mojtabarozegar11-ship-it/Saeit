#!/usr/bin/env python3
"""One-time PICM account provisioner.

Only ciphertext goes through the public repository. The RSA-OAEP decrypt key
stays in the private cPanel home; the plaintext credential is never logged.
Run only as the verified MojPlayWin cPanel user within active Django venv.
"""
import base64
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys


def main():
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("INVALID_ACCOUNT")
    home = Path("/home/zomorod2")
    root = home / ".picm-queue"
    key = root / "login-provision-rsa-private.pem"
    if root.is_symlink() or key.is_symlink() or not key.is_file():
        raise RuntimeError("PRIVATE_DECRYPTION_KEY_MISSING")
    payload = sys.stdin.buffer.read(2200).strip()
    if not payload or len(payload) > 1800:
        raise RuntimeError("INVALID_ENCRYPTED_INPUT")
    cipher = base64.b64decode(payload, validate=True)
    if len(cipher) != 384:
        raise RuntimeError("UNEXPECTED_RSA_CIPHERTEXT")
    completed = subprocess.run(
        ["openssl", "pkeyutl", "-decrypt", "-inkey", str(key),
         "-pkeyopt", "rsa_padding_mode:oaep",
         "-pkeyopt", "rsa_oaep_md:sha256"],
        input=cipher, capture_output=True, timeout=15, check=True)
    data = json.loads(completed.stdout)
    if set(data) != {"username", "password"}:
        raise RuntimeError("INVALID_SECRET_SCHEMA")
    username = data["username"]
    password = data["password"]
    if (not isinstance(username, str) or not re.fullmatch(r"09[0-9]{9}", username)
            or not isinstance(password, str) or len(password) < 10
            or len(password) > 128):
        raise RuntimeError("INVALID_PICM_LOGIN_CREDENTIALS")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    # The one-time installer lives outside the Django application directory.
    sys.path.insert(0, "/home/zomorod2/Saeit-staging")
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from django.db import transaction
    Model = get_user_model()
    with transaction.atomic():
        match = Model.objects.select_for_update().filter(username=username).first()
        if match and (match.is_staff or match.is_superuser):
            raise RuntimeError("REFUSE_EXISTING_PRIVILEGED_ACCOUNT")
        if match is None:
            match = Model(username=username, is_active=True)
        match.is_staff = False
        match.is_superuser = False
        match.is_active = True
        match.set_password(password)
        match.save()
        assert match.check_password(password)
    # Destroy the one-use private key after verifying the Django hash is stored.
    key.unlink()
    print("PICM_PRIVATE_LOGIN_USER_CREATED_OR_UPDATED")
    print("PICM_PRIVATE_RSA_PROVISIONING_KEY_REMOVED")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Never leak a decrypted username/password via exception messages.
        print("PICM_PRIVATE_LOGIN_PROVISION_ERROR=" + type(exc).__name__, file=sys.stderr)
        raise SystemExit(1)
