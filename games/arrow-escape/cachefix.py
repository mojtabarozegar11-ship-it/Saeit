#!/usr/bin/env python3
"""Guarded cache-busting follow-up: update only existing 3D HTML and card image URL."""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path('/home/zomorod2/public_html')
HOME = ROOT / 'index.html'
GAME = ROOT / 'arrow-escape'
HTML = GAME / 'index.html'
PATTERN = re.compile(r'(window\.ZOMOROD_ORBIT_DATA=)(\{.*?\})(;</script>)', re.S)
VERSION = '?v=cube3d-20261022-2'
OLD_IMAGE = '/arrow-escape/cover.svg'
NEW_IMAGE = OLD_IMAGE + VERSION
PROTECTED = ('agriculture/index.html', 'research/index.html',
             'topics/zm-r25/website-design/index.html', 'ramadan-war/index.html')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked(path):
    assert path.is_file() and not path.is_symlink(), f'unexpected path: {path}'
    return path.read_bytes()


def atomic(path, data, run):
    assert not path.is_symlink()
    tmp = path.with_name('.' + path.name + '.cube-cache-' + run)
    assert not tmp.exists() and not tmp.is_symlink()
    with open(tmp, 'xb') as output:
        output.write(data)
    os.chmod(tmp, 0o644)
    assert checked(tmp) == data
    os.replace(tmp, path)


def edit_home(raw):
    text = raw.decode('utf-8')
    matches = list(PATTERN.finditer(text))
    assert len(matches) == 1
    match = matches[0]
    manifest = json.loads(match.group(2))
    row = next(r for r in manifest['rows'] if r.get('id') == 'ZM-R25')
    cards = row['cards']
    assert len(cards) == 24 and cards[2]['id'] == 'ZM-R25-GAME-ARROW-ESCAPE-20261022'
    assert cards[2]['title'] == 'بازی مکعب پیکان‌ها' and cards[2]['image'] == OLD_IMAGE
    assert cards[3]['slug'] == 'website-design'
    cards[2]['image'] = NEW_IMAGE
    packed = json.dumps(manifest, ensure_ascii=False, separators=(',', ':'))
    output = text[:match.start(2)] + packed + text[match.end(2):]
    assert output.replace(packed, match.group(2), 1) == text
    return output.encode('utf-8')


def stage_path(run):
    return Path('/home/zomorod2/.zm-arrow-cube-cachefix-' + run)


def meta_read(stage):
    return json.loads(checked(stage / 'meta.json'))


def meta_write(stage, meta):
    path = stage / 'meta.json'
    temp = stage / 'meta.tmp'
    temp.write_text(json.dumps(meta), 'utf-8')
    os.replace(temp, path)


def protect(meta):
    for rel, d in meta['protected'].items():
        assert digest(checked(ROOT / rel)) == d, f'protected route changed {rel}'


def prepare(stage):
    assert GAME.is_dir() and not GAME.is_symlink()
    old_home, old_html = checked(HOME), checked(HTML)
    assert b'./style.css"' in old_html and b'./cube-engine.js"' in old_html
    assert 'مکعب پیکان‌ها'.encode() in old_html
    assert b'.cube-stage' in checked(GAME / 'style.css')
    assert b'ArrowCubeCore' in checked(GAME / 'cube-engine.js')
    new_html = checked(stage / 'incoming' / 'index.html')
    assert b'./style.css?v=cube3d-20261022-2' in new_html
    assert b'./cube-engine.js?v=cube3d-20261022-2' in new_html
    assert b'./app.js?v=cube3d-20261022-2' in new_html
    assert b'ZM-ARROW-ESCAPE-THIRD-CARD-20261022' in new_html
    new_home = edit_home(old_home)
    for name, data in [('old-home', old_home), ('old-html', old_html),
                       ('new-home', new_home), ('new-html', new_html)]:
        (stage / name).write_bytes(data)
    protected = {rel: digest(checked(ROOT / rel)) for rel in PROTECTED
                 if (ROOT / rel).is_file()}
    assert len(protected) >= 3
    meta_write(stage, {'phase': 'prepared', 'protected': protected,
        **{name: digest(data) for name, data in [('old-home', old_home),
         ('old-html', old_html), ('new-home', new_home), ('new-html', new_html)]}})
    print('CUBE_CACHEFIX_PREPARED=PASS')


def rollback(stage, run):
    if not (stage / 'meta.json').is_file():
        return
    meta = meta_read(stage)
    for label, path in [('home', HOME), ('html', HTML)]:
        if path.is_file() and not path.is_symlink() and digest(checked(path)) == meta['new-' + label]:
            atomic(path, checked(stage / ('old-' + label)), run)
    print('CUBE_CACHEFIX_ROLLED_BACK')


def publish(stage, run):
    meta = meta_read(stage)
    assert meta['phase'] == 'prepared'
    assert digest(checked(HOME)) == meta['old-home']
    assert digest(checked(HTML)) == meta['old-html']
    protect(meta)
    try:
        atomic(HTML, checked(stage / 'new-html'), run)
        assert digest(checked(HOME)) == meta['old-home']
        atomic(HOME, checked(stage / 'new-home'), run)
        meta['phase'] = 'published'
        meta_write(stage, meta)
        print('CUBE_CACHEFIX_PUBLISHED=PASS')
    except BaseException:
        rollback(stage, run)
        raise


def verify(stage):
    meta = meta_read(stage)
    assert meta['phase'] == 'published'
    assert digest(checked(HOME)) == meta['new-home']
    assert digest(checked(HTML)) == meta['new-html']
    protect(meta)
    print('CUBE_CACHEFIX_VERIFIED=PASS')


def main():
    assert len(sys.argv) == 3
    action, run = sys.argv[1:]
    assert re.fullmatch(r'[0-9]{4,15}', run)
    stage = stage_path(run)
    assert stage.is_dir() and not stage.is_symlink()
    {'prepare': lambda: prepare(stage), 'publish': lambda: publish(stage, run),
     'verify': lambda: verify(stage), 'rollback': lambda: rollback(stage, run)}[action]()


if __name__ == '__main__':
    main()
