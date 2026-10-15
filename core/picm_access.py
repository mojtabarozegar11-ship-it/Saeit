"""Single-owner authorization for every PICM browser endpoint.

The configured owner PK is bound once on the cPanel host; never shipped
as a public phone number or password. Missing or invalid binding denies all.
"""
import hmac
import re
from pathlib import Path

def owner_id(root=None):
    if root is None:
        from .picm_views import root_path
        root = root_path()
    path = root / ".owner-user-id"
    if path.is_symlink() or not path.is_file():
        return None
    try:
        value = path.read_text(encoding="ascii")
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
