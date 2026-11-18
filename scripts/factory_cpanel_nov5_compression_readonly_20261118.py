#!/usr/bin/env python3
"""Measure actual gzip -1 stream size for ONLY two existing cPanel Nov5 SQLite files.

Read-only, zero output files, no SQL, no factory startup, no removal. This
feasibility proof is NOT authorization to replace or destroy original files.
"""
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
import sys
import time
import zlib

ROOT = Path('/home/zomorod2/restore-staging/factory')
EXPECTED = (
    ('nov5-a', 'master-before-20261105T154953Z.sqlite3', 1408634880,
     'a9fd2175f9ace1a81d67cf7145e54b8621fd44cc06b0b2739bdc9345e21750e2'),
    ('nov5-b', 'master-before-20261105T210434Z.sqlite3', 1408634880,
     '402c16b67d430132701435eb4b3f79de88cd5c2479bb07c741c6674708a931be'),
)


def identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def check_parent():
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('WRONG_OWNER')
    for path in (Path('/home/zomorod2'), ROOT.parent, ROOT):
        s = path.lstat()
        if not stat.S_ISDIR(s.st_mode) or s.st_uid != os.geteuid() or s.st_mode & 0o022:
            raise RuntimeError('UNTRUSTED_PARENT')


def measure(item):
    name, filename, required, expected = item
    p = ROOT / filename
    st = p.lstat()
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
            or st.st_nlink != 1 or st.st_size != required):
        raise RuntimeError('UNTRUSTED_SOURCE')
    for suffix in ('-wal', '-shm', '-journal'):
        x = p.with_name(filename + suffix)
        if x.exists() or x.is_symlink():
            raise RuntimeError('SIDE_CAR_PRESENT')
    fd = os.open(p, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        if identity(os.fstat(fd)) != identity(st):
            raise RuntimeError('SOURCE_CHANGED_BEFORE_READ')
        sha = hashlib.sha256()
        gzsha = hashlib.sha256()
        zipper = zlib.compressobj(level=1, wbits=31)
        original_bytes = 0
        compressed_bytes = 0
        header = os.read(fd, 16)
        if header != b'SQLite format 3\x00':
            raise RuntimeError('NOT_SQLITE')
        os.lseek(fd, 0, os.SEEK_SET)
        while True:
            buf = os.read(fd, 1024 * 1024)
            if not buf:
                break
            original_bytes += len(buf)
            if original_bytes > required:
                raise RuntimeError('SOURCE_GREW')
            sha.update(buf)
            part = zipper.compress(buf)
            compressed_bytes += len(part)
            gzsha.update(part)
        trailer = zipper.flush(zlib.Z_FINISH)
        compressed_bytes += len(trailer)
        gzsha.update(trailer)
        if (original_bytes != required or sha.hexdigest() != expected
                or identity(os.fstat(fd)) != identity(st)):
            raise RuntimeError('SOURCE_INTEGRITY_MISMATCH')
        if identity(p.lstat()) != identity(st):
            raise RuntimeError('SOURCE_REPLACED')
        if not 0 < compressed_bytes < required:
            raise RuntimeError('NO_VERIFIED_COMPRESSION_BENEFIT')
        return {'snapshot': name, 'original_bytes': required,
                'actual_gzip_level1_bytes': compressed_bytes,
                'gzip_sha256_for_same_stream_encoder': gzsha.hexdigest(),
                'source_sha256_verified': True, 'source_unchanged': True,
                'potential_reclaim_bytes_if_replaced': required - compressed_bytes}
    finally:
        os.close(fd)


def main():
    t = time.monotonic()
    check_parent()
    results = [measure(x) for x in EXPECTED]
    original = sum(x['original_bytes'] for x in results)
    compressed = sum(x['actual_gzip_level1_bytes'] for x in results)
    report = {'schema': 'factory.cpanel.nov5.gzip1-readonly-capacity.v1',
              'items': results, 'files': len(results),
              'source_total_bytes': original,
              'prospective_gzip1_total_bytes': compressed,
              'potential_net_reclaim_bytes_if_exact_files_replaced': original - compressed,
              'potential_reclaim_is_not_actual': True,
              'compressed_backups_created': 0, 'source_files_deleted': 0,
              'source_files_modified': 0, 'factory_started': False,
              'new_current_database_backup_created': False,
              'cloud_upload_bytes': 0,
              'owner_delete_authorization_given': False,
              'elapsed_seconds': round(time.monotonic() - t, 2)}
    print('FACTORY_CPANEL_GZIP1_READONLY_AUDIT=' + json.dumps(report,sort_keys=True,separators=(',',':')), flush=True)


if __name__ == '__main__':
    try:
        main()
    except BaseException as err:
        code = str(err) if type(err) is RuntimeError else type(err).__name__
        print('FACTORY_CPANEL_GZIP1_AUDIT_HOLD=' + code, file=sys.stderr, flush=True)
        sys.exit(2)
