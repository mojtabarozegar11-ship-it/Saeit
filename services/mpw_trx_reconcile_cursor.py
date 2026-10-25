"""Fair, bounded reconciliation of all outstanding native TRX invoices.

A payment may be sent just before a merchant pauses checkout or a worker goes
offline. Never exclude an invoice based only on age, and never starve newer
customers behind older unresolved deposits. No payment is approved here.
"""
from __future__ import annotations
import os
import re
import stat
import tempfile
from pathlib import Path

MAX_ID=2**63-1
_CURSOR_RE=re.compile(r"^[0-9]{1,19}\n?$")


def _trusted_cursor_home(home: Path) -> Path:
    base=Path(home)
    if base.is_symlink() or not base.is_dir():
        raise ValueError("Unexpected merchant cursor directory")
    mode=stat.S_IMODE(base.stat().st_mode)
    if mode & 0o022:
        raise ValueError("Writable-by-others cursor directory")
    return base


def read_cursor(home: Path) -> int:
    root=_trusted_cursor_home(home)
    path=root/"mpw-trx-reconcile-cursor-v1"
    if not path.exists() and not path.is_symlink():
        return 0
    if path.is_symlink() or not path.is_file() or path.stat().st_size>32:
        raise ValueError("Unsafe cursor state file")
    contents=path.read_text("ascii")
    if not _CURSOR_RE.fullmatch(contents):
        raise ValueError("Invalid cursor state")
    result=int(contents)
    if result>MAX_ID:
        raise ValueError("Cursor ID out of range")
    return result


def write_cursor(home: Path, value: int) -> None:
    root=_trusted_cursor_home(home)
    if type(value) is not int or not 0<=value<=MAX_ID:
        raise ValueError("Invalid checkpoint")
    target=root/"mpw-trx-reconcile-cursor-v1"
    if target.is_symlink():
        raise ValueError("Unsafe cursor checkpoint target")
    fd,temporary=tempfile.mkstemp(prefix=".mpw-trx-reconcile-",dir=root)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,"w",encoding="ascii") as handle:
            handle.write(str(value)+"\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary,target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def pick_pending_page(model,provider: str,status: str,last_id: int,limit: int=6):
    """Visit every unpaid existing intent over repeated, externally locked runs."""
    if (type(last_id) is not int or last_id<0 or last_id>MAX_ID
        or type(limit) is not int or not 1<=limit<=100):
        raise ValueError("Invalid bounded queue scan")
    pool=model.objects.filter(provider=provider,status=status)
    first=list(pool.filter(pk__gt=last_id).select_related("order").order_by("pk")[:limit])
    if len(first)>=limit:
        return first
    rest=list(pool.filter(pk__lte=last_id).select_related("order").order_by("pk")[:limit-len(first)])
    return first+rest
