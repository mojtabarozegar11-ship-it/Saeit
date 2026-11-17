#!/usr/bin/env python3
"""Owner-only ephemeral, digest-pinned rclone provisioning. No OAuth/DB/Drive calls.

This helper intentionally creates NO permanent installation or rclone config.
Requires Linux amd64 and verifies an exact GitHub release asset SHA-256 before
opening an archive or executing its binary. Outputs a scrubbed JSON certificate.
"""
from __future__ import annotations
from contextlib import contextmanager
import hashlib
import io
import json
import os
import platform
import stat
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

VERSION = 'v1.76.0'
ARCHIVE_NAME = 'rclone-v1.76.0-linux-amd64.zip'
ARCHIVE_URL = 'https://github.com/rclone/rclone/releases/download/' + VERSION + '/' + ARCHIVE_NAME
ARCHIVE_SHA256 = 'b00f00b3266c3764413afe599d3ec316f6f43b3e0ea8a0bc1d186d2133e46df7'
ARCHIVE_BYTES = 32194302
MAX_ARCHIVE_BYTES = 33 * 1024 * 1024
MAX_BINARY_BYTES = 140 * 1024 * 1024
ZIP_ENTRY = 'rclone-v1.76.0-linux-amd64/rclone'


class AdmissionHold(ValueError):
    pass


def _verify_zip(raw: bytes, expected_sha: str) -> zipfile.ZipFile:
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_ARCHIVE_BYTES:
        raise AdmissionHold('ARCHIVE_BOUND_FAIL')
    if type(expected_sha) is not str or len(expected_sha) != 64:
        raise AdmissionHold('INVALID_DIGEST_PIN')
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise AdmissionHold('RELEASE_SHA256_MISMATCH')
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
        names = z.namelist()
        if len(names) > 32 or ZIP_ENTRY not in names or len(set(names)) != len(names):
            raise AdmissionHold('UNEXPECTED_RELEASE_ZIP_LAYOUT')
        for name in names:
            parts = name.rstrip('/').split('/')
            if (not name.startswith('rclone-v1.76.0-linux-amd64/') or
                '..' in parts or name.startswith('/') or '\\' in name):
                raise AdmissionHold('ZIP_PATH_UNSAFE')
        info = z.getinfo(ZIP_ENTRY)
        mode = (info.external_attr >> 16)
        if info.is_dir() or stat.S_ISLNK(mode) or not 1 <= info.file_size <= MAX_BINARY_BYTES:
            raise AdmissionHold('UNSAFE_BINARY_ENTRY')
        return z
    except (zipfile.BadZipFile, KeyError, OSError) as exc:
        raise AdmissionHold('INVALID_RELEASE_ARCHIVE') from exc


def install_verified_archive(raw: bytes, dest: Path, *, expected_sha: str = ARCHIVE_SHA256) -> Path:
    """Write ONE extracted executable into a pre-existing private temp dir."""
    if not isinstance(dest, Path) or not dest.is_dir() or dest.is_symlink():
        raise AdmissionHold('UNSAFE_TEMP_ROOT')
    mode = dest.stat().st_mode
    if not stat.S_ISDIR(mode) or mode & 0o077:
        raise AdmissionHold('TEMP_ROOT_NOT_PRIVATE')
    binary = dest / 'rclone'
    if binary.exists() or binary.is_symlink():
        raise AdmissionHold('NO_OVERWRITE')
    with _verify_zip(raw, expected_sha) as z:
        with z.open(ZIP_ENTRY) as src:
            fd = os.open(str(binary), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                with os.fdopen(fd, 'wb') as out:
                    amount = 0
                    while True:
                        buf = src.read(1024 * 1024)
                        if not buf:
                            break
                        amount += len(buf)
                        if amount > MAX_BINARY_BYTES:
                            raise AdmissionHold('EXTRACT_LIMIT')
                        out.write(buf)
            except BaseException:
                binary.unlink(missing_ok=True)
                raise
        os.chmod(binary, 0o700)
    return binary


def _download_release() -> bytes:
    req = urllib.request.Request(ARCHIVE_URL, headers={'User-Agent': 'MOJ-Factory-rclone-offline-verify/1'})
    with urllib.request.urlopen(req, timeout=35) as response:
        buf = io.BytesIO()
        while True:
            data = response.read(1024 * 1024)
            if not data:
                break
            if buf.tell() + len(data) > MAX_ARCHIVE_BYTES:
                raise AdmissionHold('OVERSIZE_DOWNLOAD')
            buf.write(data)
        raw = buf.getvalue()
    if len(raw) != ARCHIVE_BYTES:
        raise AdmissionHold('PINNED_RELEASE_SIZE_MISMATCH')
    return raw


def verify_binary_version(path: Path) -> bool:
    try:
        result = subprocess.run([str(path), 'version'], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, check=False, timeout=12)
        return (result.returncode == 0 and
                result.stdout.splitlines()[0].startswith(('rclone ' + VERSION).encode()))
    except (OSError, IndexError, subprocess.TimeoutExpired):
        return False


@contextmanager
def provision_verified_rclone(runner_temp: Path, *, downloader=None):
    """Yield a verified executable for a single owner-authorized operation.

    Does not create Drive remotes, read OAuth, or connect to a DB. Any client
    should pass the yielded absolute path as `rclone_exe` to RcloneDualStore.
    Files disappear when the context exits, including on an exception.
    """
    if sys.platform != 'linux' or platform.machine().lower() not in ('x86_64', 'amd64'):
        raise AdmissionHold('UNSUPPORTED_PLATFORM')
    if not isinstance(runner_temp, Path) or not runner_temp.is_dir() or runner_temp.is_symlink():
        raise AdmissionHold('INVALID_RUNNER_TEMP')
    # Avoid filling a nearly-full runner; this guard does not attest cloud quota.
    import shutil
    if shutil.disk_usage(str(runner_temp)).free < 320 * 1024 * 1024:
        raise AdmissionHold('INSUFFICIENT_RUNNER_TEMP_FREE_BYTES')
    raw = _download_release() if downloader is None else downloader()
    if type(raw) is not bytes or len(raw) < 1:
        raise AdmissionHold('MISSING_PINNED_ARCHIVE')
    if downloader is None and len(raw) != ARCHIVE_BYTES:
        raise AdmissionHold('PINNED_RELEASE_SIZE_MISMATCH')
    with tempfile.TemporaryDirectory(prefix='owner-rclone-verified-', dir=str(runner_temp)) as dirname:
        binary = install_verified_archive(raw, Path(dirname))
        if not verify_binary_version(binary):
            raise AdmissionHold('RCLONE_VERSION_MISMATCH')
        yield binary


def main() -> int:
    out = {'schema': 'factory.rclone.ephemeral-signed-digest-readonly.v1',
           'release': VERSION, 'artifact_sha256_verified': False,
           'ephemeral_binary_version_verified': False,
           'no_system_install': True, 'oauth_tokens_read': False,
           'cloud_provider_queried': False, 'production_modified': False,
           'new_backup_created': False, 'failure': 'UNKNOWN'}
    try:
        if sys.platform != 'linux' or platform.machine().lower() not in ('x86_64', 'amd64'):
            raise AdmissionHold('UNSUPPORTED_PLATFORM')
        base = os.environ.get('RUNNER_TEMP', '')
        if not base:
            raise AdmissionHold('NO_RUNNER_TEMP')
        parent = Path(base)
        if not parent.is_dir() or parent.is_symlink():
            raise AdmissionHold('INVALID_RUNNER_TEMP')
        with provision_verified_rclone(parent) as binary:
            out['artifact_sha256_verified'] = True
            out['ephemeral_binary_version_verified'] = True
        out['failure'] = None
        code = 0
    except (AdmissionHold, urllib.error.URLError, OSError, ValueError) as exc:
        out['failure'] = str(exc) if type(exc) is AdmissionHold else 'DOWNLOAD_OR_RUNTIME_FAILURE'
        code = 2
    print(json.dumps(out, sort_keys=True, separators=(',', ':')))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
