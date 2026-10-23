#!/usr/bin/env python3
"""Standalone Persian game: append one card to existing Zomorod games index.

Scoped writes: /home/zomorod2/public_html/games/index.html (append card),
and two entirely new files in /games/air-supremacy/. Explicit backup,
byte-identity checks, atomic updates, rollback on failed live smoke.
No homepage, English MojPlayWin, other games, database or .htaccess edits.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import stat
import sys

HOME=Path('/home/zomorod2')
ROOT=HOME/'public_html'
HUB=ROOT/'games/index.html'
GAME=ROOT/'games/air-supremacy'
GAME_HTML=GAME/'index.html'
GAME_HT=GAME/'.htaccess'
HT_BYTES=b'PassengerEnabled off\nDirectoryIndex index.html\n'
MARK=b'ZM-AIR-SUPREMACY-FA-20261023-V1'
CARD=(b'\n<article class="card" id="zm-air-supremacy-fa-20261023">'
      b'<h2>\xd8\xa8\xd8\xb1\xd8\xaa\xd8\xb1\xdb\x8c \xd9\x87\xd9\x88\xd8\xa7\xdb\x8c\xdb\x8c: \xd9\x86\xd8\xa8\xd8\xb1\xd8\xaf \xd8\xac\xd8\xaa\xe2\x80\x8c\xd9\x87\xd8\xa7</h2>'
      b'<p>\xd8\xa8\xd8\xa7\xd8\xb2\xdb\x8c \xd8\xac\xd9\x86\xda\xaf\xdb\x8c \xd8\xb3\xd9\x87\xe2\x80\x8c\xd8\xa8\xd8\xb9\xd8\xaf\xdb\x8c \xd9\x81\xd8\xa7\xd8\xb1\xd8\xb3\xdb\x8c\xd8\x9b \xdb\xb1\xdb\xb2 \xd9\x85\xd8\xa3\xd9\x85\xd9\x88\xd8\xb1\xdb\x8c\xd8\xaa\xd8\x8c \xd8\xae\xd9\x84\xd8\xa8\xd8\xa7\xd9\x86\xdb\x8c \xd9\x85\xd9\x88\xd8\xa8\xd8\xa7\xdb\x8c\xd9\x84 \xd9\x88 \xd8\xa7\xd8\xb1\xd8\xaa\xd9\x82\xd8\xa7\xdb\x8c \xd8\xb1\xd8\xa7\xdb\x8c\xda\xaf\xd8\xa7\xd9\x86 \xd9\x87\xd9\x88\xd8\xa7\xd9\xbe\xdb\x8c\xd9\x85\xd8\xa7.</p>'
      b'<a href="/games/air-supremacy/">\xd8\xa7\xd8\xac\xd8\xb1\xd8\xa7\xdb\x8c \xd8\xa8\xd8\xa7\xd8\xb2\xdb\x8c \xd8\xa8\xd8\xb1\xd8\xaa\xd8\xb1\xdb\x8c \xd9\x87\xd9\x88\xd8\xa7\xdb\x8c\xdb\x8c</a></article>\n')
ANCHOR=b'<p><a href="/agriculture/">'
STAGE_PREFIX='.zm-air-supremacy-fa-'
PROTECTED=('index.html','.htaccess','games/.htaccess','games/water-path/index.html','agriculture/index.html')


def h(data):
    return hashlib.sha256(data).hexdigest()


def safe(path):
    root=ROOT
    if not root.is_dir() or root.is_symlink():
        raise RuntimeError('unsafe root')
    here=root
    for piece in path.relative_to(root).parts:
        here=here/piece
        if here.is_symlink():
            raise RuntimeError('symlink in '+str(here))
    return here


def need(path):
    if not safe(path).is_file():
        raise RuntimeError('required file absent: '+str(path))
    return path.read_bytes()


def meta_path(stage):
    return stage/'release.json'


def save(stage,data):
    tmp=stage/'release.json.new'
    tmp.write_text(json.dumps(data,sort_keys=True),encoding='utf-8')
    os.replace(tmp,meta_path(stage))


def metadata(stage):
    return json.loads(meta_path(stage).read_text('utf-8'))


def updated_hub(old):
    if len(old)<400 or len(old)>100000 or b'ZM-HOURLY-WATER-RELEASE-20261023-V2' not in old:
        raise RuntimeError('Unexpected existing games hub')
    if old.count(ANCHOR)!=1 or old.count(b'/games/water-path/')!=1 or b'/games/air-supremacy/' in old:
        raise RuntimeError('Games hub is not approved or already changed')
    new=old.replace(ANCHOR,CARD+ANCHOR,1)
    if new.replace(CARD,b'',1)!=old:
        raise RuntimeError('Non-additive hub modification')
    return new


def game_bytes(stage):
    data=(stage/'incoming/index.html').read_bytes()
    if not 49000<len(data)<160000 or MARK not in data or b'<html lang="fa" dir="rtl">' not in data:
        raise RuntimeError('Persian game source is not valid')
    if b'zm-air-supremacy-fa-campaign-v2' not in data or b'MOJPLAYWIN ORIGINAL' in data:
        raise RuntimeError('Localization isolation failed')
    if b'MAX_MISSION=12' not in data or b'__AIR_SUPREMACY_QA__' not in data:
        raise RuntimeError('Incomplete original game mechanics')
    if data.count(b'<script>')!=1:
        raise RuntimeError('Game script count wrong')
    return data


def write_atomic(dst,data,run):
    if dst.is_symlink():
        raise RuntimeError('unsafe output symlink')
    temp=dst.with_name('.'+dst.name+'.zm-air-'+run)
    fd=os.open(str(temp),os.O_WRONLY|os.O_EXCL|os.O_CREAT,0o644)
    with os.fdopen(fd,'wb') as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())
    os.replace(temp,dst)


def prepare(stage,run):
    if meta_path(stage).exists():
        raise RuntimeError('duplicate release')
    if GAME.exists() or GAME.is_symlink():
        raise RuntimeError('new game directory already occupied')
    data=game_bytes(stage)
    old=need(HUB)
    new=updated_hub(old)
    assert need(ROOT/'games/.htaccess')==HT_BYTES
    proof={}
    for rel in PROTECTED:
        proof[rel]=h(need(ROOT/rel))
    (stage/'old-hub.html').write_bytes(old)
    manifest={'stage':'prepared','run':run,'protected':proof,
              'hub_before':h(old),'hub_after':h(new),'game':h(data),'files':{}}
    save(stage,manifest)
    print('ZM_PERSIAN_GAME_PREPARED=PASS',flush=True)


def guard(stage,meta):
    for rel,digest in meta['protected'].items():
        if h(need(ROOT/rel))!=digest:
            raise RuntimeError('Protected file drift: '+rel)


def rollback(stage,run):
    if not meta_path(stage).is_file():
        print('NO_PERSIAN_RELEASE_TO_ROLLBACK',flush=True)
        return
    m=metadata(stage)
    before=(stage/'old-hub.html').read_bytes()
    if h(before)!=m['hub_before']:
        raise RuntimeError('Corrupt protected hub backup')
    if HUB.is_file() and h(need(HUB))==m['hub_after']:
        write_atomic(HUB,before,run)
        print('ZM_GAMES_HUB_ROLLED_BACK=YES',flush=True)
    elif HUB.is_file() and h(need(HUB))!=m['hub_before']:
        raise RuntimeError('Games hub concurrent change — manual review required')
    if GAME.is_dir() and not GAME.is_symlink():
        for fn in ('index.html','.htaccess'):
            dest=GAME/fn
            if dest.is_file() and not dest.is_symlink() and h(dest.read_bytes())==m['files'].get(fn):
                dest.unlink()
            elif dest.exists():
                raise RuntimeError('Unexpected new-game file: '+fn)
        if not list(GAME.iterdir()):
            GAME.rmdir()
    m['stage']='rolled_back'
    save(stage,m)
    print('ZM_PERSIAN_GAME_ROLLBACK_DONE',flush=True)


def publish(stage,run):
    m=metadata(stage)
    if m['stage']!='prepared':
        raise RuntimeError('bad release phase')
    guard(stage,m)
    if h(need(HUB))!=m['hub_before'] or GAME.exists() or GAME.is_symlink():
        raise RuntimeError('Concurrent hub or game edit')
    raw=game_bytes(stage)
    if h(raw)!=m['game']:
        raise RuntimeError('staged game drift')
    new=updated_hub(need(HUB))
    GAME.mkdir(mode=0o755)
    try:
        for fn,blob in (('index.html',raw),('.htaccess',HT_BYTES)):
            write_atomic(GAME/fn,blob,run)
            m['files'][fn]=h(blob)
            save(stage,m)
        guard(stage,m)
        if h(need(HUB))!=m['hub_before']:
            raise RuntimeError('Concurrent hub edit immediately before replacement')
        write_atomic(HUB,new,run)
        m['stage']='published';save(stage,m)
    except BaseException:
        rollback(stage,run)
        raise
    print('ZM_PERSIAN_AIR_GAME_INSTALLED=PASS',flush=True)


def verify(stage,run):
    m=metadata(stage)
    if m['stage']!='published':
        raise RuntimeError('game not published')
    guard(stage,m)
    if h(need(HUB))!=m['hub_after'] or h(need(GAME_HTML))!=m['game'] or h(need(GAME_HT))!=h(HT_BYTES):
        raise RuntimeError('installed content mismatch')
    original=(stage/'old-hub.html').read_bytes()
    if need(HUB).replace(CARD,b'',1)!=original:
        raise RuntimeError('old games changed')
    print('ZM_PERSIAN_GAME_AND_EXISTING_GAMES_SAFE=PASS',flush=True)


def main():
    if len(sys.argv)!=3 or sys.argv[1] not in ('prepare','publish','verify','rollback') or not re.fullmatch(r'\d{7,15}',sys.argv[2]):
        raise SystemExit('usage: deploy.py prepare|publish|verify|rollback RUN_ID')
    action,run=sys.argv[1:]
    stage=HOME/(STAGE_PREFIX+run)
    if not stage.is_dir() or stage.is_symlink():
        raise RuntimeError('private staging directory missing')
    globals()[action](stage,run)


if __name__=='__main__':
    main()
