#!/usr/bin/env python3
"""Guarded cPanel release/rollback for the winding 3D Arrow Cube game.

Only the four named files inside public_html/arrow-escape can be replaced.
The homepage, game card, other routes, and other games are never modified.
"""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path('/home/zomorod2/public_html')
GAME = ROOT / 'arrow-escape'
FILES = ('index.html', 'cube-engine.js', 'app.js', 'style.css')
PROTECTED = ('index.html', 'agriculture/index.html', 'research/index.html',
             'topics/zm-r25/website-design/index.html', 'ramadan-war/index.html')
OLD = b'cube3d-touchfix-20261023-1'
NEW = b'maze3d-v3-20261023'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    assert path.is_file() and not path.is_symlink(), f'unsafe file: {path}'
    return path.read_bytes()


def location(run):
    return Path('/home/zomorod2/.zm-arrow-maze3d-' + run)


def atomic(path, data, run):
    assert path.is_file() and not path.is_symlink()
    tmp = path.with_name('.' + path.name + '.maze3d-' + run)
    assert not tmp.exists() and not tmp.is_symlink()
    with open(tmp, 'xb') as out:
        out.write(data)
    os.chmod(tmp, 0o644)
    assert read(tmp) == data
    os.replace(tmp, path)


def metadata(stage):
    return json.loads(read(stage / 'meta.json'))


def write_meta(stage, data):
    tmp = stage / 'meta.next'
    assert not tmp.exists()
    tmp.write_text(json.dumps(data, sort_keys=True), encoding='utf-8')
    os.replace(tmp, stage / 'meta.json')


def verify_protected(data):
    for rel, sha in data['protected'].items():
        assert digest(read(ROOT / rel)) == sha, 'unrelated route changed: ' + rel


def prepare(stage):
    assert GAME.is_dir() and not GAME.is_symlink()
    old = {name: read(GAME / name) for name in FILES}
    new = {name: read(stage / 'incoming' / name) for name in FILES}
    assert OLD in old['index.html'] and NEW not in old['index.html'], 'unexpected existing release'
    assert NEW in new['index.html'] and OLD not in new['index.html']
    assert new['index.html'].count(b'ZM-ARROW-ESCAPE-THIRD-CARD-20261022') == 1
    assert old['index.html'].count(b'ZM-ARROW-ESCAPE-THIRD-CARD-20261022') == 1
    for asset in (b'engine.js', b'cube-engine.js', b'app.js', b'style.css'):
        assert asset + b'?v=' + NEW in new['index.html'], asset
    assert b'mosaicPieces' in new['cube-engine.js']
    assert b'facePips' in new['app.js'] and b'arrow-hit-point' in new['app.js']
    assert b'face-pips' in new['style.css']
    assert b'id="hintMoveButton"' in new['index.html']
    protected = {name: digest(read(ROOT / name)) for name in PROTECTED
                 if (ROOT / name).is_file()}
    assert len(protected) >= 3, 'protected page inventory unexpectedly sparse'
    for name in FILES:
        (stage / ('old-' + name)).write_bytes(old[name])
        (stage / ('new-' + name)).write_bytes(new[name])
    write_meta(stage, {'phase': 'prepared', 'protected': protected,
                       'old': {n: digest(b) for n, b in old.items()},
                       'new': {n: digest(b) for n, b in new.items()}})
    print('ARROW_MAZE3D_PREPARED=PASS', flush=True)


def rollback(stage, run):
    if not (stage / 'meta.json').is_file():
        return
    meta = metadata(stage)
    for name in FILES:
        path = GAME / name
        if path.is_file() and not path.is_symlink() and digest(read(path)) == meta['new'][name]:
            atomic(path, read(stage / ('old-' + name)), run)
    print('ARROW_MAZE3D_ROLLBACK=PASS', flush=True)


def publish(stage, run):
    meta = metadata(stage)
    assert meta['phase'] == 'prepared'
    verify_protected(meta)
    for name in FILES:
        assert digest(read(GAME / name)) == meta['old'][name], 'concurrent edit: ' + name
    try:
        # Install dependencies first, HTML cache-busting reference last.
        for name in ('cube-engine.js', 'app.js', 'style.css', 'index.html'):
            atomic(GAME / name, read(stage / ('new-' + name)), run)
        meta['phase'] = 'published'
        write_meta(stage, meta)
        print('ARROW_MAZE3D_PUBLISHED=PASS', flush=True)
    except BaseException:
        rollback(stage, run)
        raise


def verify(stage):
    meta = metadata(stage)
    assert meta['phase'] == 'published'
    verify_protected(meta)
    for name in FILES:
        assert digest(read(GAME / name)) == meta['new'][name], name
    print('ARROW_MAZE3D_VERIFIED=PASS', flush=True)


def main():
    assert len(sys.argv) == 3, 'action RUN_ID'
    action, run = sys.argv[1:]
    assert action in {'prepare', 'publish', 'verify', 'rollback'}
    assert re.fullmatch(r'[0-9]{4,15}', run)
    stage = location(run)
    assert stage.is_dir() and not stage.is_symlink()
    {'prepare': prepare, 'publish': lambda s: publish(s, run),
     'verify': verify, 'rollback': lambda s: rollback(s, run)}[action](stage)


if __name__ == '__main__':
    main()
