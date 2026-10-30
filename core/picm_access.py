"""Single-owner authorization for every PICM browser endpoint.

The configured owner PK is bound once on the cPanel host; never shipped
as a public phone number or password. Missing or invalid binding denies all.
"""
import hmac
import os
import re
import stat
from pathlib import Path

def owner_id(root=None):
    if root is None:
        from .picm_views import root_path
        root = root_path()
    path = Path(root) / ".owner-user-id"
    # Bind authorization to an opened inode, not a pathname that can
    # be swapped to a symlink between is_symlink() and read_text().
    if not hasattr(os, "O_NOFOLLOW"):
        return None
    flags = (os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
             | getattr(os, "O_NONBLOCK", 0))
    try:
        fd = os.open(path, flags)
        try:
            before = os.fstat(fd)
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                    or not 1 <= before.st_size <= 19):
                return None
            raw = os.read(fd, 20)
            after = os.fstat(fd)
            if (len(raw) != before.st_size or after.st_size != before.st_size
                    or after.st_ino != before.st_ino
                    or after.st_mtime_ns != before.st_mtime_ns):
                return None
        finally:
            os.close(fd)
        value = raw.decode("ascii")
    except (UnicodeError, OSError):
        return None
    if not re.fullmatch(r"[1-9][0-9]{0,17}\n?", value):
        return None
    return value.strip()

def owner_allowed(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if not getattr(user, "is_active", True):
        return False
    expected = owner_id()
    actual = getattr(user, "pk", None)
    return (expected is not None and actual is not None
            and hmac.compare_digest(str(actual), expected))
