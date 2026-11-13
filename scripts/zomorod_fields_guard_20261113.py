#!/usr/bin/env python3
"""Pinned, reversible, three-file-only Zomorod photo carousel release gate.

Read-only by default. Never creates a release merely because the source branch merges.
A production change additionally requires an explicit --owner-approved operator flag.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import pwd
import re
import stat
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

ROOT = Path('/home/zomorod2/public_html')
BACKUP_ROOT = Path('/home/zomorod2/.backups/zomorod-fields-20261113')
FILES = ('index.html', 'assets/zm-reference-v3.css', 'assets/zm-reference-v3.js')
# Exact Git blobs of the successfully verified #2251 live-release source.
OLD_BLOBS = dict(zip(FILES, (
    'afd94198a01194ee7b31be941bb305f775cacacf',
    '61c94300dd81bbddbe3b87962aec971dba05f047',
    '29d4ba1e2e3d550271d6d61614db726b024eeea3',
)))
# Exact Git blobs from PR #2254 after its 4th carousel browser tests passed.
NEW_BLOBS = dict(zip(FILES, (
    'e0ab2643847f9a49f0a5a2ca15e66bb1e892bb5c',
    '63559875709de300ffabbd148bfa76c22e88abfc',
    'b5f99cf18ad8b74a2854a837bcd252bf98a1a30e',
)))
PROTECTED = (
    '.htaccess', 'sitemap.xml', 'agriculture/index.html',
    'research/index.html', 'industry/index.html', 'services/index.html',
    'company/index.html', 'contact/index.html', 'games/index.html',
    'apps/index.html', 'auctions/index.html',
    'site-heritage/home-before-nexus-20261112/index.html',
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def read_regular(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f'Missing or symlinked file: {path}')
    return path.read_bytes()


def identity() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('Refuse non-cPanel user')
    if ROOT.is_symlink() or not ROOT.is_dir() or ROOT != Path('/home/zomorod2/public_html'):
        raise RuntimeError('Untrusted public_html root')
    if (ROOT / 'assets').is_symlink() or not (ROOT / 'assets').is_dir():
        raise RuntimeError('Untrusted assets directory')


def safe_stage(stage: Path) -> Path:
    if not stage.is_absolute() or stage.is_symlink() or not stage.is_dir():
        raise RuntimeError('Stage must be a real absolute private directory')
    if stage == ROOT or ROOT in stage.parents:
        raise RuntimeError('Stage cannot be inside public_html')
    for name in ('old', 'new'):
        folder = stage / name
        if folder.is_symlink() or not folder.is_dir():
            raise RuntimeError('Missing private stage subfolder: ' + name)
        actual = {str(p.relative_to(folder)) for p in folder.rglob('*') if p.is_file() or p.is_symlink()}
        if actual != set(FILES):
            raise RuntimeError(f'Unexpected staged files in {name}: {actual ^ set(FILES)}')
    return stage


def candidates(stage: Path):
    safe_stage(stage)
    old = {name: read_regular(stage / 'old' / name) for name in FILES}
    new = {name: read_regular(stage / 'new' / name) for name in FILES}
    for name in FILES:
        if git_blob(old[name]) != OLD_BLOBS[name]:
            raise RuntimeError('Old source does not match approved revision: ' + name)
        if git_blob(new[name]) != NEW_BLOBS[name]:
            raise RuntimeError('Candidate not approved and browser-tested: ' + name)
        if old[name] == new[name]:
            raise RuntimeError('No actual change: ' + name)
    page = new['index.html']
    js = new['assets/zm-reference-v3.js']
    if not (page.count(b'data-auto-strip=') == 3 and
            page.count(b'data-field-carousel=') == 1 and
            page.count(b'data-rotator-toggle=') == 4 and
            b'zm-reference-v3.js?v=20261113-fields1' in page and
            b'zm-reference-v3.css?v=20261113-fields1' in page and
            b'const strips=Array.from(document.querySelectorAll(' in js and
            b'prefers-reduced-motion' in js):
        raise RuntimeError('Candidate lacks verified four-carousel behavior')
    return old, new


def protected_fingerprints():
    # Legacy sites may not have all optional subsite files. Preserve EVERY existing one.
    result = {}
    for name in PROTECTED:
        path = ROOT / name
        if path.exists() or path.is_symlink():
            result[name] = sha256(read_regular(path))
    if len(result) < 9:
        raise RuntimeError('Too few protected existing files')
    return result


def preflight(stage: Path):
    identity()
    old, new = candidates(stage)
    before = {}
    for name in FILES:
        path = ROOT / name
        actual = read_regular(path)
        if sha256(actual) != sha256(old[name]):
            raise RuntimeError('Live source differs from last pinned release: ' + name)
        before[name] = {'old': sha256(actual), 'new': sha256(new[name]),
                        'mode': stat.S_IMODE(path.stat().st_mode)}
    if BACKUP_ROOT.is_symlink():
        raise RuntimeError('Untrusted backup directory')
    return {'files': before, 'protected': protected_fingerprints()}


def atomic(path: Path, data: bytes, mode: int):
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.zm-fields-', delete=False) as stream:
            temp = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
        directory = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()


def release_dir(release_id: str) -> Path:
    if not re.fullmatch(r'fields-[0-9]{7,22}', release_id):
        raise RuntimeError('Invalid release identifier')
    return BACKUP_ROOT / release_id


@contextmanager
def exclusive():
    if BACKUP_ROOT.is_symlink() or not BACKUP_ROOT.parent.is_dir():
        raise RuntimeError('Untrusted backup parent')
    lock_file = BACKUP_ROOT.parent / '.zomorod-fields-release.lock'
    if lock_file.is_symlink():
        raise RuntimeError('Untrusted release lock')
    with open(lock_file, 'a+b') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def backup(release: Path, before, old):
    release.mkdir(mode=0o700)
    for name in FILES:
        target = release / 'old' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic(target, old[name], 0o600)
        if sha256(read_regular(target)) != before['files'][name]['old']:
            raise RuntimeError('Backup read-back failed: ' + name)
    atomic(release / 'manifest.json', json.dumps(before, sort_keys=True).encode(), 0o600)


def load_backup(release: Path):
    if release.is_symlink() or not release.is_dir():
        raise RuntimeError('Missing private release backup')
    manifest = json.loads(read_regular(release / 'manifest.json'))
    if set(manifest['files']) != set(FILES):
        raise RuntimeError('Unsafe release manifest')
    old = {name: read_regular(release / 'old' / name) for name in FILES}
    for name in FILES:
        if sha256(old[name]) != manifest['files'][name]['old']:
            raise RuntimeError('Corrupted release backup: ' + name)
    return manifest, old


def verify(release_id: str) -> None:
    identity()
    manifest, _ = load_backup(release_dir(release_id))
    if protected_fingerprints() != manifest['protected']:
        raise RuntimeError('Internal content changed during release')
    for name in FILES:
        if sha256(read_regular(ROOT / name)) != manifest['files'][name]['new']:
            raise RuntimeError('Published file does not match approved candidate: ' + name)
    print('ZM_FIELDS_RELEASE=VERIFIED; REPLACED_FILES=3; INTERNAL_FILES_UNTOUCHED=YES')


def restore(release_id: str) -> None:
    manifest, old = load_backup(release_dir(release_id))
    if protected_fingerprints() != manifest['protected']:
        raise RuntimeError('Protected content mismatch; refuse automated restore')
    # Verify all files BEFORE touching any file. Concurrent human edits are never clobbered.
    for name in FILES:
        if sha256(read_regular(ROOT / name)) not in (
                manifest['files'][name]['new'], manifest['files'][name]['old']):
            raise RuntimeError('Concurrent edit detected; refuse restore: ' + name)
    for name in FILES:
        if sha256(read_regular(ROOT / name)) == manifest['files'][name]['new']:
            atomic(ROOT / name, old[name], manifest['files'][name]['mode'])
    for name in FILES:
        if sha256(read_regular(ROOT / name)) != manifest['files'][name]['old']:
            raise RuntimeError('Post-rollback mismatch: ' + name)
    print('ZM_FIELDS_RELEASE=ROLLED_BACK_EXACTLY')


def apply(stage: Path, release_id: str) -> None:
    with exclusive():
        manifest = preflight(stage)
        old, new = candidates(stage)
        release = release_dir(release_id)
        if release.exists() or release.is_symlink():
            raise RuntimeError('Release identifier already used')
        if BACKUP_ROOT.is_symlink():
            raise RuntimeError('Untrusted backup root')
        BACKUP_ROOT.mkdir(mode=0o700, exist_ok=True)
        backup(release, manifest, old)
        # Atomic per-file writes; HTML last so old page keeps using old versioned assets.
        try:
            for name in ('assets/zm-reference-v3.js', 'assets/zm-reference-v3.css', 'index.html'):
                if sha256(read_regular(ROOT / name)) != manifest['files'][name]['old']:
                    raise RuntimeError('Changed since audit: ' + name)
                atomic(ROOT / name, new[name], manifest['files'][name]['mode'])
            verify(release_id)
        except BaseException:
            restore(release_id)
            raise
        print('ZM_FIELDS_RELEASE=APPLIED_AFTER_EXPLICIT_APPROVAL')


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) == 2 and args[0] == 'check':
        result = preflight(Path(args[1]))
        print(json.dumps(result, sort_keys=True))
    elif len(args) == 4 and args[0] == 'apply' and args[3] == '--owner-approved':
        apply(Path(args[1]), args[2])
    elif len(args) == 3 and args[0] == 'rollback' and args[2] == '--owner-approved':
        identity()
        with exclusive():
            restore(args[1])
    elif len(args) == 2 and args[0] == 'verify':
        verify(args[1])
    else:
        raise SystemExit('Read-only: check STAGE | verify RELEASE; owner-only: apply STAGE RELEASE --owner-approved | rollback RELEASE --owner-approved')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
