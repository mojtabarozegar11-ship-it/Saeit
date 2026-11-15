#!/usr/bin/env python3
"""C28: bounded *real* file backup + isolated restore on authorized cPanel.

Public, explicitly allowlisted HTML only. NEVER restores into the live docroot,
changes Passenger/rewrite config or claims a recoverable DB/full-site backup.
The output is sanitized, no HTML, personal data, paths or secrets.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat
import sys

HOME = Path('/home/zomorod2')
ROOT = HOME / 'mojplaywin.com'
VAULT = HOME / '.mojprop-static-restore-evidence'
PUBLIC_FILES = ('moj-prop/index.html', 'moj-prop/catalog/index.html')
RUN_ID = re.compile(r'[1-9][0-9]{0,18}\Z')
MAX_BYTES = 512_000
MIN_SPARE_BYTES = 64 * 1024 * 1024


def _meta(path: Path, *, kind: str, uid: int) -> os.stat_result:
    info = path.lstat()
    if info.st_uid != uid or info.st_mode & stat.S_IWOTH:
        raise RuntimeError('unsafe owner or world writable path')
    if kind == 'dir' and not stat.S_ISDIR(info.st_mode):
        raise RuntimeError('expected owned directory')
    if kind == 'file' and (not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES
                           or info.st_nlink != 1):
        raise RuntimeError('not an acceptable public regular file')
    return info


def _read_public(path: Path, *, uid: int) -> bytes:
    pre = _meta(path, kind='file', uid=uid)
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_CLOEXEC', 0))
    with os.fdopen(fd, 'rb') as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != uid or info.st_ino != pre.st_ino or info.st_size != pre.st_size or info.st_mtime_ns != pre.st_mtime_ns:
            raise RuntimeError('public file changed during read')
        body = handle.read(MAX_BYTES + 1)
    if not 64 <= len(body) <= MAX_BYTES:
        raise RuntimeError('invalid bounded public file')
    return body


def _create_file(path: Path, body: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    with os.fdopen(fd, 'wb') as writer:
        writer.write(body)
        writer.flush()
        os.fsync(writer.fileno())
    if path.stat().st_mode & 0o077:
        raise RuntimeError('non-private backup')


def audit_and_restore(*, home: Path = HOME, root: Path = ROOT,
                      vault: Path = VAULT, owner: str = 'zomorod2',
                      run_id: str) -> dict:
    if not RUN_ID.fullmatch(run_id):
        raise ValueError('bad run identifier')
    uid = os.geteuid()
    if pwd.getpwuid(uid).pw_name != owner:
        raise RuntimeError('unauthorized tenant identity')
    if root != home / 'mojplaywin.com' or vault != home / '.mojprop-static-restore-evidence':
        raise ValueError('out-of-scope root or archive')
    _meta(home, kind='dir', uid=uid)
    _meta(root, kind='dir', uid=uid)
    _meta(root / 'moj-prop', kind='dir', uid=uid)
    _meta(root / 'moj-prop' / 'catalog', kind='dir', uid=uid)
    # Restrict to two already-public files. No database, environment or buyer data.
    sources = {}
    for rel in PUBLIC_FILES:
        sources[rel] = _read_public(root / rel, uid=uid)
    spare = os.statvfs(home)
    if spare.f_bavail * spare.f_frsize < MIN_SPARE_BYTES + 3 * sum(map(len, sources.values())):
        raise RuntimeError('insufficient free space for private isolated rehearsal')
    if vault.is_symlink():
        raise RuntimeError('vault symlink denied')
    if vault.exists():
        meta = _meta(vault, kind='dir', uid=uid)
        if meta.st_mode & 0o077:
            raise RuntimeError('vault not private')
    else:
        vault.mkdir(mode=0o700)
        os.chmod(vault, 0o700)
    evidence = vault / run_id
    # Never reuse a run identifier, modify or delete an earlier backup.
    evidence.mkdir(mode=0o700)
    base = evidence / 'backup'
    second = evidence / 'isolated-restore'
    base.mkdir(mode=0o700)
    second.mkdir(mode=0o700)
    digests = {}
    for name, body in sources.items():
        # Numeric private file IDs, never derived from untrusted paths.
        idx = PUBLIC_FILES.index(name)
        fname = f'file-{idx}.bin'
        _create_file(base / fname, body)
        persisted = _read_public(base / fname, uid=uid)
        if persisted != body:
            raise RuntimeError('backup hash/readback mismatch')
        _create_file(second / fname, persisted)
        restored = _read_public(second / fname, uid=uid)
        digest = hashlib.sha256(body).hexdigest()
        if hashlib.sha256(restored).hexdigest() != digest:
            raise RuntimeError('isolated restore digest mismatch')
        # Double-check production bytes stayed unchanged throughout.
        if hashlib.sha256(_read_public(root / name, uid=uid)).hexdigest() != digest:
            raise RuntimeError('live source changed; abort')
        digests[f'file-{idx}'] = digest
    manifest = {
        'schema': 'mojprop.static.restore.evidence.v1',
        'run_id': run_id,
        'relative_public_allowlist': list(PUBLIC_FILES),
        'sha256': digests,
        'verified_isolated_restore': True,
        'live_files_modified': False,
        'database_backup_or_restore': False,
        'all_site_backup_proven': False,
        'subsite_isolation_proven': False,
        'release_permitted': False,
        'payment_permitted': False,
        'revenue_proven': False,
    }
    _create_file(evidence / 'manifest.json', json.dumps(manifest, sort_keys=True).encode())
    # Output only boolean contract and count, no sensitive file or URL data.
    return {'schema': manifest['schema'], 'private_file_backup_count': 2,
            'verified_isolated_restore': True, 'live_files_modified': False,
            'database_backup_or_restore': False, 'all_site_backup_proven': False,
            'subsite_isolation_proven': False, 'release_permitted': False,
            'payment_permitted': False, 'revenue_proven': False}


def main() -> int:
    try:
        report = audit_and_restore(run_id=sys.argv[1])
    except (IndexError, OSError, ValueError, RuntimeError, KeyError) as error:
        print(json.dumps({'schema': 'mojprop.static.restore.evidence.v1',
                          'error_class': type(error).__name__,
                          'verified_isolated_restore': False,
                          'release_permitted': False, 'payment_permitted': False}))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
