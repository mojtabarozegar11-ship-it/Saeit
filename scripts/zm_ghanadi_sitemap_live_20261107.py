#!/usr/bin/env python3
"""Guarded, reversible discovery of two already-live pastry pages in root sitemap."""

import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree as ET

HOME = Path('/home/zomorod2')
ROOT = HOME / 'public_html'
SITEMAP = ROOT / 'sitemap.xml'
LOCK = HOME / '.locks/zm-ghanadi-sitemap-20261107.lock'
BACKUP = HOME / '.backups/zm-ghanadi-sitemap-20261107'
PAGES = ('ghanadi/', 'ghanadi/cafe-shiraz/')
URLS = tuple('https://zomorodmelal.ir/' + page for page in PAGES)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked_file(path):
    if not ROOT.is_dir() or ROOT.is_symlink():
        raise RuntimeError('UNSAFE_DOMAIN_ROOT')
    if not path.is_relative_to(ROOT):
        raise RuntimeError('PATH_OUTSIDE_DOMAIN_ROOT')
    current = path
    while current != ROOT:
        if current.is_symlink():
            raise RuntimeError('SYMLINK_PATH')
        current = current.parent
    if not path.is_file() or path.stat().st_size > 2_000_000:
        raise RuntimeError('FILE_MISSING_OR_TOO_LARGE')
    return path


def atomic_replace(path, data):
    fd, temp = tempfile.mkstemp(prefix='.zm-ghanadi-seo-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, path.stat().st_mode & 0o777)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def locations(data):
    root = ET.fromstring(data)
    if not root.tag.endswith('urlset'):
        raise RuntimeError('UNEXPECTED_SITEMAP_ROOT')
    locs = [element.text for element in root.iter() if element.tag.endswith('loc')]
    if len(locs) != len(set(locs)):
        raise RuntimeError('PREEXISTING_DUPLICATE_LOC')
    return locs


def apply(run):
    for page in PAGES:
        checked_file(ROOT / page / 'index.html')
    checked_file(SITEMAP)
    before = SITEMAP.read_bytes()
    locs = locations(before)
    missing = [url for url in URLS if url not in locs]
    if not missing:
        print('GHANADI_ROOT_SITEMAP_ALREADY_CORRECT')
        return
    body = before.decode('utf-8')
    if body.count('</urlset>') != 1:
        raise RuntimeError('UNEXPECTED_SITEMAP_END')
    addition = ''.join('  <url><loc>' + url + '</loc></url>\n' for url in missing)
    after = body.replace('</urlset>', addition + '</urlset>', 1).encode('utf-8')
    next_locs = locations(after)
    if len(next_locs) != len(locs) + len(missing) or any(next_locs.count(url) != 1 for url in URLS):
        raise RuntimeError('SITEMAP_POSTPATCH_INVALID')
    backup = BACKUP / run
    if backup.exists():
        raise RuntimeError('RUN_BACKUP_ALREADY_EXISTS')
    backup.mkdir(mode=0o700, parents=True)
    (backup / 'sitemap.before').write_bytes(before)
    (backup / 'manifest.json').write_text(json.dumps({
        'before': digest(before), 'after': digest(after), 'added': missing,
    }), encoding='utf-8')
    if SITEMAP.read_bytes() != before:
        raise RuntimeError('CONCURRENT_SITEMAP_UPDATE')
    atomic_replace(SITEMAP, after)
    print('GHANADI_ROOT_SITEMAP_ADDED', len(missing))
    for url in URLS:
        print('GHANADI_CANONICAL_IN_SITEMAP', url)


def rollback(run):
    checked_file(SITEMAP)
    backup = BACKUP / run
    if not backup.exists():
        print('NO_GHANADI_SITEMAP_PATCH_TO_ROLL_BACK')
        return
    manifest = json.loads((backup / 'manifest.json').read_text(encoding='utf-8'))
    before = (backup / 'sitemap.before').read_bytes()
    if digest(before) != manifest['before']:
        raise RuntimeError('BACKUP_HASH_MISMATCH')
    now = SITEMAP.read_bytes()
    if digest(now) == manifest['before']:
        print('SITEMAP_ALREADY_RESTORED')
        return
    if digest(now) != manifest['after']:
        raise RuntimeError('ROLLBACK_REFUSED_CONCURRENT_CHANGES')
    atomic_replace(SITEMAP, before)
    print('GHANADI_SITEMAP_ROLLED_BACK')


def main():
    if len(sys.argv) != 3 or sys.argv[1] not in ('apply', 'rollback') or not re.fullmatch(r'[0-9]{6,20}', sys.argv[2]):
        raise SystemExit('usage: apply|rollback numeric_run_id')
    LOCK.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    BACKUP.mkdir(mode=0o700, parents=True, exist_ok=True)
    with LOCK.open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        (apply if sys.argv[1] == 'apply' else rollback)(sys.argv[2])


if __name__ == '__main__':
    main()
