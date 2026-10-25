#!/usr/bin/env python3
"""Restore exactly two missing MojPlayWin CSS files with sealed rollback.

No changes to payment code, templates, routing, accounts, database or wallets.
The shared homepage CSS is reconstructed from the site's own original HTML,
using the same extraction rule as the previously reviewed unification release.
"""
from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import stat
import sys
import tempfile
from pathlib import Path

OWNER = 'zomorod2'
ROOT = Path('/home/zomorod2/mojplaywin.com')
STAGING = Path('/home/zomorod2/Saeit-staging')
BACKUPS = Path('/home/zomorod2/.private_mojplaywin_main_agents')
ORIGINAL_HOME = ROOT / 'design-preview-20261017/production-home-20261017.html'
ASSET_DIR = ROOT / 'mpw-editorial/revenue/assets'
PUBLIC_PARENTS = (ROOT / 'mpw-editorial', ROOT / 'mpw-editorial/revenue', ASSET_DIR)
ASSET_HOME = ASSET_DIR / 'home-shared-v1.css'
ASSET_FINTECH = ASSET_DIR / 'mpw-fintech-checkout-v2.css'
FINTECH_SHA = '2eaa44985afddd5b840f60d0f1c04a48ab76126f632e167e255592b86847ed47'
RUN_RE = re.compile(r'[0-9]{8,20}')
CSS_ANCHORS = ('main .panel', 'main #invoice', 'main #downloads',
               'main .mpwf-intro', 'main #start', '@media (max-width: 640px)')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fail(reason: str) -> None:
    raise RuntimeError(reason)


def locations(run: str) -> tuple[Path, Path]:
    if not RUN_RE.fullmatch(run):
        fail('Invalid run identifier')
    return (BACKUPS / ('mpw-two-css-'+run),
            BACKUPS / ('mpw-two-css-'+run+'.fintech.staged.css'))


def guard() -> None:
    if pwd.getpwuid(os.getuid()).pw_name != OWNER:
        fail('Wrong cPanel identity')
    for directory in (ROOT, STAGING, BACKUPS):
        if not directory.is_dir() or directory.is_symlink():
            fail('Missing/unsafe expected directory')
    for directory in PUBLIC_PARENTS:
        if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
            fail('Unsafe static asset parent path')
    if stat.S_IMODE(BACKUPS.stat().st_mode) & 0o077:
        fail('Private backup directory permissions are too broad')
    if not (ROOT / '.htaccess').is_file():
        fail('Webroot has no expected routing configuration')
    wsgi = ROOT / 'passenger_wsgi.py'
    if not wsgi.is_file() or wsgi.is_symlink():
        fail('Wrong Passenger webroot')
    if "APP='/home/zomorod2/Saeit-staging'" not in wsgi.read_text('utf8', 'replace'):
        fail('Wrong public application identity')
    if not ORIGINAL_HOME.is_file() or ORIGINAL_HOME.is_symlink():
        fail('Original homepage is missing')
    for candidate in (ASSET_HOME, ASSET_FINTECH):
        if candidate.is_symlink():
            fail('An asset target is a symlink')


def generated_home_css() -> bytes:
    original = ORIGINAL_HOME.read_text('utf8')
    chunks = re.findall(r'<style\b[^>]*>([\s\S]*?)</style\s*>', original, re.I)
    contents = '\n\n'.join(chunks)
    if len(contents) < 1500 or 'mw-site-nav' not in original or 'mw-site-footer' not in original:
        fail('Unexpected homepage styling source')
    contents = ('/* Exact native CSS extracted from current MojPlayWin homepage; '
                'all other main pages share this source */\n' + contents + '\n' +
                'body{background:#090b0c;color:#f4eedc}body .mw-site-nav{z-index:40}' +
                'body .mw-site-footer{color:#f1e7ce}body .mw-nav-panel{background:#11191d}' +
                '@media(max-width:740px){body .mw-site-nav{padding:10px 14px}' +
                'body .mw-nav-panel{max-width:92vw}}')
    css = contents.encode('utf8')
    if len(css) > 400000:
        fail('Unexpected homepage CSS size')
    return css


def staged_fintech(path: Path) -> bytes:
    if not path.is_file() or path.is_symlink():
        fail('Missing private staged fintech CSS')
    data = path.read_bytes()
    if len(data) < 4000 or len(data) > 20000 or sha(data) != FINTECH_SHA:
        fail('Fintech CSS differs from source-controlled reviewed artifact')
    text = data.decode('utf8')
    if not all(anchor in text for anchor in CSS_ANCHORS):
        fail('Unexpected fintech CSS selectors')
    if '@import' in text.lower() or 'javascript:' in text.lower():
        fail('Unexpected active CSS payload')
    return data


def preflight(run: str) -> tuple[bytes, bytes]:
    guard()
    folder, stage = locations(run)
    if folder.exists() or folder.is_symlink():
        fail('A previous backup with this run id already exists')
    for target in (ASSET_HOME, ASSET_FINTECH):
        if target.exists() or target.is_symlink():
            fail('Expected missing CSS now exists; refuse overwrite')
    home, fintech = generated_home_css(), staged_fintech(stage)
    return home, fintech


def atomic_new(path: Path, payload: bytes) -> None:
    if path.exists() or path.is_symlink():
        fail('Concurrent CSS asset appeared')
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.mpw-css-repair-')
    try:
        os.fchmod(fd, 0o644)
        with os.fdopen(fd, 'wb') as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        if path.exists() or path.is_symlink():
            fail('Concurrent asset creation detected')
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def preview(run: str) -> None:
    home, fintech = preflight(run)
    print('MPW_CSS_PREFLIGHT=' + json.dumps({
        'missing_targets_verified': 2, 'home_css_sha': sha(home),
        'fintech_css_sha': sha(fintech), 'staging_only': True,
        'templates_changed': False, 'payment_changed': False}))


def publish(run: str) -> None:
    home, fintech = preflight(run)
    folder, _ = locations(run)
    missing_folders = [p for p in PUBLIC_PARENTS if not p.exists()]
    folder.mkdir(mode=0o700)
    manifest = {'run': run, 'files': {
        'home-shared-v1.css': sha(home),
        'mpw-fintech-checkout-v2.css': sha(fintech)},
        'created_folders': [str(p.relative_to(ROOT)) for p in missing_folders],
        'previous_files': 'absent', 'payment_changed': False}
    file = folder / 'manifest.json'
    with file.open('x', encoding='utf8') as handle:
        os.fchmod(handle.fileno(), 0o600)
        json.dump(manifest, handle, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    written = []
    created = []
    try:
        for directory in missing_folders:
            if directory.exists() or directory.is_symlink():
                fail('Concurrent public directory creation detected')
            directory.mkdir(mode=0o755)
            created.append(directory)
        for path, payload in ((ASSET_HOME, home), (ASSET_FINTECH, fintech)):
            atomic_new(path, payload)
            written.append((path, sha(payload)))
            if sha(path.read_bytes()) != sha(payload):
                fail('Postwrite CSS mismatch')
    except BaseException:
        for path, expected in reversed(written):
            if path.is_file() and not path.is_symlink() and sha(path.read_bytes()) == expected:
                path.unlink()
        for directory in reversed(created):
            if directory.is_dir() and not directory.is_symlink():
                try:directory.rmdir()
                except OSError:pass  # Preserve any concurrent content.
        raise
    print('MPW_CSS_INSTALLED=' + json.dumps({'assets_created': 2,
        'new_empty_parents_created': len(missing_folders),
        'run': run, 'backup_manifest': True, 'payment_changed': False}))


def verify(run: str) -> None:
    guard()
    folder, _ = locations(run)
    if folder.is_symlink() or not folder.is_dir():
        fail('Missing sealed release folder')
    m = json.loads((folder / 'manifest.json').read_text('utf8'))
    if m['run'] != run or m['previous_files'] != 'absent':
        fail('Unexpected CSS release manifest')
    correct = {'home-shared-v1.css': generated_home_css(),
               'mpw-fintech-checkout-v2.css': ASSET_FINTECH.read_bytes()}
    for name, expected in correct.items():
        target = ASSET_DIR / name
        if not target.is_file() or target.is_symlink():
            fail('Expected CSS is missing')
        if sha(target.read_bytes()) != m['files'][name] or sha(expected) != m['files'][name]:
            fail('CSS content drift')
    print('MPW_CSS_VERIFIED=' + json.dumps({'assets_verified': 2,
        'home_sha': m['files']['home-shared-v1.css'],
        'fintech_sha': m['files']['mpw-fintech-checkout-v2.css']}))


def rollback(run: str) -> None:
    guard()
    folder, _ = locations(run)
    if folder.is_symlink() or not folder.is_dir():
        fail('Unknown release folder')
    m = json.loads((folder / 'manifest.json').read_text('utf8'))
    if m['run'] != run or m['previous_files'] != 'absent':
        fail('Incorrect rollback manifest')
    for name, expected in m['files'].items():
        p = ASSET_DIR / name
        if not p.is_file() or p.is_symlink() or sha(p.read_bytes()) != expected:
            fail('Concurrent change blocks safe rollback')
    # Pre-check that directory removal cannot affect any unrelated files.
    all_expected = {ASSET_HOME, ASSET_FINTECH}
    expected_dirs = set()
    for rel in m.get('created_folders', []):
        p = ROOT / rel
        if p not in PUBLIC_PARENTS or not p.is_dir() or p.is_symlink():
            fail('Unexpected rollback directory')
        expected_dirs.add(p)
    for directory in expected_dirs:
        if any(child not in all_expected and child not in expected_dirs for child in directory.iterdir()):
            fail('Other content was added; refuse to remove directory')
    for name in m['files']:
        (ASSET_DIR / name).unlink()
    for directory in reversed(PUBLIC_PARENTS):
        if directory in expected_dirs:
            directory.rmdir()
    print('MPW_CSS_ROLLBACK=PASS')


def selftest() -> None:
    # No host access needed; exercises unsafe identifiers before any write.
    for value in ('../danger', '123-456', ''):
        try:
            locations(value)
        except RuntimeError:
            pass
        else:
            fail('Unsafe run identifier passed')
    if FINTECH_SHA != '2eaa44985afddd5b840f60d0f1c04a48ab76126f632e167e255592b86847ed47':
        fail('Fintech source pin changed')
    print('MPW_CSS_REPAIR_SELFTEST=PASS')


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'selftest':
        selftest()
    elif len(sys.argv) == 3 and sys.argv[1] in ('preview', 'publish', 'verify', 'rollback'):
        {'preview': preview, 'publish': publish,
         'verify': verify, 'rollback': rollback}[sys.argv[1]](sys.argv[2])
    else:
        raise SystemExit('selftest | preview|publish|verify|rollback RUN_ID')
