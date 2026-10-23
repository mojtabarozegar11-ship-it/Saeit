#!/usr/bin/env python3
"""Atomic and reversible cPanel update for the Arrow Escape touch controls.

Does not modify homepage, navigation, neighbouring cards or any other route.
Only expected prior release may be upgraded; concurrent changes abort safely.
"""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

SITE = Path('/home/zomorod2/public_html')
GAME = SITE / 'arrow-escape'
FILES = ('index.html', 'style.css', 'app.js')
PROTECTED = ('index.html', 'agriculture/index.html', 'research/index.html',
             'topics/zm-r25/website-design/index.html', 'ramadan-war/index.html')
OLD_VERSION = b'cube3d-20261022-2'
NEW_VERSION = b'cube3d-touchfix-20261023-1'


def stage_dir(run):
    return Path('/home/zomorod2/.zm-arrow-touchfix-' + run)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe_read(path):
    assert path.is_file() and not path.is_symlink(), f'unsafe path: {path}'
    return path.read_bytes()


def atomic(path, data, run):
    assert path.is_file() and not path.is_symlink()
    temp = path.with_name('.' + path.name + '.touchfix-' + run)
    assert not temp.exists() and not temp.is_symlink()
    with open(temp, 'xb') as stream:
        stream.write(data)
    os.chmod(temp, 0o644)
    assert safe_read(temp) == data
    os.replace(temp, path)


def read_meta(stage):
    return json.loads(safe_read(stage / 'meta.json'))


def update_meta(stage, meta):
    path = stage / 'meta.json'
    temp = stage / 'meta.next'
    temp.write_text(json.dumps(meta, sort_keys=True), encoding='utf-8')
    os.replace(temp, path)


def check_protected(meta):
    for relative, digest in meta['protected'].items():
        assert sha(safe_read(SITE / relative)) == digest, relative


def prepare(stage):
    assert GAME.is_dir() and not GAME.is_symlink()
    originals = {name: safe_read(GAME / name) for name in FILES}
    incoming = {name: safe_read(stage / 'incoming' / name) for name in FILES}
    old_html, new_html = originals['index.html'], incoming['index.html']
    assert OLD_VERSION in old_html and NEW_VERSION not in old_html
    assert NEW_VERSION in new_html and OLD_VERSION not in new_html
    for script in (b'style.css', b'cube-engine.js', b'app.js'):
        assert script + b'?v=' + NEW_VERSION in new_html
    assert old_html.count(b'ZM-ARROW-ESCAPE-THIRD-CARD-20261022') == 1
    assert new_html.count(b'ZM-ARROW-ESCAPE-THIRD-CARD-20261022') == 1
    assert b'ArrowMazeDebug' in originals['app.js']
    assert b'hintMoveButton' in incoming['app.js']
    assert b'arrow-hit-point' in incoming['style.css']
    assert b'arrow-hit-point' in incoming['app.js']
    assert b'id="hintMoveButton"' in new_html
    protected = {name: sha(safe_read(SITE / name)) for name in PROTECTED
                 if (SITE / name).is_file()}
    assert len(protected) >= 3, 'protected site routes missing'
    for name in FILES:
        (stage / ('old-' + name)).write_bytes(originals[name])
        (stage / ('new-' + name)).write_bytes(incoming[name])
    meta = {'phase': 'prepared', 'protected': protected,
            'old': {name: sha(originals[name]) for name in FILES},
            'new': {name: sha(incoming[name]) for name in FILES}}
    update_meta(stage, meta)
    print('ARROW_TOUCH_PREPARED=PASS')


def rollback(stage, run):
    if not (stage / 'meta.json').is_file():
        return
    meta = read_meta(stage)
    for name in FILES:
        path = GAME / name
        if path.is_file() and not path.is_symlink() and sha(safe_read(path)) == meta['new'][name]:
            atomic(path, safe_read(stage / ('old-' + name)), run)
    print('ARROW_TOUCH_ROLLBACK_COMPLETE')


def publish(stage, run):
    meta = read_meta(stage)
    assert meta['phase'] == 'prepared'
    check_protected(meta)
    for name in FILES:
        assert sha(safe_read(GAME / name)) == meta['old'][name], f'concurrent game edit: {name}'
    try:
        # Publish scripts and CSS first, then switch the HTML cache key last.
        for name in ('app.js', 'style.css', 'index.html'):
            atomic(GAME / name, safe_read(stage / ('new-' + name)), run)
        meta['phase'] = 'published'
        update_meta(stage, meta)
        print('ARROW_TOUCH_PUBLISHED=PASS')
    except BaseException:
        rollback(stage, run)
        raise


def verify(stage):
    meta = read_meta(stage)
    assert meta['phase'] == 'published'
    check_protected(meta)
    for name in FILES:
        assert sha(safe_read(GAME / name)) == meta['new'][name], name
    print('ARROW_TOUCH_VERIFIED=PASS')


def main():
    assert len(sys.argv) == 3
    action, run = sys.argv[1:]
    assert re.fullmatch(r'[0-9]{4,15}', run)
    stage = stage_dir(run)
    assert stage.is_dir() and not stage.is_symlink()
    {'prepare': prepare,
     'publish': lambda s: publish(s, run),
     'verify': verify,
     'rollback': lambda s: rollback(s, run)}[action](stage)


if __name__ == '__main__':
    main()
