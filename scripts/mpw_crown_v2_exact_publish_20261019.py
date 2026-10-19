#!/usr/bin/env python3
"""Crown Defender V2: replace ONLY the existing static game index.html.

Requires the exact approved V1 digest; refuses concurrent edits/symlinks.
Before replacement, saves a verified complete rollback copy in private home.
No modifications to Django, Passenger, .htaccess, studio, store or subsites.
"""
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

HOME = Path('/home/zomorod2')
GAME = HOME/'mojplaywin.com/design-preview-20261017/mpw-crown-defender-20261019/index.html'
BACKUPS = HOME/'.mpw-crown-v2-snapshots'
PREVIOUS_SHA = '207bb18a6d93a91963c4be92191a7ea47a8d67521bca92273b738e6a2ecb88e5'
NEW_MARKER = b'Crown Defender V2'

def sha(content):
    return hashlib.sha256(content).hexdigest()

def fail(message):
    raise SystemExit('CROWN_V2_SAFE_ABORT '+message)

def check_regular(path):
    if path.is_symlink() or not path.is_file():
        fail('not a regular file: '+str(path))

def atomic_write(path, content, mode=0o644):
    fd, temp = tempfile.mkstemp(prefix='.crown-v2-',dir=str(path.parent))
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def manifest_file(run):
    if not re.fullmatch(r'[0-9]{6,15}',run):fail('invalid run')
    return BACKUPS/('v2-'+run+'.json')

def stage_file(run):
    return HOME/('.mpw-crown-game-stage-'+run+'.html')

def install(run, expected):
    manifest=manifest_file(run)
    if not re.fullmatch(r'[0-9a-f]{64}',expected):fail('invalid digest')
    if BACKUPS.is_symlink():fail('symlinked backup directory')
    if manifest.exists():fail('run already installed')
    check_regular(GAME)
    check_regular(stage_file(run))
    previous=GAME.read_bytes()
    staged=stage_file(run).read_bytes()
    if sha(previous)!=PREVIOUS_SHA:fail('current V1 differs from approved release; refuse overwrite')
    if sha(staged)!=expected:fail('staged game differs from verified GitHub asset')
    if not (34000<=len(staged)<=90000 and NEW_MARKER in staged and b'window.__mpwCrownDefenderTest' in staged):
        fail('V2 gameplay validation missing')
    BACKUPS.mkdir(mode=0o700,exist_ok=True)
    if BACKUPS.is_symlink():fail('symlinked backup directory')
    original_file=BACKUPS/('v1-'+run+'.html')
    if original_file.exists():fail('backup exists')
    with original_file.open('xb') as f:
        os.fchmod(f.fileno(),0o600)
        f.write(previous)
        f.flush()
        os.fsync(f.fileno())
    mode=stat.S_IMODE(GAME.stat().st_mode)
    meta={'run':run,'before_sha':sha(previous),'after_sha':expected,'before_bytes':len(previous),'after_bytes':len(staged),'mode':mode,'target':str(GAME)}
    atomic_write(manifest,json.dumps(meta,sort_keys=True).encode('utf-8'),0o600)
    atomic_write(GAME,staged,mode)
    if sha(GAME.read_bytes())!=expected:fail('post-install hash verification failed')
    print(json.dumps({'status':'CROWN_V2_EXACT_GAME_REPLACED','game_only':True,'old_sha':meta['before_sha'],'new_sha':expected,'backup':str(original_file),'bytes':len(staged)}))

def status(run):
    manifest=manifest_file(run)
    check_regular(manifest)
    data=json.loads(manifest.read_text('utf-8'))
    check_regular(GAME)
    current=sha(GAME.read_bytes())
    print(json.dumps({'status':'CROWN_V2_READONLY_STATUS','game_only':True,'expected':data['after_sha'],'actual':current,'verified':current==data['after_sha'],'backup_exists':(BACKUPS/('v1-'+run+'.html')).is_file()}))
    if current!=data['after_sha']:fail('installed hash differs')

def rollback(run):
    manifest=manifest_file(run)
    check_regular(manifest)
    data=json.loads(manifest.read_text('utf-8'))
    original=BACKUPS/('v1-'+run+'.html')
    check_regular(original)
    check_regular(GAME)
    previous=original.read_bytes()
    if sha(previous)!=data['before_sha']:fail('backup corrupted')
    current=sha(GAME.read_bytes())
    if current not in (data['after_sha'],data['before_sha']):fail('concurrent edit; refuse rollback')
    if current==data['after_sha']:
        atomic_write(GAME,previous,data['mode'])
    print(json.dumps({'status':'CROWN_V2_ROLLED_BACK','game_only':True,'sha':sha(GAME.read_bytes())}))

if __name__=='__main__':
    if len(sys.argv)<3:fail('usage: install run sha | status run | rollback run')
    action,run=sys.argv[1:3]
    if action=='install' and len(sys.argv)==4:install(run,sys.argv[3])
    elif action=='status' and len(sys.argv)==3:status(run)
    elif action=='rollback' and len(sys.argv)==3:rollback(run)
    else:fail('unknown action')