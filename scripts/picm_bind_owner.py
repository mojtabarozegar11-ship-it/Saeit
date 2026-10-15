#!/usr/bin/env python3
"""Bind the unique existing private PICM account to private owner-id (once).

Run as cPanel owner in the real Django virtualenv before deploying the owner
guard. No passwords, telephone numbers, or user ids are printed to CI.
"""
import os
from pathlib import Path
import pwd
import re
import sys
import tempfile

sys.path.insert(0, "/home/zomorod2/Saeit-staging")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def main():
    if pwd.getpwuid(os.getuid()).pw_name != "zomorod2":
        raise RuntimeError("UNEXPECTED_CPANEl_USER")
    import django
    django.setup()
    from django.contrib.auth import get_user_model
    from core.picm_views import root_path

    users = list(get_user_model().objects.filter(
        username__startswith="picm-").values(
            "pk", "username", "is_active", "is_staff", "is_superuser")[:2])
    if len(users) != 1:
        raise RuntimeError("PICM_UNIQUE_OWNER_REQUIRED")
    u = users[0]
    if (not re.fullmatch(r"picm-09[0-9]{9}", str(u["username"]))
            or not u["is_active"] or u["is_staff"] or u["is_superuser"]):
        raise RuntimeError("PICM_NONPRIVILEGED_ACCOUNT_REQUIRED")
    root = root_path()
    owner_file = root / ".owner-user-id"
    if owner_file.is_symlink():
        raise RuntimeError("PICM_OWNER_FILE_SYMLINK")
    expected = str(u["pk"]) + "\n"
    if owner_file.exists():
        if owner_file.read_text(encoding="ascii") != expected:
            raise RuntimeError("PICM_OWNER_ALREADY_BOUND_TO_DIFFERENT_ACCOUNT")
        owner_file.chmod(0o600)
        print("PICM_SINGLE_OWNER_BINDING_VERIFIED")
        return
    fd, temp = tempfile.mkstemp(prefix=".picm-owner-", dir=root)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as stream:
            stream.write(expected)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, owner_file)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    print("PICM_SINGLE_OWNER_BINDING_INSTALLED")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("PICM_OWNER_BINDING_REFUSED=" + type(exc).__name__ + ":" +
              (str(exc) if str(exc) in {
                  "PICM_UNIQUE_OWNER_REQUIRED",
                  "PICM_NONPRIVILEGED_ACCOUNT_REQUIRED",
                  "PICM_OWNER_ALREADY_BOUND_TO_DIFFERENT_ACCOUNT",
                  "PICM_OWNER_FILE_SYMLINK",
                  "UNEXPECTED_CPANEl_USER"} else "UNCLASSIFIED"), file=sys.stderr)
        raise SystemExit(1)
