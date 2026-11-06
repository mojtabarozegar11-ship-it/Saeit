#!/usr/bin/env python3
"""Reorder the production services hero ahead of two previously-added panels.

No new products, form submissions, database edits, outbound messages or costs.
Deployment is one exact-SHA-guarded static file with rollback on failure.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

SITE = Path('/home/zomorod2/public_html')
PAGE = SITE / 'services/index.html'
PRIVATE = Path('/home/zomorod2/.private')
BACKUPS = PRIVATE / 'zomorod-services-first-screen-backups'
EXPECTED_SHA256 = '06f121478ad510b6a5b303424a55a5094482a9cf6b335bdeca3725e49d69beed'
MARKER = 'zm-services-first-screen-20261106'
MAIN = '<main id="main">'
HERO = '<section class="zm-hero">'
OLD_H1 = '<h1>هر خدمت، با یک <em>مسئله واقعی.</em></h1>'
NEW_H1 = '<h1>خدمات کشاورزی <em>و اقتصاد تولید</em></h1>'
PANEL = re.compile(
    r'\s*<aside id="zm-services-action-hub-20261106"[\s\S]*?'
    r'</aside><!-- zm-services-conversion-20261106 -->\s*'
    r'<!-- zm-specialist-intent-20261106:services -->\s*'
    r'<section id="zm-service-deliverables-20261106"[\s\S]*?'
    r'</section><!-- zm-service-deliverables-20261106 -->\s*\Z'
)


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def validate() -> None:
    if os.geteuid() == 0 or os.geteuid() != SITE.stat().st_uid:
        raise RuntimeError('FIRST_SCREEN_REFUSE_WRONG_SITE_OWNER')
    for part in (SITE, PAGE.parent, PAGE, PRIVATE, BACKUPS):
        if part.is_symlink():
            raise RuntimeError('FIRST_SCREEN_REFUSE_SYMLINK')
    if not PAGE.is_file():
        raise RuntimeError('FIRST_SCREEN_REFUSE_MISSING_PAGE')
    boundary = PAGE.parent / '.htaccess'
    if boundary.is_symlink() or not boundary.is_file() or 'PassengerEnabled off' not in boundary.read_text():
        raise RuntimeError('FIRST_SCREEN_REFUSE_NONSTATIC_ROUTE')


def transform(source: str) -> str:
    if MARKER in source:
        raise RuntimeError('FIRST_SCREEN_REFUSE_REPEAT')
    for anchor in (MAIN, HERO, OLD_H1,
                   '<!-- zm-services-conversion-20261106 -->',
                   '<!-- zm-service-deliverables-20261106 -->',
                   '<section class="zm-page-section">'):
        if source.count(anchor) != 1 and anchor != '<section class="zm-page-section">':
            raise RuntimeError('FIRST_SCREEN_REFUSE_MISSING_ANCHOR:' + anchor[:45])
    if source.count(MAIN) != 1 or source.count(HERO) != 1 or source.count(OLD_H1) != 1:
        raise RuntimeError('FIRST_SCREEN_REFUSE_STRUCTURE')
    main_end = source.index(MAIN) + len(MAIN)
    hero_start = source.index(HERO, main_end)
    if hero_start <= main_end:
        raise RuntimeError('FIRST_SCREEN_REFUSE_HERO_LOCATION')
    before_hero = source[main_end:hero_start]
    if not PANEL.fullmatch(before_hero):
        raise RuntimeError('FIRST_SCREEN_REFUSE_CHANGED_PRE_HERO_PANELS')
    hero_end = source.find('</section>', hero_start)
    if hero_end < 0 or '<section' in source[hero_start + len(HERO):hero_end]:
        raise RuntimeError('FIRST_SCREEN_REFUSE_NESTED_OR_UNCLOSED_HERO')
    hero_end += len('</section>')
    if not re.match(r'\s*<section class="zm-page-section">', source[hero_end:]):
        raise RuntimeError('FIRST_SCREEN_REFUSE_CHANGED_HERO_SUCCESSOR')
    hero = source[hero_start:hero_end]
    if hero.count(OLD_H1) != 1 or 'data-zm-hero-cta="zm-service-hero-cta-20261106"' not in hero:
        raise RuntimeError('FIRST_SCREEN_REFUSE_UNEXPECTED_HERO')
    new_hero = hero.replace(OLD_H1, NEW_H1, 1)
    result = (source[:main_end] + '\n<!-- ' + MARKER + ' -->\n'
              + new_hero + '\n' + before_hero + source[hero_end:])
    if (result.count(HERO) != 1 or result.count(NEW_H1) != 1
            or result.count(MARKER) != 1
            or result.index(HERO) > result.index('zm-services-action-hub-20261106')
            or result.count('zm-service-deliverables-20261106') != 2
            or result.count('data-zm-hero-cta="zm-service-hero-cta-20261106"') != 1):
        raise RuntimeError('FIRST_SCREEN_INVALID_RESULT')
    return result


def target_folder(run_id: str) -> Path:
    if not re.fullmatch(r'[0-9]{5,20}', run_id):
        raise RuntimeError('FIRST_SCREEN_BAD_RUN_ID')
    return BACKUPS / run_id


def atomic_write(payload: bytes, mode: int) -> None:
    fd, name = tempfile.mkstemp(prefix='.zm-services-first-screen-', dir=str(PAGE.parent))
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(name, mode)
        os.replace(name, PAGE)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def preflight() -> tuple[bytes, bytes, int]:
    validate()
    old = PAGE.read_bytes()
    if sha(old) != EXPECTED_SHA256:
        raise RuntimeError('FIRST_SCREEN_REFUSE_UNRECOGNIZED_LIVE_SHA256:' + sha(old))
    new = transform(old.decode('utf-8')).encode('utf-8')
    return old, new, stat.S_IMODE(PAGE.stat().st_mode)


def preview() -> None:
    old, new, _ = preflight()
    print('FIRST_SCREEN_OLD_SHA256=' + sha(old))
    print('FIRST_SCREEN_NEW_SHA256=' + sha(new))
    print('FIRST_SCREEN_PREFLIGHT_OK=1')


def publish(run_id: str) -> None:
    old, new, mode = preflight()
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    folder = target_folder(run_id)
    folder.mkdir(mode=0o700)
    with (folder / 'services-index.backup').open('xb') as f:
        f.write(old)
    (folder / 'services-index.backup').chmod(0o600)
    manifest = {'old_sha': sha(old), 'new_sha': sha(new), 'mode': mode}
    (folder / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True))
    (folder / 'manifest.json').chmod(0o600)
    if PAGE.is_symlink() or sha(PAGE.read_bytes()) != manifest['old_sha']:
        raise RuntimeError('FIRST_SCREEN_REFUSE_CONCURRENT_EDIT')
    atomic_write(new, mode)
    print('FIRST_SCREEN_PUBLISHED=1')


def verify(run_id: str) -> None:
    validate()
    manifest = json.loads((target_folder(run_id) / 'manifest.json').read_text())
    raw = PAGE.read_bytes()
    if sha(raw) != manifest['new_sha']:
        raise RuntimeError('FIRST_SCREEN_ORIGIN_SHA_MISMATCH')
    source = raw.decode('utf-8')
    if not (source.index(MAIN) < source.index(MARKER) < source.index(HERO)
            < source.index(NEW_H1) < source.index('zm-services-action-hub-20261106')
            < source.index('zm-service-deliverables-20261106')):
        raise RuntimeError('FIRST_SCREEN_ORIGIN_ORDER_MISMATCH')
    print('FIRST_SCREEN_ORIGIN_VERIFIED=1')


def rollback(run_id: str) -> None:
    validate()
    folder = target_folder(run_id)
    manifest = json.loads((folder / 'manifest.json').read_text())
    prior = (folder / 'services-index.backup').read_bytes()
    if sha(prior) != manifest['old_sha']:
        raise RuntimeError('FIRST_SCREEN_CORRUPT_BACKUP')
    current = sha(PAGE.read_bytes())
    if current == manifest['new_sha']:
        atomic_write(prior, manifest['mode'])
        print('FIRST_SCREEN_ROLLBACK_VERIFIED=1')
    elif current == manifest['old_sha']:
        print('FIRST_SCREEN_ALREADY_ROLLED_BACK=1')
    else:
        raise RuntimeError('FIRST_SCREEN_REFUSE_OVERWRITE_NEWER_VERSION')


def selftest() -> None:
    main = '<html>' + MAIN
    panel = ('\n<aside id="zm-services-action-hub-20261106">x'
             '</aside><!-- zm-services-conversion-20261106 -->\n'
             '<!-- zm-specialist-intent-20261106:services -->\n'
             '<section id="zm-service-deliverables-20261106">content'
             '</section><!-- zm-service-deliverables-20261106 -->\n')
    hero = (HERO + OLD_H1 + '<div data-zm-hero-cta="zm-service-hero-cta-20261106">go</div>'
            '</section>\n<section class="zm-page-section">section</section></main></html>')
    output = transform(main + panel + hero)
    assert output.index(HERO) < output.index('zm-services-action-hub-20261106')
    assert NEW_H1 in output and OLD_H1 not in output
    assert output.count(MARKER) == 1
    print('FIRST_SCREEN_SELFTEST_OK=1')


if __name__ == '__main__':
    argv = sys.argv[1:]
    if argv == ['selftest']:
        selftest()
    elif argv == ['preview']:
        preview()
    elif len(argv) == 2 and argv[0] in ('publish', 'verify', 'rollback'):
        {'publish': publish, 'verify': verify, 'rollback': rollback}[argv[0]](argv[1])
    else:
        raise RuntimeError('FIRST_SCREEN_UNSAFE_MODE')
