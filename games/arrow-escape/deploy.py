#!/usr/bin/env python3
"""Hash-guarded cPanel release: add one game route and insert exactly card three.

Run from a private staging directory via the established GitHub Actions SSH
relay. No database, other card, template or unrelated public route is edited.
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
ROW = 'ZM-R25'
GAME_ID = 'ZM-R25-GAME-ARROW-ESCAPE-20261022'
MARK = 'ZM-ARROW-ESCAPE-THIRD-CARD-20261022'
ASSETS = ('index.html', 'style.css', 'engine.js', 'app.js', 'cover.svg', '.htaccess')
PROTECTED = ('agriculture/index.html', 'research/index.html', 'company/index.html',
             'topics/zm-r25/website-design/index.html', 'ramadan-war/index.html')
PATTERN = re.compile(r'(window\.ZOMOROD_ORBIT_DATA=)(\{.*?\})(;</script>)', re.S)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require_file(path):
    assert path.is_file() and not path.is_symlink(), f'missing or symlinked: {path}'
    return path.read_bytes()


def atomically_write(path, data, run):
    assert not path.is_symlink(), f'symlink blocked: {path}'
    temp = path.with_name('.' + path.name + '.arrow-' + run)
    assert not temp.exists() and not temp.is_symlink(), f'temp collision: {temp}'
    with open(temp, 'xb') as file:
        file.write(data)
    os.chmod(temp, 0o644)
    assert digest(require_file(temp)) == digest(data)
    os.replace(temp, path)


def edit_home(original):
    text = original.decode('utf-8')
    matches = list(PATTERN.finditer(text))
    assert len(matches) == 1, 'homepage manifest count differs from one'
    match = matches[0]
    data = json.loads(match.group(2))
    rows = data.get('rows', [])
    assert isinstance(rows, list) and len(rows) >= 26
    targets = [row for row in rows if row.get('id') == ROW]
    assert len(targets) == 1
    row = targets[0]
    assert row.get('title') == 'فناوری اطلاعات و خدمات دیجیتال'
    assert row.get('index') == 25 and row.get('slug') == 'digital-services'
    cards = row['cards']
    assert len(cards) == 23, f'expected 23 current cards, got {len(cards)}'
    assert cards[0].get('id') == 'ZM-R25-GAME-FARM-DOMINION-20261019'
    assert cards[1].get('id') == 'ZM-R25-GAME-RAMADAN-WAR-20261022'
    assert cards[2].get('slug') == 'website-design'
    assert not any(card.get('slug') == 'arrow-escape' or card.get('id') == GAME_ID
                   for other in rows for card in other.get('cards', []))
    prior = [card.copy() for card in cards]
    count = sum(len(entry['cards']) for entry in rows)
    cards.insert(2, {
        'id': GAME_ID,
        'title': 'بازی هزارتوی پیکان‌ها',
        'slug': 'arrow-escape',
        'image': '/arrow-escape/cover.svg',
        'imageStatus': 'original_vector_artwork',
        'canonicalUrl': '/arrow-escape/',
        'livePage': True
    })
    assert cards[3:] == prior[2:], 'existing cards changed'
    assert sum(len(entry['cards']) for entry in rows) == count + 1
    packed = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    assert '</script' not in packed.lower()
    revised = text[:match.start(2)] + packed + text[match.end(2):]
    assert revised.replace(packed, match.group(2), 1) == text
    return revised.encode('utf-8')


def stage_path(run):
    return Path('/home/zomorod2/.zm-arrow-escape-' + run)


def write_meta(stage, meta):
    data = json.dumps(meta, sort_keys=True, ensure_ascii=False).encode('utf-8')
    tmp = stage / 'release.json.tmp'
    tmp.write_bytes(data)
    os.replace(tmp, stage / 'release.json')


def read_meta(stage):
    return json.loads(require_file(stage / 'release.json'))


def prepare(stage):
    assert ROOT.is_dir() and not ROOT.is_symlink()
    assert not GAME.exists() and not GAME.is_symlink(), 'route already present: abort'
    old_home = require_file(HOME)
    new_home = edit_home(old_home)
    incoming = {}
    for name in ASSETS:
        incoming[name] = require_file(stage / 'incoming' / name)
    assert MARK.encode() in incoming['index.html']
    assert len(incoming['index.html']) > 1500
    assert b'ArrowMazeCore' in incoming['engine.js']
    assert b'ArrowMazeDebug' in incoming['app.js']
    assert b'<svg' in incoming['cover.svg']
    assert incoming['.htaccess'] == b'PassengerEnabled off\nDirectoryIndex index.html\n'
    assert b'./engine.js' in incoming['index.html']
    assert b'./app.js' in incoming['index.html']
    assert b'./style.css' in incoming['index.html']
    assert not (stage / 'old-home.html').exists()
    (stage / 'old-home.html').write_bytes(old_home)
    (stage / 'new-home.html').write_bytes(new_home)
    protected = {}
    for rel in PROTECTED:
        path = ROOT / rel
        if path.exists():
            protected[rel] = digest(require_file(path))
    assert len(protected) >= 3, 'too few protected routes available'
    meta = {
        'phase': 'prepared', 'oldHome': digest(old_home), 'newHome': digest(new_home),
        'assets': {name: digest(content) for name, content in incoming.items()},
        'protected': protected
    }
    write_meta(stage, meta)
    print('ARROW_GAME_PREPARED=PASS; protected routes fingerprinted')


def protected_verify(meta):
    for rel, expected in meta['protected'].items():
        assert digest(require_file(ROOT / rel)) == expected, f'protected route changed: {rel}'


def rollback(stage, run):
    if not (stage / 'release.json').is_file():
        print('ARROW_ROLLBACK_NO_STATE')
        return
    meta = read_meta(stage)
    if HOME.is_file() and digest(require_file(HOME)) == meta['newHome']:
        atomically_write(HOME, require_file(stage / 'old-home.html'), run)
        print('ARROW_ROLLBACK_HOME_RESTORED')
    if GAME.is_dir() and not GAME.is_symlink():
        for name, expected in meta['assets'].items():
            path = GAME / name
            if path.is_file() and not path.is_symlink() and digest(path.read_bytes()) == expected:
                path.unlink()
            elif path.exists():
                print('ARROW_ROLLBACK_SKIPPED_UNEXPECTED_ASSET', name)
        if not list(GAME.iterdir()):
            GAME.rmdir()
            print('ARROW_ROLLBACK_CREATED_ROUTE_REMOVED')


def publish(stage, run):
    meta = read_meta(stage)
    assert meta['phase'] == 'prepared'
    assert digest(require_file(HOME)) == meta['oldHome'], 'homepage changed concurrently'
    assert not GAME.exists() and not GAME.is_symlink(), 'target game route already exists'
    protected_verify(meta)
    for name, expected in meta['assets'].items():
        assert digest(require_file(stage / 'incoming' / name)) == expected
    try:
        GAME.mkdir(mode=0o755)
        for name in ASSETS:
            atomically_write(GAME / name, require_file(stage / 'incoming' / name), run)
        for name, expected in meta['assets'].items():
            assert digest(require_file(GAME / name)) == expected
        assert digest(require_file(HOME)) == meta['oldHome'], 'homepage changed during deployment'
        atomically_write(HOME, require_file(stage / 'new-home.html'), run)
        meta['phase'] = 'published'
        write_meta(stage, meta)
        print('ARROW_GAME_PUBLISHED=PASS; ONLY_ROW_25_CARD_3_ADDED')
    except BaseException:
        rollback(stage, run)
        raise


def verify(stage):
    meta = read_meta(stage)
    assert meta['phase'] == 'published'
    assert digest(require_file(HOME)) == meta['newHome']
    for name, expected in meta['assets'].items():
        assert digest(require_file(GAME / name)) == expected
    protected_verify(meta)
    text = require_file(HOME).decode('utf-8')
    manifest = json.loads(PATTERN.search(text).group(2))
    row = next(row for row in manifest['rows'] if row.get('id') == ROW)
    assert len(row['cards']) == 24
    assert row['cards'][2]['id'] == GAME_ID
    assert row['cards'][2]['canonicalUrl'] == '/arrow-escape/'
    assert row['cards'][3]['slug'] == 'website-design'
    print('ARROW_GAME_AND_PROTECTED_ROUTES=PASS')


def main():
    assert len(sys.argv) == 3, 'usage: deploy.py prepare|publish|verify|rollback RUN_ID'
    action, run = sys.argv[1:]
    assert re.fullmatch(r'[0-9]{4,15}', run), 'invalid run id'
    stage = stage_path(run)
    assert stage.is_dir() and not stage.is_symlink()
    actions = {
        'prepare': lambda: prepare(stage),
        'publish': lambda: publish(stage, run),
        'verify': lambda: verify(stage),
        'rollback': lambda: rollback(stage, run)
    }
    assert action in actions
    actions[action]()


if __name__ == '__main__':
    main()
