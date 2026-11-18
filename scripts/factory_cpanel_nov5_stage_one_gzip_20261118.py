#!/usr/bin/env python3
"""Stage ONE existing Nov5 cPanel SQLite gzip copy after quota/identity admission.

No historical source deletion, replacement, MySQL, process, cron or cloud access.
Only a NEW private .gz copy is permitted. No mode can unlink source.
"""
import hashlib
import json
import os
from pathlib import Path
import pwd
import secrets
import stat
import subprocess
import sys
import zlib

ROOT = Path('/home/zomorod2/restore-staging/factory')
SOURCE = 'master-before-20261105T154953Z.sqlite3'
SOURCE_BYTES = 1408634880
SOURCE_SHA = 'a9fd2175f9ace1a81d67cf7145e54b8621fd44cc06b0b2739bdc9345e21750e2'
GZIP_BYTES = 279659980
GZIP_SHA = '591a0b10b2f782cb7cb8db3fa340f4b3827b8d1db2960ca89a507098ccc35c78'
RESERVE_MIB = 768


def identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def admission():
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('OWNER_MISMATCH')
    for path in (Path('/home/zomorod2'), ROOT.parent, ROOT):
        st = path.lstat()
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid() or st.st_mode & 0o022:
            raise RuntimeError('PARENT_UNTRUSTED')
    path = ROOT / SOURCE
    st = path.lstat()
    if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid()
            or st.st_nlink != 1 or st.st_size != SOURCE_BYTES):
        raise RuntimeError('SOURCE_UNTRUSTED')
    for suffix in ('-wal', '-shm', '-journal'):
        aux = ROOT / (SOURCE + suffix)
        if aux.exists() or aux.is_symlink():
            raise RuntimeError('SIDE_CAR_PRESENT')
    target = ROOT / (SOURCE + '.gz')
    if target.is_symlink():
        raise RuntimeError('DESTINATION_SYMLINK_DENIED')
    return path, target, st, target.exists()


def quota_mib():
    try:
        p = subprocess.run(['uapi', '--output=json', 'Quota', 'get_quota_info'],
                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=30, check=False)
        if p.returncode or len(p.stdout) > 32768:
            raise ValueError()
        body = json.loads(p.stdout).get('result', {})
        if body.get('status') not in (1, True):
            raise ValueError()
        data = body.get('data', {})
        remain = data.get('megabytes_remain')
        limit = data.get('megabyte_limit')
        if (type(remain) not in (int, float) or type(limit) not in (int, float)
                or remain <= 0 or limit < 1 or remain > limit):
            raise ValueError()
        return float(remain)
    except (OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired):
        raise RuntimeError('CPANEL_CURRENT_QUOTA_UNAVAILABLE') from None


def write_all(fd, data):
    view = memoryview(data)
    while view:
        n = os.write(fd, view)
        if n <= 0:
            raise RuntimeError('WRITING_COMPRESSED_FILE_FAILED')
        view = view[n:]


def verify_compressed(path):
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    try:
        s = os.fstat(fd)
        if (not stat.S_ISREG(s.st_mode) or s.st_uid != os.geteuid()
                or s.st_size != GZIP_BYTES or s.st_mode & 0o077):
            raise RuntimeError('STAGED_FILE_NOT_PRIVATE')
        digest_gz, digest_plain = hashlib.sha256(), hashlib.sha256()
        decomp = zlib.decompressobj(wbits=31)
        count_gz, count_plain = 0, 0
        while True:
            block = os.read(fd, 1024 * 1024)
            if not block:
                break
            count_gz += len(block)
            digest_gz.update(block)
            plain = decomp.decompress(block, SOURCE_BYTES - count_plain + 1)
            count_plain += len(plain)
            digest_plain.update(plain)
            if count_gz > GZIP_BYTES or count_plain > SOURCE_BYTES:
                raise RuntimeError('STAGED_FILE_OVERSIZE')
            if decomp.unconsumed_tail:
                raise RuntimeError('STAGED_GZIP_UNCONSUMED_TAIL')
        extra = decomp.flush()
        count_plain += len(extra)
        digest_plain.update(extra)
        if (not decomp.eof or decomp.unused_data or count_gz != GZIP_BYTES
                or count_plain != SOURCE_BYTES or digest_gz.hexdigest() != GZIP_SHA
                or digest_plain.hexdigest() != SOURCE_SHA):
            raise RuntimeError('STAGED_GZIP_RESTORE_INVALID')
    finally:
        os.close(fd)


def stage():
    source, destination, before, already = admission()
    if already:
        verify_compressed(destination)
        if identity(source.lstat()) != identity(before):
            raise RuntimeError('ORIGINAL_SOURCE_CHANGED')
        return {'schema': 'factory.cpanel.nov5.single-gzip-stage.v1',
                'snapshot': 'nov5-a', 'gzip_bytes_stored': GZIP_BYTES,
                'gzip_sha256': GZIP_SHA, 'decompressed_sha256_matches_source': True,
                'gzip_crc_verified': True, 'snapshot_unchanged': True,
                'already_staged_verified': True,
                'new_compressed_backup_files_created': 0,
                'source_raw_files_deleted': 0, 'source_raw_files_modified': 0,
                'factory_started': False, 'production_mysql_accessed': False,
                'space_reclaimed': 0, 'safe_to_delete_raw': False,
                'owner_raw_delete_authorization_given': False}
    quota_before = quota_mib()
    required_mib = GZIP_BYTES / (1024 * 1024) + RESERVE_MIB
    if quota_before < required_mib:
        raise RuntimeError('INSUFFICIENT_ACCOUNT_FREE_WITH_RESERVE')
    tmp = ROOT / ('.' + SOURCE + '.gz.owner-stage-' + secrets.token_hex(12))
    source_fd = os.open(source, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    temp_fd = None
    try:
        if identity(os.fstat(source_fd)) != identity(before):
            raise RuntimeError('SOURCE_CHANGED_BEFORE_STAGE')
        if os.read(source_fd, 16) != b'SQLite format 3\x00':
            raise RuntimeError('NOT_SQLITE')
        os.lseek(source_fd, 0, os.SEEK_SET)
        temp_fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        gz = zlib.compressobj(level=1, wbits=31)
        source_digest, gzip_digest = hashlib.sha256(), hashlib.sha256()
        count_raw = count_gz = 0
        while True:
            block = os.read(source_fd, 1024 * 1024)
            if not block:
                break
            count_raw += len(block)
            if count_raw > SOURCE_BYTES:
                raise RuntimeError('SOURCE_GREW')
            source_digest.update(block)
            packet = gz.compress(block)
            count_gz += len(packet)
            gzip_digest.update(packet)
            if count_gz > GZIP_BYTES:
                raise RuntimeError('COMPRESSED_SIZE_EXCEEDED')
            write_all(temp_fd, packet)
        packet = gz.flush(zlib.Z_FINISH)
        count_gz += len(packet)
        gzip_digest.update(packet)
        if count_gz > GZIP_BYTES:
            raise RuntimeError('COMPRESSED_SIZE_EXCEEDED')
        write_all(temp_fd, packet)
        os.fsync(temp_fd)
        os.close(temp_fd)
        temp_fd = None
        if (count_raw != SOURCE_BYTES or count_gz != GZIP_BYTES
                or source_digest.hexdigest() != SOURCE_SHA
                or gzip_digest.hexdigest() != GZIP_SHA
                or identity(os.fstat(source_fd)) != identity(before)
                or identity(source.lstat()) != identity(before)):
            raise RuntimeError('SOURCE_OR_COMPRESSED_HASH_CHANGED')
        verify_compressed(tmp)
        quota_during = quota_mib()
        if quota_during < RESERVE_MIB:
            raise RuntimeError('QUOTA_RESERVE_LOST')
        if destination.exists() or destination.is_symlink():
            raise RuntimeError('DESTINATION_RACE')
        os.link(tmp, destination, follow_symlinks=False)
        dfd = os.open(ROOT, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
        # Remove ONLY this run's new staging alias, not historical originals.
        os.unlink(tmp)
        verify_compressed(destination)
        return {'schema': 'factory.cpanel.nov5.single-gzip-stage.v1',
                'snapshot': 'nov5-a', 'gzip_bytes_stored': GZIP_BYTES,
                'gzip_sha256': GZIP_SHA, 'decompressed_sha256_matches_source': True,
                'gzip_crc_verified': True, 'snapshot_unchanged': True,
                'quota_remaining_mib_before': quota_before,
                'quota_remaining_mib_staging_check': quota_during,
                'quota_reserve_mib': RESERVE_MIB,
                'already_staged_verified': False,
                'new_compressed_backup_files_created': 1,
                'source_raw_files_deleted': 0,
                'source_raw_files_modified': 0,
                'factory_started': False, 'production_mysql_accessed': False,
                'space_reclaimed': 0, 'safe_to_delete_raw': False,
                'owner_raw_delete_authorization_given': False}
    finally:
        if temp_fd is not None:
            os.close(temp_fd)
        os.close(source_fd)
        if tmp.exists():
            os.unlink(tmp)


if __name__ == '__main__':
    try:
        print('FACTORY_CPANEL_GZIP_STAGE=' + json.dumps(stage(), sort_keys=True, separators=(',', ':')), flush=True)
    except BaseException as error:
        code = str(error) if type(error) is RuntimeError else type(error).__name__
        print('FACTORY_CPANEL_GZIP_STAGE_HOLD=' + code, file=sys.stderr, flush=True)
        sys.exit(2)
