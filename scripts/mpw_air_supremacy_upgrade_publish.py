#!/usr/bin/env python3
"""SHA guarded, reversible in-place *only Air Supremacy* campaign upgrade.

No changes to root htaccess, other games, Crown Defender, studio, store, DB,
or payments. Refuse any unrecognized live HTML or concurrent modification.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import stat
import sys
import tempfile

HOME=Path('/home/zomorod2')
ROOT=HOME/'mojplaywin.com'
STATIC=ROOT/'design-preview-20261017'
DIR=STATIC/'air-supremacy'
TARGET=DIR/'index.html'
BACKUPS=HOME/'.mpw-air-campaign-release-backups'
BEFORE='f86480f92a2dfdea76b26b369f1ec517f60065c0db05984de5e33afb33054c95'
MARKERS=(b'Air Supremacy',b'MAX_MISSION=12',b'CAMPAIGN',b'100',
         b'cannonUpgrade',b'armorUpgrade',b'missileUpgrade',b'localStorage')


def sha(b):
    return hashlib.sha256(b).hexdigest()


def abort(msg):
    raise RuntimeError('AIR_CAMPAIGN_GUARDED_ABORT '+msg)


def checked(run,new):
    if not re.fullmatch(r'[0-9]{8,16}',run) or not re.fullmatch(r'[a-f0-9]{64}',new):
        abort('invalid run or digest')
    for p in (HOME,ROOT,STATIC,DIR):
        if p.is_symlink() or not p.is_dir():
            abort('unsafe directory '+str(p))
    if TARGET.is_symlink() or not TARGET.is_file():
        abort('game not a regular file')
    if BACKUPS.is_symlink():
        abort('unsafe backup parent')
    stage=HOME/('.mpw-air-campaign-stage-'+run+'.html')
    if stage.is_symlink():
        abort('unsafe stage')
    return stage,BACKUPS/('before-'+run+'.html'),BACKUPS/('receipt-'+run+'.json')


def valid_new(data,new):
    if not 35_000<len(data)<125_000:
        abort('unexpected upgraded game size')
    if sha(data)!=new or any(m not in data for m in MARKERS):
        abort('new content is not approved commercial campaign game')
    if data.count(b'<!doctype html>')!=1 or data.count(b'<script>')!=1:
        abort('unexpected HTML structure')


def atomic(data,mode):
    fd,tmp=tempfile.mkstemp(prefix='.air-campaign-upgrade-',dir=str(DIR))
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,TARGET)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def install(run,new):
    stage,backup,receipt=checked(run,new)
    if not stage.is_file() or backup.exists() or receipt.exists():
        abort('missing stage or existing receipt')
    old=TARGET.read_bytes()
    upgraded=stage.read_bytes()
    if sha(old)!=BEFORE:
        abort('unrecognized or concurrently changed Air Supremacy live HTML')
    valid_new(upgraded,new)
    mode=stat.S_IMODE(TARGET.stat().st_mode)
    BACKUPS.mkdir(mode=0o700,exist_ok=True)
    if BACKUPS.is_symlink():
        abort('unsafe private backup directory')
    with backup.open('xb') as f:
        os.fchmod(f.fileno(),0o600)
        f.write(old);f.flush();os.fsync(f.fileno())
    payload={'run':run,'before':BEFORE,'after':new,'mode':mode,'target':str(TARGET)}
    with receipt.open('x',encoding='utf8') as f:
        os.fchmod(f.fileno(),0o600)
        json.dump(payload,f,sort_keys=True)
        f.flush();os.fsync(f.fileno())
    if sha(TARGET.read_bytes())!=BEFORE:
        abort('concurrent edit before replacement')
    atomic(upgraded,mode)
    if sha(TARGET.read_bytes())!=new:
        abort('postwrite digest mismatch')
    print('AIR_COMMERCIAL_CAMPAIGN_INSTALLED='+new)
    print('AIR_GAME_ONLY_CHANGE=YES')


def record(run,new):
    stage,backup,receipt=checked(run,new)
    if backup.is_symlink() or receipt.is_symlink() or not receipt.is_file() or not backup.is_file():
        abort('missing receipt or backup')
    item=json.loads(receipt.read_text('utf8'))
    if item.get('run')!=run or item.get('before')!=BEFORE or item.get('after')!=new or item.get('target')!=str(TARGET) or sha(backup.read_bytes())!=BEFORE:
        abort('corrupt release receipt')
    return backup,item


def status(run,new):
    _,item=record(run,new)
    if sha(TARGET.read_bytes())!=new:
        abort('post-install status mismatch')
    print('AIR_UPGRADED_GAME_SHA256_VERIFIED='+new)


def rollback(run,new):
    backup,item=record(run,new)
    current=sha(TARGET.read_bytes())
    if current==new:
        atomic(backup.read_bytes(),item['mode'])
    elif current!=BEFORE:
        abort('unrecognized concurrent live modification, refusing overwrite')
    if sha(TARGET.read_bytes())!=BEFORE:
        abort('original file not restored')
    print('AIR_UPGRADE_ROLLBACK_RESTORED=YES')


if __name__=='__main__':
    if len(sys.argv)!=4:
        abort('install|status|rollback RUN SHA')
    op,run,new=sys.argv[1:]
    if op=='install':
        install(run,new)
    elif op=='status':
        status(run,new)
    elif op=='rollback':
        rollback(run,new)
    else:
        abort('unknown operation')
