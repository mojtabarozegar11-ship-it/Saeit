#!/usr/bin/env python3
"""Game-only, atomically reversible Crown Defender easy-100-lives balance release.

Scope: /home/zomorod2/mojplaywin.com/design-preview-20261017/mpw-crown-defender-20261019/index.html.
Does not edit rewrite rules, the Studio page, Django, store, cPanel settings or any subsite.
"""
from pathlib import Path
import hashlib, json, os, re, stat, sys, tempfile
HOME=Path('/home/zomorod2')
GAME=HOME/'mojplaywin.com/design-preview-20261017/mpw-crown-defender-20261019/index.html'
BACKUPS=HOME/'.mpw-crown-air-snapshots'
PREVIOUS_SHA='fc5b05020610b656721b247c61ac406d7adf8b98e1f68b224b1b7e723a4762b7'
MARKERS=(b'Crown Defender',b'Air Supremacy',b'id="game"',b'id="start"',b'id="pause"',b'id="shopPane"',b'id="energy"',b'id="emp"',b'id="portraitOverdrive"',b'id="portraitChrono"',b'Boss Rush',b'width="540" height="960"',b'window.__mpwCrownDefenderTest')

ASSET_DIR=HOME/'mojplaywin.com/mpw-crown-air-assets-20261022'
ASSET_HASHES={'falcon.webp': '1544eb43552ff652c308ac86a25f77c1dbf94ae2887886180af929236921a969', 'flagship.webp': 'ef2cb31fda2ca4ae62701f878629b9e8e16155dce9fc6006886849d9b9863a53', 'island-fortress.webp': 'a8264d50b15f761686a54200182cd33e83699c3702d475d8582d35bb35e33010', 'manta.webp': 'f7f684ee5c985a6bdd8530784ffa6612ea1868b9ac2b1ab5bfaf85d531f26aaf', 'phoenix.webp': '0178f1cf9cd22f6c0baf90e39f906bb4a5983ded16b3ecbbad1aa8a7c84f7c39', 'raptor.webp': '56bb00cec7ffd525d718cb1ebd23a398391ed872e8a5ff873bf3687214aee080', 'sovereign.webp': '172c09629aa9996cf73bb81dffae801ec79a55bc786151b4dc0c17b24dcc96b4', 'spectre.webp': '89c1e3007256c2769051baaef26f32d9e1a291094d27d518451a03ce0827a2b4', 'tempest.webp': 'b4cccd8b8a55f3e213534db4bd6b69b8847331e041fc1ddcc88e002246f96a5c', 'valkyrie.webp': '04f76b6ffa5be275da1194c38bd568716b163b36557d69399869248ddfbf8d35'}

def digest(raw):return hashlib.sha256(raw).hexdigest()
def stop(msg):raise RuntimeError('CROWN_AIR_SAFE_ABORT: '+msg)
def regular(path):
    if not path.is_file() or path.is_symlink():stop('Missing regular file '+str(path))
def verify_payload(raw):
    if not 35000<=len(raw)<=160000:stop('Unexpected AIR game size')
    if raw.count(b'<!doctype html>')!=1 or raw.count(b'<script>')!=1:stop('Game document shape changed')
    if any(marker not in raw for marker in MARKERS):stop('AIR feature markers missing')
    if b'<iframe' in raw or b'<form' in raw or b'https://cdn.' in raw:stop('Unexpected third-party dependency')
    return digest(raw)
def runpaths(run):
    if not re.fullmatch(r'[0-9]{8,16}',run):stop('Invalid GitHub run number')
    return (HOME/('.mpw-crown-game-stage-'+run+'.html'),BACKUPS/('before-air-'+run+'.html'),BACKUPS/('air-'+run+'.json'))
def write_atomic(path,raw,mode):
    if path.is_symlink():stop('Symlink denied '+str(path))
    fd,temp=tempfile.mkstemp(dir=str(path.parent),prefix='.crown-air-')
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as f:
            f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)
def remove_assets():
    if not ASSET_DIR.exists():return
    if ASSET_DIR.is_symlink() or not ASSET_DIR.is_dir():stop('Unsafe assets path')
    present={p.name for p in ASSET_DIR.iterdir()}
    if not present.issubset(ASSET_HASHES):stop('Unexpected asset directory content')
    for name in present:
        path=ASSET_DIR/name;regular(path)
        if digest(path.read_bytes())!=ASSET_HASHES[name]:stop('Changed asset; refuse removal')
    for name in present:(ASSET_DIR/name).unlink()
    ASSET_DIR.rmdir()

def install(run,newsha):
    stage,backup,manifest=runpaths(run)
    if not re.fullmatch(r'[a-f0-9]{64}',newsha):stop('Invalid expected SHA')
    regular(GAME);regular(stage)
    if BACKUPS.is_symlink() or any(p.is_symlink() for p in (GAME.parent,GAME.parent.parent,GAME.parent.parent.parent)):
        stop('Unsafe parent path')
    if backup.exists() or manifest.exists():stop('Run backup already exists')
    old=GAME.read_bytes();new=stage.read_bytes()
    if digest(old)!=PREVIOUS_SHA:stop('Unexpected live AIR SHA; concurrent edit or different version')
    if verify_payload(new)!=newsha:stop('Staged AIR source differs from approved GitHub SHA')
    stage_assets=HOME/('.mpw-crown-air-assets-stage-'+run)
    if not stage_assets.is_dir() or stage_assets.is_symlink():stop('Missing asset staging directory')
    if ASSET_DIR.exists() or ASSET_DIR.is_symlink():stop('Asset version already exists; inspect before retry')
    for name,expected in ASSET_HASHES.items():
        asset=stage_assets/name;regular(asset)
        if digest(asset.read_bytes())!=expected:stop('Asset hash mismatch')
    BACKUPS.mkdir(mode=0o700,exist_ok=True)
    if BACKUPS.is_symlink():stop('Unsafe backup storage')
    mode=stat.S_IMODE(GAME.stat().st_mode)
    with backup.open('xb') as f:
        os.fchmod(f.fileno(),0o600);f.write(old);f.flush();os.fsync(f.fileno())
    data={'run':run,'before':PREVIOUS_SHA,'after':newsha,'before_bytes':len(old),'after_bytes':len(new),'target':str(GAME),'mode':mode}
    write_atomic(manifest,json.dumps(data,sort_keys=True).encode('utf-8'),0o600)
    if digest(GAME.read_bytes())!=PREVIOUS_SHA:stop('Concurrent game change detected before write')
    try:
        ASSET_DIR.mkdir(mode=0o755)
        for name in ASSET_HASHES:write_atomic(ASSET_DIR/name,(stage_assets/name).read_bytes(),0o644)
        write_atomic(GAME,new,mode)
        if digest(GAME.read_bytes())!=newsha:stop('AIR write failed hash verification')
    except BaseException:
        if digest(GAME.read_bytes())==newsha:write_atomic(GAME,old,mode)
        remove_assets()
        raise
    print(json.dumps({'status':'CROWN_AIR_GAME_ONLY_INSTALLED','bytes':len(new),'old_sha':PREVIOUS_SHA,'new_sha':newsha,'backup_saved':str(backup),'only_game_and_versioned_assets_edited':True}))
def status(run):
    stage,backup,manifest=runpaths(run)
    regular(manifest);regular(backup);regular(GAME)
    obj=json.loads(manifest.read_text('utf-8'))
    verified=digest(GAME.read_bytes())==obj['after'] and digest(backup.read_bytes())==obj['before']
    print(json.dumps({'status':'CROWN_AIR_READONLY_STATUS','verified':verified,'current':digest(GAME.read_bytes()),'backup':backup.is_file()}))
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
    remove_assets()
    print(json.dumps({'status':'CROWN_AIR_ROLLED_BACK_GAME_ONLY','verified':digest(GAME.read_bytes())==obj['before']}))
if __name__=='__main__':
    if len(sys.argv)<3:stop('Usage install RUN SHA | status RUN | rollback RUN')
    action,run=sys.argv[1:3]
    if action=='install' and len(sys.argv)==4:install(run,sys.argv[3])
    elif action=='status' and len(sys.argv)==3:status(run)
    elif action=='rollback' and len(sys.argv)==3:rollback(run)
    else:stop('Unsupported command')