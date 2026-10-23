#!/usr/bin/env python3
"""Hash-guarded additive Nexus 3D deployment for the existing live Arrow Cube.

It never overwrites the old game's JS, CSS, engine, or homepage cards.  The
only changed existing file is the arrow-escape index, with one additive link.
"""
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path('/home/zomorod2/public_html')
GAME = ROOT / 'arrow-escape'
INDEX = GAME / 'index.html'
MARK = 'NEXUS-3D-ENTRY-20261023'
SOURCE_MARK = 'ZM-ARROW-ESCAPE-THIRD-CARD-20261022'
FILES = ('nexus.html', 'nexus.css', 'nexus.js', 'nexus-core.js', 'nexus-fallback.js', 'nexus-experience.js',
         'three.module.js', 'three.core.min.js')
CTA = ('\n      <!-- ' + MARK + ' -->\n'
       '      <a href="./nexus.html" '
       'style="display:inline-flex;align-items:center;justify-content:center;'
       'background:linear-gradient(120deg,#174348,#1b6d64);color:#effcf6;'
       'border:1px solid #79b5a7;border-radius:14px;padding:13px 19px;'
       'font-weight:800;text-decoration:none;margin-top:18px;'
       'box-shadow:0 9px 24px #174a4333">'
       '✦ بازی جدید: نکسوس سه‌بعدی — پیچش واقعی و فلش‌های هوشمند ←</a>\n')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    assert path.is_file() and not path.is_symlink(), f'bad file: {path}'
    return path.read_bytes()


def update_index(data):
    text = data.decode('utf-8')
    assert text.count(SOURCE_MARK) == 1, 'unexpected live version marker'
    if MARK in text:
        assert text.count(MARK) == 1 and 'href="./nexus.html"' in text
        return data
    match = re.search(r'<section\b[^>]*class="intro"[^>]*>.*?</section>', text, re.S)
    assert match and text.count('class="intro"') == 1, 'intro insertion point changed'
    altered = text[:match.end()] + CTA + text[match.end():]
    assert altered.replace(CTA, '', 1) == text, 'changed more than one insertion'
    return altered.encode('utf-8')


def stagedir(run):
    return Path('/home/zomorod2/.zm-nexus3d-' + run)


def metadata(stage):
    return json.loads(read(stage / 'release.json'))


def write_meta(stage, value):
    tmp = stage / 'release.json.tmp'
    assert not tmp.exists() and not tmp.is_symlink()
    tmp.write_text(json.dumps(value, sort_keys=True), encoding='utf-8')
    os.replace(tmp, stage / 'release.json')


def atomic(path, contents, run):
    assert not path.is_symlink()
    temp = path.with_name('.' + path.name + '.nexus-' + run)
    assert not temp.exists() and not temp.is_symlink()
    with temp.open('xb') as output:
        output.write(contents)
    os.chmod(temp, 0o644)
    assert sha(read(temp)) == sha(contents)
    os.replace(temp, path)


def prepare(stage):
    assert GAME.is_dir() and not GAME.is_symlink(), 'existing cube route required'
    backup = stage / 'backup'
    assert not backup.exists()
    backup.mkdir(mode=0o700)
    old = read(INDEX)
    updated = update_index(old)
    (backup / 'index.html').write_bytes(old)
    (stage / 'updated-index.html').write_bytes(updated)
    state = {'phase': 'prepared', 'oldIndex': sha(old), 'newIndex': sha(updated),
             'oldAssets': {}, 'newAssets': {}, 'protected': {}}
    for name in FILES:
        path = GAME / name
        payload = read(stage / 'incoming' / name)
        assert len(payload) > 100, 'empty or incomplete asset ' + name
        assert not path.is_symlink()
        state['newAssets'][name] = sha(payload)
        if path.exists():
            existing = read(path)
            (backup / name).write_bytes(existing)
            state['oldAssets'][name] = sha(existing)
        else:
            state['oldAssets'][name] = None
    assert b'ARROW NEXUS 3D' in read(stage / 'incoming' / 'nexus.html')
    assert b'ArrowNexusCore' in read(stage / 'incoming' / 'nexus-core.js')
    assert b'ArrowNexusDebug' in read(stage / 'incoming' / 'nexus.js')
    assert b'nexus-fallback.js' in read(stage / 'incoming' / 'nexus.js')
    assert b'nexus-css3d' in read(stage / 'incoming' / 'nexus-fallback.js')
    assert b'NexusExperience' in read(stage / 'incoming' / 'nexus-experience.js')
    assert b'nexus-experience.js' in read(stage / 'incoming' / 'nexus.html')
    assert b'./three.core.min.js' in read(stage / 'incoming' / 'three.module.js')
    for name in ('engine.js', 'app.js', 'style.css', 'cube-engine.js', 'cover.svg'):
        path = GAME / name
        if path.exists():
            state['protected'][name] = sha(read(path))
    assert len(state['protected']) >= 4, 'old live game assets incomplete'
    write_meta(stage, state)
    print('NEXUS_UPGRADE_STAGED=PASS')


def verify_protected(state):
    for name, digest in state['protected'].items():
        assert sha(read(GAME / name)) == digest, 'old game changed: ' + name


def rollback(stage, run):
    if not (stage / 'release.json').is_file():
        print('NEXUS_ROLLBACK_NO_STATE')
        return
    state = metadata(stage)
    backup = stage / 'backup'
    if INDEX.is_file() and sha(read(INDEX)) == state['newIndex']:
        if state['newIndex'] != state['oldIndex']:
            atomic(INDEX, read(backup / 'index.html'), run)
    for name, before in state['oldAssets'].items():
        path = GAME / name
        if not path.is_file() or path.is_symlink() or sha(read(path)) != state['newAssets'][name]:
            continue
        if before is None:
            path.unlink()
        else:
            atomic(path, read(backup / name), run)
    print('NEXUS_UPGRADE_ROLLBACK=PASS')


def publish(stage, run):
    state = metadata(stage)
    assert state['phase'] == 'prepared'
    assert sha(read(INDEX)) == state['oldIndex'], 'index changed concurrently'
    for name, digest in state['oldAssets'].items():
        path = GAME / name
        assert (sha(read(path)) if path.exists() else None) == digest, 'asset changed: ' + name
    verify_protected(state)
    for name, digest in state['newAssets'].items():
        assert sha(read(stage / 'incoming' / name)) == digest
    try:
        for name in FILES:
            atomic(GAME / name, read(stage / 'incoming' / name), run)
        atomic(INDEX, read(stage / 'updated-index.html'), run)
        state['phase'] = 'published'
        write_meta(stage, state)
        verify(stage)
    except BaseException:
        rollback(stage, run)
        raise


def verify(stage):
    state = metadata(stage)
    assert state['phase'] == 'published'
    assert sha(read(INDEX)) == state['newIndex']
    assert MARK.encode() in read(INDEX)
    for name, digest in state['newAssets'].items():
        assert sha(read(GAME / name)) == digest
    verify_protected(state)
    print('NEXUS_UPGRADE_VERIFIED=PASS')


def main():
    assert len(sys.argv) == 3, 'usage: nexus-upgrade.py prepare|publish|verify|rollback RUN_ID'
    command, run = sys.argv[1:]
    assert re.fullmatch(r'[0-9]{4,15}', run)
    stage = stagedir(run)
    assert stage.is_dir() and not stage.is_symlink()
    operations = {'prepare': lambda: prepare(stage), 'publish': lambda: publish(stage, run),
                  'verify': lambda: verify(stage), 'rollback': lambda: rollback(stage, run)}
    assert command in operations
    operations[command]()


if __name__ == '__main__':
    main()
