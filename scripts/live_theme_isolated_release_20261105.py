#!/usr/bin/env python3
"""SHA-pinned, reversible production UI-only changes for both live sites.

Run on the authenticated zomorod2 cPanel account. No database, order, wallet,
gateway, credentials, or application controller is modified.
"""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path


HOME = Path('/home/zomorod2')
MPW = HOME / 'Saeit-staging/core/templates/mojplaywin/store.html'
ZM_STORE = HOME / 'public_html/store/index.php'
ZM_BUSINESS = HOME / '.private/zomorod-business/app.php'
WSGI = HOME / 'mojplaywin.com/passenger_wsgi.py'
RESTART = HOME / 'mojplaywin.com/tmp/restart.txt'
BACKUP_BASE = HOME / '.private/theme-ui-backups'
MARKER = 'live-theme-fix-20261105'
EXPECTED = {
    'mpw_store': (MPW, '315acaae6131ef6827aac16ae62844bb1f45a76e792e62715dd12cf77093ac83'),
    'zm_store': (ZM_STORE, 'f00716fd5878088185ec04d297f6e681488d69224c7708144327a8615700aff7'),
    'zm_business': (ZM_BUSINESS, '5ca1cd896da862196dfb3bcf9bba42a06bdb59b8e70d8c1eca71d8329a3b8e87'),
}

MPW_CSS = '''
/* live-theme-fix-20261105: source-preserving storefront viewport improvements */
.mpw-shop-hero{gap:clamp(18px,3vw,38px);padding:clamp(22px,3vw,42px)}
.mpw-shop-hero h1{font-size:clamp(2.15rem,4.25vw,3.75rem);line-height:1.07;margin:12px 0 14px}
.mpw-shop-art-image{height:clamp(160px,17vw,210px)}
.mpw-shop-catalog{padding-top:clamp(28px,4vw,52px)}
.mpw-product-bottom{flex-wrap:wrap}
@media(max-width:650px){.mpw-shop-hero{padding:22px 18px}.mpw-shop-art{grid-row:auto}.mpw-shop-art-image{height:145px}.mpw-shop-hero h1{font-size:clamp(2.15rem,10vw,3.2rem)}.mpw-shop-primary{margin-top:18px}.mpw-shop-catalog{padding-top:28px}}
'''

ZM_CSS = '''
/* live-theme-fix-20261105: responsive navigation, focus and contrast */
.zm-theme-nav{display:flex;flex-wrap:wrap;gap:7px;align-items:center;justify-content:center;margin-top:12px}
.zm-theme-nav a{color:#f9eac8;text-decoration:none;padding:9px 12px;border:1px solid #d5bd75;border-radius:9px;display:inline-flex;align-items:center;min-height:40px;font-weight:700}
.zm-theme-nav a[aria-current=page]{color:#1a2b1c;background:#efd58e}
.zm-theme-nav a:focus-visible{outline:3px solid #fff;outline-offset:3px}
@media(max-width:650px){.zm-theme-nav{justify-content:flex-start;flex-wrap:nowrap;overflow-x:auto;padding-bottom:8px}.zm-theme-nav a{white-space:nowrap;flex:none}}
'''

ZM_NAV = ('<nav class="zm-theme-nav" aria-label="ناوبری اصلی زمرد ملل">'
          '<a href="/">خانه</a><a href="/agriculture/">کشاورزی</a>'
          '<a href="/research/">پژوهش‌ها</a><a href="/industry/">صنعت</a>'
          '<a href="/store/" aria-current="page">فروشگاه</a>'
          '<a href="/contact/">ارتباط</a></nav>')


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replace_exact(text: str, old: str, new: str, count: int = 1) -> str:
    observed = text.count(old)
    if observed != count:
        raise RuntimeError(f'UI_ANCHOR_MISMATCH expected={count} found={observed} anchor={old[:24]!r}')
    return text.replace(old, new)


def patch_mpw(data: bytes) -> bytes:
    text = data.decode('utf-8')
    if MARKER in text:
        raise RuntimeError('MPW_ALREADY_PATCHED')
    if ('/commerce/book/72/' not in text or '/commerce/book/225/' not in text
            or 'id="mpw-products"' not in text):
        raise RuntimeError('MPW_GUEST_CHECKOUT_OR_CATALOG_CHANGED')
    return replace_exact(text, '</style>', MPW_CSS + '</style>').encode('utf-8')


def patch_zm_store(data: bytes) -> bytes:
    text = data.decode('utf-8')
    if MARKER in text or '<nav' in text.lower():
        raise RuntimeError('ZM_NAV_ALREADY_PRESENT_OR_PATCHED')
    if ('zm-store-inquiry' not in text or '/ask-master/index.php' not in text
            or 'پرداخت آنلاین تا اتصال درگاه غیرفعال است' not in text):
        raise RuntimeError('ZM_STORE_LIVE_FEATURES_CHANGED')
    # Live PHP contains more than one CSS block. Only touch the first in <head>.
    head_end = text.lower().find('</head>')
    style_end = text.lower().find('</style>')
    if head_end < 0 or style_end < 0 or style_end >= head_end:
        raise RuntimeError('ZM_HEAD_STYLE_ANCHOR_CHANGED')
    text = text[:style_end] + ZM_CSS + text[style_end:]
    return replace_exact(text, '</header>', ZM_NAV + '</header>').encode('utf-8')


def patch_zm_business(data: bytes) -> bytes:
    text = data.decode('utf-8')
    if MARKER in text or 'for="business-login-password"' in text:
        raise RuntimeError('ZM_MANAGEMENT_LABELS_ALREADY_UPDATED')
    changes = (
        ('<label>نام کاربری</label><input name="username"',
         '<label for="business-login-username">نام کاربری</label><input id="business-login-username" name="username"'),
        ('<label>رمز عبور</label><input name="password"',
         '<label for="business-login-password">رمز عبور</label><input id="business-login-password" name="password"'),
    )
    for old, new in changes:
        text = replace_exact(text, old, new)
    # The management application is large and live-only; preserve all its other modules.
    return text.encode('utf-8')


PATCHES = {
    'mpw_store': patch_mpw,
    'zm_store': patch_zm_store,
    'zm_business': patch_zm_business,
}


def guard() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('UNEXPECTED_DEPLOY_USER')
    if not HOME.is_dir() or HOME.is_symlink() or not WSGI.is_file():
        raise RuntimeError('VERIFIED_HOST_PATH_MISSING')
    if "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text('utf-8', 'replace'):
        raise RuntimeError('PASSENGER_TARGET_CHANGED')
    for label, (path, sha) in EXPECTED.items():
        if path.is_symlink() or not path.is_file() or path.parent.is_symlink():
            raise RuntimeError('UNSAFE_LIVE_PATH:' + label)
        if digest(path.read_bytes()) != sha:
            raise RuntimeError('LIVE_SHA_CHANGED:' + label)


def planned() -> dict[str, tuple[bytes, bytes]]:
    guard()
    result = {}
    for label, (path, _) in EXPECTED.items():
        previous = path.read_bytes()
        updated = PATCHES[label](previous)
        if previous == updated or MARKER in previous.decode('utf-8', 'replace'):
            raise RuntimeError('NO_UI_CHANGE:' + label)
        result[label] = previous, updated
    return result


def lint_php(data: bytes, parent: Path) -> None:
    php = shutil.which('php')
    if not php:
        raise RuntimeError('PHP_CLI_UNAVAILABLE_FAIL_CLOSED')
    fd, tmp = tempfile.mkstemp(prefix='.theme-lint-', suffix='.php', dir=parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
        check = subprocess.run([php, '-l', tmp], capture_output=True, text=True, timeout=15)
        if check.returncode != 0:
            raise RuntimeError('PHP_LINT_FAILED:' + check.stderr[:180])
    finally:
        Path(tmp).unlink(missing_ok=True)


def atomic_write(path: Path, data: bytes, mode: int) -> None:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('LIVE_PATH_CHANGED_DURING_WRITE')
    fd, tmp = tempfile.mkstemp(prefix='.theme-release-', dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def backup_dir(run: str) -> Path:
    if not re.fullmatch(r'[0-9]{9,20}', run):
        raise RuntimeError('INVALID_RUN_ID')
    return BACKUP_BASE / ('run-' + run)


def touch_restart() -> None:
    if not RESTART.parent.is_dir() or RESTART.parent.is_symlink():
        raise RuntimeError('PASSENGER_RESTART_DIRECTORY_UNAVAILABLE')
    if RESTART.is_symlink():
        raise RuntimeError('UNSAFE_RESTART_MARKER')
    RESTART.touch(exist_ok=True)


def preview() -> None:
    changes = planned()
    for label in ('zm_store', 'zm_business'):
        lint_php(changes[label][1], EXPECTED[label][0].parent)
    print('THEME_PREVIEW=' + json.dumps({
        label: {'original_sha256': digest(old), 'patched_sha256': digest(new),
                'added_bytes': len(new) - len(old)}
        for label, (old, new) in changes.items()
    }, sort_keys=True))


def publish(run: str) -> None:
    changes = planned()
    for label in ('zm_store', 'zm_business'):
        lint_php(changes[label][1], EXPECTED[label][0].parent)
    if not RESTART.parent.is_dir() or RESTART.is_symlink():
        raise RuntimeError('PASSENGER_RESTART_UNAVAILABLE')

    root = backup_dir(run)
    if root.exists() or root.is_symlink():
        raise RuntimeError('BACKUP_COLLISION')
    BACKUP_BASE.mkdir(mode=0o700, exist_ok=True)
    root.mkdir(mode=0o700)
    manifest = {}
    for label, (old, new) in changes.items():
        path, _ = EXPECTED[label]
        out = root / (label + '.original')
        with out.open('xb') as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(old)
            stream.flush()
            os.fsync(stream.fileno())
        manifest[label] = {'old_sha256': digest(old), 'new_sha256': digest(new),
                           'mode': stat.S_IMODE(path.stat().st_mode)}
    (root / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True))
    (root / 'manifest.json').chmod(0o600)

    written = []
    try:
        for label, (old, new) in changes.items():
            path, sha = EXPECTED[label]
            if digest(path.read_bytes()) != sha:
                raise RuntimeError('CONCURRENT_FILE_CHANGE:' + label)
            atomic_write(path, new, manifest[label]['mode'])
            written.append(label)
            if digest(path.read_bytes()) != digest(new):
                raise RuntimeError('POSTWRITE_HASH_MISMATCH:' + label)
        touch_restart()
    except BaseException:
        for label in reversed(written):
            path, _ = EXPECTED[label]
            if digest(path.read_bytes()) == manifest[label]['new_sha256']:
                atomic_write(path, changes[label][0], manifest[label]['mode'])
        if 'mpw_store' in written:
            touch_restart()
        raise
    print('THEME_PUBLISHED=' + json.dumps({'run': run, 'files': list(changes),
                                            'rollback_available': True, 'payments_or_database_modified': False}))


def rollback(run: str) -> None:
    root = backup_dir(run)
    if not root.is_dir() or root.is_symlink():
        raise RuntimeError('BACKUP_MISSING')
    info = json.loads((root / 'manifest.json').read_text())
    for label, (path, sha) in EXPECTED.items():
        item = info[label]
        old = (root / (label + '.original')).read_bytes()
        if digest(old) != sha or digest(old) != item['old_sha256']:
            raise RuntimeError('BACKUP_INTEGRITY_FAIL:' + label)
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('UNSAFE_ROLLBACK_PATH:' + label)
        current = digest(path.read_bytes())
        if current not in (sha, item['new_sha256']):
            raise RuntimeError('CONCURRENT_CHANGE_PREVENTS_ROLLBACK:' + label)
    for label, (path, sha) in EXPECTED.items():
        if digest(path.read_bytes()) != sha:
            atomic_write(path, (root / (label + '.original')).read_bytes(), info[label]['mode'])
    touch_restart()
    print('THEME_ROLLBACK=RESTORED_ORIGINAL_SHA')


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'preview':
        preview()
    elif len(sys.argv) == 3 and sys.argv[1] == 'publish':
        publish(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == 'rollback':
        rollback(sys.argv[2])
    else:
        raise SystemExit('USAGE: preview | publish RUN_ID | rollback RUN_ID')
