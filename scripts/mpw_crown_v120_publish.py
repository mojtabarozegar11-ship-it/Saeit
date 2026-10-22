#!/usr/bin/env python3
"""Game-only, atomically reversible Crown Defender easy-100-lives balance release.

Scope: /home/zomorod2/mojplaywin.com/design-preview-20261017/mpw-crown-defender-20261019/index.html.
Does not edit rewrite rules, the Studio page, Django, store, cPanel settings or any subsite.
"""
from pathlib import Path
import hashlib, json, os, re, stat, sys, tempfile
HOME=Path('/home/zomorod2')
GAME=HOME/'mojplaywin.com/design-preview-20261017/mpw-crown-defender-20261019/index.html'
BACKUPS=HOME/'.mpw-crown-v120-snapshots'
PREVIOUS_SHA='6f4ba27c68a2bb5f414d94a52883c12e916762c69bc1cd8a418b1ea188fc5232'
MARKERS=(b'Crown Defender V120',b'Jet Dominion',b'id="game"',b'id="start"',b'id="pause"',b'id="shopPane"',b'id="energy"',b'id="emp"',b'id="portraitOverdrive"',b'id="portraitChrono"',b'Boss Rush',b'width="540" height="960"',b'window.__mpwCrownDefenderTest')

def digest(raw):return hashlib.sha256(raw).hexdigest()
def stop(msg):raise RuntimeError('CROWN_V120_SAFE_ABORT: '+msg)
def regular(path):
    if not path.is_file() or path.is_symlink():stop('Missing regular file '+str(path))
def verify_payload(raw):
    if not 35000<=len(raw)<=160000:stop('Unexpected V120 game size')
    if raw.count(b'<!doctype html>')!=1 or raw.count(b'<script>')!=1:stop('Game document shape changed')
    if any(marker not in raw for marker in MARKERS):stop('V120 feature markers missing')
    if b'<iframe' in raw or b'<form' in raw or b'https://cdn.' in raw:stop('Unexpected third-party dependency')
    return digest(raw)
def runpaths(run):
    if not re.fullmatch(r'[0-9]{8,16}',run):stop('Invalid GitHub run number')
    return (HOME/('.mpw-crown-game-stage-'+run+'.html'),BACKUPS/('before-jet120-'+run+'.html'),BACKUPS/('jet120-'+run+'.json'))
def write_atomic(path,raw,mode):
    if path.is_symlink():stop('Symlink denied '+str(path))
    fd,temp=tempfile.mkstemp(dir=str(path.parent),prefix='.crown-v120-')
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)
def install(run,newsha):
    stage,backup,manifest=runpaths(run)
    if not re.fullmatch(r'[a-f0-9]{64}',newsha):stop('Invalid expected SHA')
    regular(GAME);regular(stage)
    if BACKUPS.is_symlink() or any(p.is_symlink() for p in (GAME.parent,GAME.parent.parent,GAME.parent.parent.parent)):
        stop('Unsafe parent path')
    if backup.exists() or manifest.exists():stop('Run backup already exists')
    old=GAME.read_bytes();new=stage.read_bytes()
    if digest(old)!=PREVIOUS_SHA:stop('Unexpected live V120 SHA; concurrent edit or different version')
    if verify_payload(new)!=newsha:stop('Staged V120 source differs from approved GitHub SHA')
    BACKUPS.mkdir(mode=0o700,exist_ok=True)
    if BACKUPS.is_symlink():stop('Unsafe backup storage')
    mode=stat.S_IMODE(GAME.stat().st_mode)
    with backup.open('xb') as f:
        os.fchmod(f.fileno(),0o600);f.write(old);f.flush();os.fsync(f.fileno())
    data={'run':run,'before':PREVIOUS_SHA,'after':newsha,'before_bytes':len(old),'after_bytes':len(new),'target':str(GAME),'mode':mode}
    write_atomic(manifest,json.dumps(data,sort_keys=True).encode('utf-8'),0o600)
    if digest(GAME.read_bytes())!=PREVIOUS_SHA:stop('Concurrent game change detected before write')
    try:
        write_atomic(GAME,new,mode)
        if digest(GAME.read_bytes())!=newsha:stop('V120 write failed hash verification')
    except BaseException:
        if digest(GAME.read_bytes())==newsha:write_atomic(GAME,old,mode)
        raise
    print(json.dumps({'status':'CROWN_V120_GAME_ONLY_INSTALLED','bytes':len(new),'old_sha':PREVIOUS_SHA,'new_sha':newsha,'backup_saved':str(backup),'no_other_files_edited':True}))
def status(run):
    stage,backup,manifest=runpaths(run)
    regular(manifest);regular(backup);regular(GAME)
    obj=json.loads(manifest.read_text('utf-8'))
    verified=digest(GAME.read_bytes())==obj['after'] and digest(backup.read_bytes())==obj['before']
    print(json.dumps({'status':'CROWN_V120_READONLY_STATUS','verified':verified,'current':digest(GAME.read_bytes()),'backup':backup.is_file()}))
    if not verified:stop('Status not verified')
def rollback(run):
    stage,backup,manifest=runpaths(run)
    regular(manifest);regular(backup);regular(GAME)
    obj=json.loads(manifest.read_text('utf-8'))
    old=backup.read_bytes()
    if digest(old)!=obj['before']:stop('Rollback backup corrupt')
    current=digest(GAME.read_bytes())
    if current not in (obj['after'],obj['before']):stop('Concurrent change, refuse rollback')
    if current==obj['after']:write_atomic(GAME,old,obj['mode'])
    print(json.dumps({'status':'CROWN_V120_ROLLED_BACK_GAME_ONLY','verified':digest(GAME.read_bytes())==obj['before']}))
if __name__=='__main__':
    if len(sys.argv)<3:stop('Usage install RUN SHA | status RUN | rollback RUN')
    action,run=sys.argv[1:3]
    if action=='install' and len(sys.argv)==4:install(run,sys.argv[3])
    elif action=='status' and len(sys.argv)==3:status(run)
    elif action=='rollback' and len(sys.argv)==3:rollback(run)
    else:stop('Unsupported command')