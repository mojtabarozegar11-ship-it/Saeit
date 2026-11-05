#!/usr/bin/env python3
"""One-file, hash-guarded homepage scroll-layout correction on live cPanel.

The 29 lazily rendered orbit shelves have incorrect placeholder heights. When a
deep nav anchor is clicked, their first render changes the page's height and
the browser lands far below the intended anchor. Preserve content-visibility
and reserve observed heights per breakpoint without changing any other page.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import secrets
import stat
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen


HOME = Path('/home/zomorod2')
HTML = HOME / 'public_html' / 'index.html'
BACKUPS = HOME / 'Saeit' / '.route-backups'
LOCK = BACKUPS / 'orbit-homepage-20261105.lock'
MARKER = b'id="zm-orbit-anchor-stability-20261105"'
INSERT = b'''<style id="zm-orbit-anchor-stability-20261105">
/* Reserve measured shelf heights while preserving lazy rendering. */
@media (min-width:701px) {
  body .orbit-shelf { contain-intrinsic-size:auto 475px !important; }
}
@media (min-width:501px) and (max-width:700px) {
  body .orbit-shelf { contain-intrinsic-size:auto 340px !important; }
}
@media (max-width:500px) {
  body .orbit-shelf { contain-intrinsic-size:auto 363px !important; }
}
</style>
'''
OLD_DESKTOP = b'.orbit-shelf{content-visibility:auto;contain-intrinsic-size:auto 410px}'
OLD_MOBILE = b'.orbit-shelf{contain-intrinsic-size:auto 290px}'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def patch_homepage(original: bytes) -> bytes:
    if MARKER in original:
        raise RuntimeError('HOMEPAGE_ALREADY_HAS_ANCHOR_PATCH')
    if original.count(OLD_DESKTOP) != 1 or original.count(OLD_MOBILE) != 1:
        raise RuntimeError('HOMEPAGE_CSS_BASELINE_CHANGED_ABORT')
    if original.lower().count(b'</head>') != 1:
        raise RuntimeError('HOMEPAGE_HEAD_STRUCTURE_CHANGED_ABORT')
    if original.count(b'orbit-shelf') < 29 or not all(
        (b'id="orbit-' + str(number).encode() + b'"') in original
        for number in (1, 12, 17, 29)
    ):
        raise RuntimeError('ORBIT_ANCHOR_STRUCTURE_CHANGED_ABORT')
    result = re.sub(rb'</head>', lambda _: INSERT + b'</head>', original,
                    count=1, flags=re.IGNORECASE)
    if result.count(MARKER) != 1 or result.replace(INSERT, b'', 1) != original:
        raise RuntimeError('PATCH_NOT_ISOLATED')
    return result


def atomic_write(target: Path, content: bytes, mode: int) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.zm-orbit-',
                                         delete=False) as writer:
            temporary = Path(writer.name)
            writer.write(content)
            writer.flush()
            os.fsync(writer.fileno())
        os.chmod(temporary, stat.S_IMODE(mode))
        os.replace(temporary, target)
        temporary = None
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def safety_check() -> None:
    if os.getuid() != HOME.stat().st_uid:
        raise RuntimeError('WRONG_CPANEL_ACCOUNT_ABORT')
    if HTML.is_symlink() or HTML.parent.is_symlink() or not HTML.is_file():
        raise RuntimeError('HOME_FILE_PATH_UNEXPECTED_ABORT')
    if HTML.stat().st_size > 5_000_000:
        raise RuntimeError('UNEXPECTED_HOMEPAGE_SIZE_ABORT')


def live_get(url_path: str) -> tuple[int, bytes]:
    separator = '&' if '?' in url_path else '?'
    target = ('https://zomorodmelal.ir' + url_path + separator +
              'zm_orbit=' + secrets.token_hex(8))
    request = Request(target, headers={'User-Agent': 'ZM-Orbit-Guard/1.0',
                                      'Cache-Control': 'no-cache',
                                      'Pragma': 'no-cache'})
    with urlopen(request, timeout=15) as response:
        return response.status, response.read(5_000_001)


def baseline_live() -> None:
    for route in ('/', '/newsletter/', '/search/?q=%DA%AF%D9%86%D8%AF%D9%85',
                  '/carpets/'):
        status, _ = live_get(route)
        if status != 200:
            raise RuntimeError('EXISTING_LIVE_ROUTE_UNHEALTHY:' + route + ':' + str(status))


def verify_live(patched: bytes) -> bool:
    status, body = live_get('/')
    if status != 200 or body.count(MARKER) != 1:
        return False
    if any(x not in body for x in (
        b'body .orbit-shelf { contain-intrinsic-size:auto 475px !important; }',
        b'body .orbit-shelf { contain-intrinsic-size:auto 340px !important; }',
        b'body .orbit-shelf { contain-intrinsic-size:auto 363px !important; }',
    )):
        return False
    # The browser receives the same verified file's unique style, and all
    # prior section ids remain available for fragment-based navigation.
    if not all((b'id="orbit-' + str(n).encode() + b'"') in body
               for n in (1, 12, 17, 29)):
        return False
    return True


def run(mode: str) -> dict:
    safety_check()
    BACKUPS.mkdir(exist_ok=True, mode=0o700)
    with LOCK.open('a+b') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        safety_check()
        current = HTML.read_bytes()
        if mode == 'preview':
            changed = patch_homepage(current)
            baseline_live()
            return {'status': 'PREVIEW_ONLY', 'homepage_sha256': digest(current),
                    'bytes': len(current), 'new_sha256': digest(changed),
                    'target': str(HTML), 'live_baseline_healthy': True}
        if mode != 'publish':
            raise RuntimeError('INVALID_MODE')
        updated = patch_homepage(current)
        baseline_live()
        copy = BACKUPS / ('homepage-orbit-20261105-' + digest(current)[:16] + '.bak')
        if copy.exists():
            if digest(copy.read_bytes()) != digest(current):
                raise RuntimeError('BACKUP_CONFLICT_ABORT')
        else:
            with copy.open('xb') as writer:
                writer.write(current)
                writer.flush()
                os.fsync(writer.fileno())
            copy.chmod(0o600)
        original_mode = HTML.stat().st_mode
        if HTML.read_bytes() != current:
            raise RuntimeError('CONCURRENT_HOMEPAGE_EDIT_ABORT')
        atomic_write(HTML, updated, original_mode)
        try:
            consecutive = 0
            for _ in range(12):
                consecutive = consecutive + 1 if verify_live(updated) else 0
                if consecutive >= 2:
                    baseline_live()
                    return {'status': 'LIVE_HTTP_VERIFIED',
                            'homepage_before_sha256': digest(current),
                            'homepage_after_sha256': digest(updated),
                            'private_backup': str(copy),
                            'public_verification_passes': consecutive,
                            'existing_routes_healthy': True,
                            'browser_first_click_qa_pending': True}
                time.sleep(3)
            raise RuntimeError('PUBLIC_HTML_NOT_UPDATED_IN_TIME')
        except Exception as error:
            if HTML.read_bytes() != updated:
                raise RuntimeError('CONCURRENT_HOMEPAGE_EDIT_MANUAL_REVIEW') from error
            atomic_write(HTML, current, original_mode)
            if HTML.read_bytes() != current:
                raise RuntimeError('HOMEPAGE_ROLLBACK_FAILED') from error
            raise RuntimeError('HOMEPAGE_ROLLED_BACK:' + str(error)) from error


def selftest() -> None:
    sample = (b'<html><head><style>' + OLD_DESKTOP + OLD_MOBILE + b'</style></head>'
              b'<body>' + b''.join(b'<section class="orbit-shelf" id="orbit-' +
                                 str(n).encode() + b'"></section>'
                                 for n in range(1, 30)) + b'</body></html>')
    result = patch_homepage(sample)
    assert result.count(MARKER) == 1
    assert result.replace(INSERT, b'', 1) == sample
    assert b'content-visibility:auto' in result
    try:
        patch_homepage(result)
    except RuntimeError as exc:
        assert 'ALREADY_HAS' in str(exc)
    else:
        raise AssertionError('duplicate patch incorrectly accepted')


if __name__ == '__main__':
    try:
        if sys.argv[1:] == ['selftest']:
            selftest()
            print('ORBIT_PATCH_SELFTEST_OK')
        elif len(sys.argv) == 2 and sys.argv[1] in ('preview', 'publish'):
            print('ZM_ORBIT_RESULT=' + json.dumps(run(sys.argv[1]), sort_keys=True), flush=True)
        else:
            raise RuntimeError('USAGE: selftest|preview|publish')
    except Exception as exc:
        print('ZM_ORBIT_FAILED=' + str(exc), flush=True)
        raise
