#!/usr/bin/env python3
"""Conservative in-place 2D -> 3D game upgrade for an already installed card.

Uses the established private GitHub Actions -> VPS -> cPanel relay. Rejects
unexpected live changes, snapshots the exact bytes, and supports safe rollback.
"""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path('/home/zomorod2/public_html')
HOME = ROOT / 'index.html'
GAME = ROOT / 'arrow-escape'
MARK = b'ZM-ARROW-ESCAPE-THIRD-CARD-20261022'
ASSETS = ('index.html', 'style.css', 'engine.js', 'cube-engine.js', 'app.js', 'cover.svg')
PROTECTED = ('agriculture/index.html', 'research/index.html',
             'topics/zm-r25/website-design/index.html', 'ramadan-war/index.html')
PATTERN = re.compile(r'(window\.ZOMOROD_ORBIT_DATA=)(\{.*?\})(;</script>)', re.S)
CARD_ID = 'ZM-R25-GAME-ARROW-ESCAPE-20261022'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked(path):
    assert path.is_file() and not path.is_symlink(), f'missing or symlinked: {path}'
    return path.read_bytes()


def atomic(path, data, run):
    assert not path.is_symlink(), f'symlink blocked: {path}'
    temp = path.with_name('.' + path.name + '.cube-' + run)
    assert not temp.exists() and not temp.is_symlink(), f'temp collision: {temp}'
    with open(temp, 'xb') as output:
        output.write(data)
    os.chmod(temp, 0o644)
    assert digest(checked(temp)) == digest(data)
    os.replace(temp, path)


def edit_home(raw):
    text = raw.decode('utf-8')
    matches = list(PATTERN.finditer(text))
    assert len(matches) == 1, 'homepage manifest missing or duplicated'
    match = matches[0]
    data = json.loads(match.group(2))
    rows = [r for r in data['rows'] if r.get('id') == 'ZM-R25']
    assert len(rows) == 1 and rows[0]['title'] == 'فناوری اطلاعات و خدمات دیجیتال'
    cards = rows[0]['cards']
    assert len(cards) == 24 and cards[0]['id'] == 'ZM-R25-GAME-FARM-DOMINION-20261019'
    assert cards[1]['id'] == 'ZM-R25-GAME-RAMADAN-WAR-20261022'
    assert cards[2]['id'] == CARD_ID and cards[2]['slug'] == 'arrow-escape'
    assert cards[2]['canonicalUrl'] == '/arrow-escape/'
    assert cards[2]['title'] == 'بازی هزارتوی پیکان‌ها', 'old third card unexpectedly changed'
    assert cards[3]['slug'] == 'website-design', 'fourth card moved'
    before = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    cards[2]['title'] = 'بازی مکعب پیکان‌ها'
    after = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    assert len(cards) == 24
    revised = text[:match.start(2)] + after + text[match.end(2):]
    assert revised.replace(after, match.group(2), 1) == text
    assert before != after
    return revised.encode('utf-8')


def stage_path(run):
    return Path('/home/zomorod2/.zm-arrow-cube-upgrade-' + run)


def read_meta(stage):
    return json.loads(checked(stage / 'release.json'))


def write_meta(stage, meta):
    temp = stage / 'release.json.tmp'
    assert not temp.is_symlink()
    temp.write_text(json.dumps(meta, ensure_ascii=False, sort_keys=True), 'utf-8')
    os.replace(temp, stage / 'release.json')


def protected_checks(protected):
    for rel, expected in protected.items():
        assert digest(checked(ROOT / rel)) == expected, f'protected page changed: {rel}'


def prepare(stage):
    assert ROOT.is_dir() and not ROOT.is_symlink()
    assert GAME.is_dir() and not GAME.is_symlink(), 'expected existing game route'
    assert (GAME / '.htaccess').is_file()
    assert checked(GAME / '.htaccess') == b'PassengerEnabled off\nDirectoryIndex index.html\n'
    assert not (GAME / 'cube-engine.js').exists() and not (GAME / 'cube-engine.js').is_symlink()
    old_home = checked(HOME)
    new_home = edit_home(old_home)
    old = {name: checked(GAME / name) for name in ASSETS if name != 'cube-engine.js'}
    assert MARK in old['index.html'] and '<title>هزارتوی پیکان‌ها'.encode() in old['index.html'], 'not old 2D route'
    assert b'./cube-engine.js' not in old['index.html']
    incoming = {name: checked(stage / 'incoming' / name) for name in ASSETS}
    assert MARK in incoming['index.html']
    assert b'./cube-engine.js' in incoming['index.html']
    assert b'ArrowCubeCore' in incoming['cube-engine.js']
    assert b'ArrowMazeDebug' in incoming['app.js']
    assert b'<svg' in incoming['cover.svg']
    assert all(len(content) > 200 for content in incoming.values())
    protected = {}
    for rel in PROTECTED:
        path = ROOT / rel
        if path.is_file():
            protected[rel] = digest(checked(path))
    assert len(protected) >= 3, 'protected pages unavailable'
    (stage / 'old-home.html').write_bytes(old_home)
    (stage / 'new-home.html').write_bytes(new_home)
    backup = stage / 'backup'
    backup.mkdir(mode=0o700)
    for name, content in old.items():
        (backup / name).write_bytes(content)
    meta = {
        'phase': 'prepared', 'oldHome': digest(old_home), 'newHome': digest(new_home),
        'old': {n: digest(v) for n, v in old.items()},
        'new': {n: digest(v) for n, v in incoming.items()},
        'protected': protected,
    }
    write_meta(stage, meta)
    print('ARROW_CUBE_UPGRADE_PREPARED=PASS')


def rollback(stage, run):
    if not (stage / 'release.json').is_file():
        print('ARROW_CUBE_ROLLBACK_NO_STATE')
        return
    meta = read_meta(stage)
    if HOME.is_file() and not HOME.is_symlink() and digest(checked(HOME)) == meta['newHome']:
        atomic(HOME, checked(stage / 'old-home.html'), run)
    if GAME.is_dir() and not GAME.is_symlink():
        for name, expected in meta['new'].items():
            path = GAME / name
            if not path.is_file() or path.is_symlink() or digest(checked(path)) != expected:
                continue  # Protect unrelated concurrent edits.
            if name in meta['old']:
                atomic(path, checked(stage / 'backup' / name), run)
            else:
                path.unlink()  # Only this exact new asset, with matching hash.
    print('ARROW_CUBE_ROLLBACK_FINISHED')


def publish(stage, run):
    meta = read_meta(stage)
    assert meta['phase'] == 'prepared'
    assert digest(checked(HOME)) == meta['oldHome'], 'homepage changed concurrently'
    assert GAME.is_dir() and not GAME.is_symlink()
    for name, expected in meta['old'].items():
        assert digest(checked(GAME / name)) == expected, f'old game asset changed: {name}'
    assert not (GAME / 'cube-engine.js').exists() and not (GAME / 'cube-engine.js').is_symlink()
    protected_checks(meta['protected'])
    for name, expected in meta['new'].items():
        assert digest(checked(stage / 'incoming' / name)) == expected
    try:
        for name in ASSETS:
            atomic(GAME / name, checked(stage / 'incoming' / name), run)
        for name, expected in meta['new'].items():
            assert digest(checked(GAME / name)) == expected
        assert digest(checked(HOME)) == meta['oldHome'], 'homepage changed during upload'
        atomic(HOME, checked(stage / 'new-home.html'), run)
        meta['phase'] = 'published'
        write_meta(stage, meta)
        print('ARROW_CUBE_3D_PUBLISHED=PASS; CARD_THREE_TITLE_ONLY')
    except BaseException:
        rollback(stage, run)
        raise


def verify(stage):
    meta = read_meta(stage)
    assert meta['phase'] == 'published'
    assert digest(checked(HOME)) == meta['newHome']
    for name, expected in meta['new'].items():
        assert digest(checked(GAME / name)) == expected
    protected_checks(meta['protected'])
    manifest = json.loads(PATTERN.search(checked(HOME).decode('utf-8')).group(2))
    row = next(r for r in manifest['rows'] if r.get('id') == 'ZM-R25')
    assert len(row['cards']) == 24
    assert row['cards'][2]['id'] == CARD_ID
    assert row['cards'][2]['title'] == 'بازی مکعب پیکان‌ها'
    assert row['cards'][3]['slug'] == 'website-design'
    print('ARROW_CUBE_UPGRADE_AND_PROTECTED_PAGES=PASS')


def main():
    assert len(sys.argv) == 3, 'usage: upgrade.py prepare|publish|verify|rollback RUN_ID'
    action, run = sys.argv[1:]
    assert re.fullmatch(r'[0-9]{4,15}', run), 'invalid run ID'
    stage = stage_path(run)
    assert stage.is_dir() and not stage.is_symlink()
    {'prepare': lambda: prepare(stage), 'publish': lambda: publish(stage, run),
     'verify': lambda: verify(stage), 'rollback': lambda: rollback(stage, run)}[action]()


if __name__ == '__main__':
    main()
