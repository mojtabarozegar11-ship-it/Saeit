#!/usr/bin/env python3
"""A single exact Air Supremacy route, reversible without touching Crown Defender.

Require the original Crown canonical anchor and exact game bytes installed.
Only insert one new GET path RewriteRule before the Crown canonical route.
Backup the original .htaccess before the edit and refuse concurrent edits.
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
RULES=ROOT/'.htaccess'
GAME=ROOT/'design-preview-20261017/air-supremacy/index.html'
BACKUPS=HOME/'.mpw-air-supremacy-exact-route-backups'
ANCHOR=(
    b'RewriteCond %{REQUEST_METHOD} ^GET$',
    b'RewriteCond %{REQUEST_URI} ^/games/crown-defender/?$',
)
BLOCK=(
    b'# One new standalone Air Supremacy game route (2026-10-23).',
    b'RewriteCond %{REQUEST_METHOD} ^GET$',
    b'RewriteCond %{REQUEST_URI} ^/air-supremacy/?$',
    b'RewriteRule ^.*$ /design-preview-20261017/air-supremacy/index.html [END,QSD]',
)


def stop(s):
    raise RuntimeError('AIR_EXACT_ALIAS_SAFE_ABORT '+s)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def pathcheck(run,game_sha):
    if not re.fullmatch(r'[0-9]{8,16}',run) or not re.fullmatch(r'[0-9a-f]{64}',game_sha):
        stop('Invalid release identifier')
    if any(p.is_symlink() or not p.is_dir() for p in (HOME,ROOT)):
        stop('Unsafe site directory')
    if RULES.is_symlink() or not RULES.is_file():
        stop('Unsafe root rewrite file')
    if GAME.is_symlink() or not GAME.is_file() or sha(GAME.read_bytes())!=game_sha:
        stop('Exact new game file must be present before route installation')
    if BACKUPS.is_symlink():
        stop('Unsafe receipt parent')
    return (BACKUPS/('before-'+run+'.htaccess'),BACKUPS/('receipt-'+run+'.json'))


def rewrite(original):
    if len(original) < 1000 or len(original) > 200000:
        stop('Unexpected root rewrite file size')
    nl=b'\r\n' if b'\r\n' in original else b'\n'
    anchor=nl.join(ANCHOR)
    block=nl.join(BLOCK)+nl
    if original.count(anchor)!=1 or original.count(b'^/air-supremacy/?$')!=0:
        stop('Canonical Crown anchor not unique or new route already installed')
    after=original.replace(anchor,block+anchor,1)
    if after.replace(block,b'',1)!=original or after.count(block)!=1:
        stop('Rewrite edits any other rule')
    return after


def atomic(data,mode):
    fd,path=tempfile.mkstemp(prefix='.air-supremacy-exact-',dir=str(ROOT))
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(path,RULES)
    finally:
        if os.path.exists(path):
            os.unlink(path)


def install(run,game_sha):
    backup,receipt=pathcheck(run,game_sha)
    if any(p.exists() or p.is_symlink() for p in (backup,receipt)):
        stop('Run already installed')
    before=RULES.read_bytes()
    after=rewrite(before)
    previous=sha(before)
    mode=stat.S_IMODE(RULES.stat().st_mode)
    BACKUPS.mkdir(mode=0o700,exist_ok=True)
    if BACKUPS.is_symlink():
        stop('Backup directory symlink')
    with backup.open('xb') as f:
        os.fchmod(f.fileno(),0o600)
        f.write(before)
        f.flush()
        os.fsync(f.fileno())
    with receipt.open('x',encoding='utf-8') as f:
        os.fchmod(f.fileno(),0o600)
        json.dump({'run':run,'game':game_sha,'before':previous,'after':sha(after),'mode':mode},f)
        f.flush()
        os.fsync(f.fileno())
    if sha(RULES.read_bytes())!=previous:
        stop('Concurrent edit before commit')
    atomic(after,mode)
    if sha(RULES.read_bytes())!=sha(after):
        stop('New rewrite file not byte-identical')
    print('AIR_SUPREMACY_EXACT_ALIAS_INSTALLED=YES')
    print('AIR_ORIGINAL_HTACCESS_SHA256='+previous)
    print('AIR_NEW_HTACCESS_SHA256='+sha(after))


def recover(run,game_sha,restore):
    if not re.fullmatch(r'[0-9]{8,16}',run) or not re.fullmatch(r'[0-9a-f]{64}',game_sha):
        stop('Invalid release identifier')
    backup=BACKUPS/('before-'+run+'.htaccess')
    receipt=BACKUPS/('receipt-'+run+'.json')
    if not receipt.exists():
        if restore and RULES.is_file() and b'^/air-supremacy/?$' not in RULES.read_bytes():
            print('AIR_ALIAS_NOT_APPLIED_NO_ROLLBACK_NEEDED')
            return
        stop('Missing rewrite receipt')
    if RULES.is_symlink() or backup.is_symlink() or receipt.is_symlink():
        stop('Unsafe receipt or route')
    data=json.loads(receipt.read_text(encoding='utf-8'))
    if data.get('run')!=run or data.get('game')!=game_sha:
        stop('Receipt release mismatch')
    previous=backup.read_bytes()
    if sha(previous)!=data['before'] or sha(rewrite(previous))!=data['after']:
        stop('Corrupt or rewritten snapshot')
    current=sha(RULES.read_bytes())
    if restore:
        if current==data['after']:
            atomic(previous,data['mode'])
        elif current!=data['before']:
            stop('Unrecognized concurrent root rewrite change')
        if sha(RULES.read_bytes())!=data['before']:
            stop('Rollback hash mismatch')
        print('AIR_SUPREMACY_EXACT_ALIAS_RESTORED=YES')
    else:
        if current!=data['after']:
            stop('Exact alias not installed')
        print('AIR_SUPREMACY_EXACT_ALIAS_STATUS=PASS')


if __name__=='__main__':
    if len(sys.argv)!=4 or sys.argv[1] not in ('install','status','rollback'):
        stop('install|status|rollback RUN SHA')
    mode,run,game_sha=sys.argv[1:]
    if mode=='install':
        install(run,game_sha)
    else:
        recover(run,game_sha,mode=='rollback')
