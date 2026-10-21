"""Private ZIP storage using only server-generated opaque keys.

No URL-provided filename is ever joined onto a filesystem path; O_NOFOLLOW and
relative dirfd operations prevent symlink escapes. This is a local-files pilot,
not yet a malware scanning/upload pipeline or object-store integration.
"""
import hashlib
import os
import re
import stat
from pathlib import Path
from django.conf import settings
from .services import CommerceUnavailable, CommerceRejected

HEX32 = re.compile(r'^[a-f0-9]{32}$')
HEX64 = re.compile(r'^[a-f0-9]{64}$')
MAX_PILOT_ZIP_SIZE = 100 * 1024 * 1024


def open_verified_product(product):
    key = product.file_key
    if not isinstance(key, str) or not HEX32.fullmatch(key):
        raise CommerceRejected('Unsafe stored key')
    if not isinstance(product.sha256, str) or not HEX64.fullmatch(product.sha256):
        raise CommerceRejected('Missing approved file checksum')
    root_value = getattr(settings, 'MOJ_COMMERCE_PRIVATE_ROOT', None)
    if not isinstance(root_value, str) or not os.path.isabs(root_value):
        raise CommerceUnavailable('Private media root not configured')
    root = Path(root_value)
    if root.is_symlink() or not root.is_dir() or root.stat().st_mode & 0o007:
        raise CommerceUnavailable('Private media root must be a non-public directory')
    flags = os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0)
    dir_flags = flags | getattr(os, 'O_DIRECTORY', 0)
    fdroot = os.open(str(root), dir_flags)
    fdseller = None
    fdfile = None
    try:
        fdseller = os.open(product.merchant.public_id.hex, dir_flags, dir_fd=fdroot)
        fdfile = os.open(key + '.zip', flags, dir_fd=fdseller)
        st = os.fstat(fdfile)
        if not stat.S_ISREG(st.st_mode) or st.st_size <= 0 or st.st_size > MAX_PILOT_ZIP_SIZE:
            raise CommerceRejected('Stored asset is not a valid bounded regular file')
        # Test integrity on every download in the pilot; optimize only after an
        # independently-reviewed immutable object storage/ingest solution.
        h = hashlib.sha256()
        while True:
            chunk = os.read(fdfile, 65536)
            if not chunk:
                break
            h.update(chunk)
        if h.hexdigest() != product.sha256:
            raise CommerceRejected('Stored asset checksum mismatch')
        os.lseek(fdfile, 0, os.SEEK_SET)
        result = os.fdopen(fdfile, 'rb')
        fdfile = None
        return result
    finally:
        if fdfile is not None:
            os.close(fdfile)
        if fdseller is not None:
            os.close(fdseller)
        os.close(fdroot)