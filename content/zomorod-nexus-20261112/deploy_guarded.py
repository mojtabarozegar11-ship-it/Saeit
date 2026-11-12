#!/usr/bin/env python3
"""Fail-closed Zomorod Mellal homepage release, isolated to /index.html + one CSS.

Commands:
  python3 deploy_guarded.py check
  python3 deploy_guarded.py apply 20261112-nexus01
  python3 deploy_guarded.py verify 20261112-nexus01
  python3 deploy_guarded.py rollback 20261112-nexus01

This script is intentionally not auto-executing and never modifies internal pages,
.htaccess, sitemap, databases, payments, or server configuration.
"""
from __future__ import annotations
import argparse
import fcntl
import hashlib
import json
import os
import pwd
import re
import shutil
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path

SITE = Path('/home/zomorod2/public_html')
BACKUPS = Path('/home/zomorod2/.backups/zomorod-nexus-20261112')
SRC = Path(__file__).resolve().parent
HOME_SOURCE = SRC / 'index.html'
CSS_SOURCE = SRC / 'assets/zm-nexus-v1.css'
HOME = SITE / 'index.html'
CSS = SITE / 'assets/zm-nexus-v1.css'
ARCHIVE = SITE / 'site-heritage/home-before-nexus-20261112/index.html'
LOCK = BACKUPS.parent / '.zomorod-homepage-deploy.lock'
ROOT_MARKERS = ('ZOMOROD_ORBIT_DATA', 'id="main-view"', 'id="orbital-cards"', 'id="site-footer"')
PROTECTED = (
    'agriculture/index.html', 'research/index.html', 'industry/index.html',
    'company/index.html', 'services/index.html', 'contact/index.html',
    'store/index.php', 'sitemap.xml', '.htaccess',
    'games/index.html', 'apps/index.html', 'auctions/index.html',
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_path(path: Path, require: bool = True):
    if path.is_symlink():
        raise RuntimeError(f'Symlink rejected: {path}')
    if require and not path.is_file():
        raise RuntimeError(f'Required file missing: {path}')


def ensure_identity():
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('Refusing: unexpected cPanel user identity')
    if not SITE.is_dir() or SITE.is_symlink() or BACKUPS.is_symlink():
        raise RuntimeError('Unexpected production filesystem')
    if not BACKUPS.parent.is_dir() or BACKUPS.parent.is_symlink():
        raise RuntimeError('Private backup location unavailable')
    safe_path(HOME)
    safe_path(SRC / 'validate.py')
    for parent in (CSS.parent, ARCHIVE.parent.parent):
        if not parent.is_dir() or parent.is_symlink():
            raise RuntimeError(f'Unexpected asset/archive folder: {parent}')


def read_candidate():
    safe_path(HOME_SOURCE)
    safe_path(CSS_SOURCE)
    html = HOME_SOURCE.read_bytes()
    css = CSS_SOURCE.read_bytes()
    assert b'<body class="nexus-home">' in html
    assert b'<link rel="stylesheet" href="/assets/zm-nexus-v1.css">' in html
    assert b'@media(max-width:640px)' in css
    assert b'prefers-reduced-motion:reduce' in css
    assert b'Vancouver' not in html and 'ونکوور'.encode() not in html
    if not 14000 <= len(html) <= 70000 or not 12000 <= len(css) <= 90000:
        raise RuntimeError('Unexpected candidate size')
    return html, css


def preflight():
    ensure_identity()
    candidate, css = read_candidate()
    original = HOME.read_bytes()
    if len(original) < 40_000 or not all(x.encode() in original for x in ROOT_MARKERS):
        raise RuntimeError('Unknown or changed live homepage; fail closed')
    if b'nexus-home' in original:
        raise RuntimeError('NEXUS already installed; avoid duplicate')
    if ARCHIVE.exists() or ARCHIVE.is_symlink():
        raise RuntimeError('Archive location already occupied; do not overwrite')
    if CSS.exists() or CSS.is_symlink():
        raise RuntimeError('New asset path already exists; do not overwrite')
    # These assets are referenced on existing live pages and must be in the same site.
    for asset in (
        'static/site/zomorod-v7/company-logo.webp',
        'static/site/heroes/smart-agriculture.webp',
        'static/site/heroes/agriculture.webp',
        'static/site/heroes/research.webp',
        'static/site/heroes/industry.webp',
        'static/site/heroes/economy.webp',
        'static/site/heroes/ai.webp',
        'static/site/heroes/services.webp',
        'static/site/heroes/marketplace.webp',
        'static/site/zomorod-ten-editorials/research.webp',
        'agriculture/assets/zomorod-olive-v1/laboratory.webp',
    ):
        safe_path(SITE / asset)
    protected = {}
    for p in PROTECTED:
        f = SITE / p
        if f.is_file():
            safe_path(f)
            protected[p] = sha(f.read_bytes())
    if len(protected) < 5:
        raise RuntimeError('Protected internal pages not sufficiently identified')
    return {
        'original': sha(original), 'candidate': sha(candidate), 'css': sha(css),
        'protected': protected, 'original_size': len(original),
        'candidate_size': len(candidate), 'css_size': len(css)
    }


def atomic(path: Path, data: bytes, mode: int = 0o644):
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.zm-nexus-', delete=False) as h:
            tmp = Path(h.name)
            h.write(data)
            h.flush()
            os.fsync(h.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if tmp and tmp.exists():
            tmp.unlink()


@contextmanager
def locked():
    with open(LOCK, 'a+b') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def release_dir(run: str):
    if not re.fullmatch(r'[a-zA-Z0-9_-]{6,42}', run):
        raise RuntimeError('Invalid release ID')
    return BACKUPS / run


def apply(run: str):
    with locked():
        baseline = preflight()
        folder = release_dir(run)
        if folder.exists() or folder.is_symlink():
            raise RuntimeError('Release folder already exists')
        folder.mkdir(mode=0o700, parents=True)
        before = HOME.read_bytes()
        mode = stat.S_IMODE(HOME.stat().st_mode)
        atomic(folder / 'index.before.html', before, 0o600)
        assert sha((folder / 'index.before.html').read_bytes()) == baseline['original']
        baseline['mode'] = mode
        (folder / 'manifest.json').write_text(json.dumps(baseline, indent=2, ensure_ascii=False), encoding='utf-8')
        if sha(HOME.read_bytes()) != baseline['original']:
            raise RuntimeError('Homepage changed after preflight')
        html, css = read_candidate()
        archive_created = False
        css_created = False
        try:
            ARCHIVE.parent.mkdir(mode=0o755, parents=True, exist_ok=False)
            atomic(ARCHIVE, before, 0o644)
            archive_created = True
            atomic(CSS, css, 0o644)
            css_created = True
            atomic(HOME, html, mode)
            verify(run, locked_already=True)
        except BaseException:
            if sha(HOME.read_bytes()) == baseline['candidate']:
                atomic(HOME, before, mode)
            if css_created and CSS.is_file() and sha(CSS.read_bytes()) == baseline['css']:
                CSS.unlink()
            if archive_created and ARCHIVE.is_file() and sha(ARCHIVE.read_bytes()) == baseline['original']:
                ARCHIVE.unlink()
                ARCHIVE.parent.rmdir()
            raise
    print('NEXUS_HOMEPAGE_APPLIED=YES')


def verify(run: str, locked_already: bool = False):
    ensure_identity()
    folder = release_dir(run)
    manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    assert sha((folder / 'index.before.html').read_bytes()) == manifest['original']
    assert sha(HOME.read_bytes()) == manifest['candidate']
    assert sha(CSS.read_bytes()) == manifest['css']
    assert sha(ARCHIVE.read_bytes()) == manifest['original']
    for rel, expected in manifest['protected'].items():
        if sha((SITE / rel).read_bytes()) != expected:
            raise RuntimeError('Protected route changed: ' + rel)
    print('NEXUS_PROTECTED_INNER_PAGES=UNCHANGED')
    print('NEXUS_ROOT_AND_CSS=CHECKSUM_VERIFIED')


def rollback(run: str):
    with locked():
        ensure_identity()
        manifest = json.loads((release_dir(run) / 'manifest.json').read_text(encoding='utf-8'))
        original = (release_dir(run) / 'index.before.html').read_bytes()
        assert sha(original) == manifest['original']
        current = sha(HOME.read_bytes())
        if current != manifest['candidate']:
            if current == manifest['original']:
                print('NEXUS_ALREADY_ROLLED_BACK=YES')
                return
            raise RuntimeError('Concurrent homepage modification; rollback refused')
        atomic(HOME, original, manifest['mode'])
        if CSS.is_file() and sha(CSS.read_bytes()) == manifest['css']:
            CSS.unlink()
        # Preserve the archive and private backup as forensic records.
        for rel, expected in manifest['protected'].items():
            assert sha((SITE / rel).read_bytes()) == expected
        print('NEXUS_ROLLBACK=RESTORED_ORIGINAL')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['check', 'apply', 'verify', 'rollback'])
    parser.add_argument('run', nargs='?')
    args = parser.parse_args()
    if args.mode == 'check':
        print(json.dumps(preflight(), ensure_ascii=False, indent=2))
    else:
        if not args.run:
            parser.error('Release ID required')
        {'apply': apply, 'verify': verify, 'rollback': rollback}[args.mode](args.run)

if __name__ == '__main__':
    main()
