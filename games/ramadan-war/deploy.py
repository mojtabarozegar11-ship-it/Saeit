#!/usr/bin/env python3
"""Narrow, hash-guarded reversible web-client update for the existing game route."""
from pathlib import Path
import hashlib, json, os, re, sys

ROOT=Path('/home/zomorod2/public_html')
ROW='ZM-R25'; GAME_ID='ZM-R25-GAME-RAMADAN-WAR-20261022'; GAME=ROOT/'ramadan-war'
MARK='ZM-RAMADAN-WAR-WEB-CARD-20261022'
ASSETS=['index.html','game.js','game.css','upgrade-policy.mjs','moj1-commerce-policy.mjs','input-guard.mjs','missile-targets.mjs','enemy-action-policy.mjs','save-validation.mjs','engine3d.js','three.module.js','three.core.min.js','THREE-LICENSE.txt','ASSET-CREDITS.md','weapon-overlay.webp','soldier-enemy.webp','stone-wall.webp','scene-desert.webp','scene-sniper-desert-v2.webp','scene-night.webp','scene-airbase.webp','soldier-rigged-ccby.glb','m24-sniper-ccby.glb','arms_basecolor.webp','arms_normal.webp','three-addons/loaders/GLTFLoader.js','three-addons/utils/BufferGeometryUtils.js','three-addons/utils/SkeletonUtils.js','three-addons/libs/meshopt_decoder.module.js']

def digest(data): return hashlib.sha256(data).hexdigest()
def atomic(path,data,run):
    assert path.is_relative_to(GAME),f'write outside game route refused: {path}'
    assert not path.is_symlink(),f'symlink refused: {path}'
    parent=path.parent
    while parent!=GAME:
        assert not parent.is_symlink(),f'symlink directory refused: {parent}'
        parent=parent.parent
    assert not GAME.is_symlink(),f'symlink directory refused: {GAME}'
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name('.'+path.name+'.ramadan-'+run)
    # O_EXCL makes temporary-file creation atomic: a concurrent publisher
    # cannot insert a symlink/file between a preflight check and write_bytes.
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0)
    try:
        fd=os.open(tmp,flags,0o644)
    except FileExistsError as exc:
        raise AssertionError(f'temporary path exists: {tmp}') from exc
    identity=(os.fstat(fd).st_dev,os.fstat(fd).st_ino)
    try:
        with os.fdopen(fd,'wb') as output:
            os.fchmod(output.fileno(),0o644)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        assert not tmp.is_symlink(),f'temporary path linked: {tmp}'
        assert digest(tmp.read_bytes())==digest(data)
        os.replace(tmp,path)
    except BaseException:
        # A failed write must not strand a partial payload on a full disk.
        # Never delete an unrelated writer's pre-existing/replaced temp file.
        try:
            if not tmp.is_symlink():
                current=tmp.stat()
                if (current.st_dev,current.st_ino)==identity:
                    tmp.unlink()
        except FileNotFoundError:
            pass
        raise
def metadata(stage): return json.loads((stage/'release.json').read_text('utf-8'))
def store(stage,value):
    # Release metadata is security-critical: refuse a planted temporary link
    # rather than following it with Path.write_text on the cPanel host.
    assert stage.is_dir() and not stage.is_symlink()
    p=stage/'release.json.tmp'
    target=stage/'release.json'
    assert not target.is_symlink(),'linked release state refused'
    payload=json.dumps(value,sort_keys=True).encode('utf-8')
    flags=os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0)
    try:
        fd=os.open(p,flags,0o600)
    except FileExistsError as exc:
        raise RuntimeError('release state temporary file already exists') from exc
    identity=(os.fstat(fd).st_dev,os.fstat(fd).st_ino)
    try:
        with os.fdopen(fd,'wb') as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(p,target)
    except BaseException:
        try:
            if not p.is_symlink():
                current=p.stat()
                if (current.st_dev,current.st_ino)==identity:
                    p.unlink()
        except FileNotFoundError:
            pass
        raise
def live_card_check():
    home=ROOT/'index.html';assert home.is_file() and not home.is_symlink()
    text=home.read_text('utf-8');m=re.search(r'window\.ZOMOROD_ORBIT_DATA=(\{.*?\});</script>',text,re.S)
    assert m,'live homepage manifest unavailable'
    data=json.loads(m.group(1));rows=[r for r in data.get('rows',[]) if r.get('id')==ROW]
    assert len(rows)==1;row=rows[0]
    assert row.get('title')=='فناوری اطلاعات و خدمات دیجیتال' and row.get('index')==25
    cards=row.get('cards',[])
    assert len(cards)>=24 and cards[0].get('id')=='ZM-R25-GAME-FARM-DOMINION-20261019'
    assert cards[1].get('id')==GAME_ID and cards[1].get('canonicalUrl')=='/ramadan-war/'
    assert cards[2].get('id')=='ZM-R25-GAME-ARROW-ESCAPE-20261022' and cards[2].get('canonicalUrl')=='/arrow-escape/'
    assert cards[3].get('slug')=='website-design'
    return home

def prepare(stage):
    assert ROOT.is_dir() and not ROOT.is_symlink() and GAME.is_dir() and not GAME.is_symlink()
    home=live_card_check()
    inputs={name:(stage/f'incoming/{name}') for name in ASSETS+['.htaccess']}
    assert all(p.is_file() and not p.is_symlink() for p in inputs.values())
    assert inputs['.htaccess'].read_text('utf-8')=='PassengerEnabled off\nDirectoryIndex index.html\n'
    new={name:inputs[name].read_bytes() for name in ASSETS}
    assert len(new['index.html'])>1000 and MARK.encode() in new['index.html']
    assert b'RamadanWarDebug' in new['game.js'] and b'createEngine' in new['game.js'] and b'./game.js' in new['index.html'] and b'./game.css' in new['index.html']
    assert b'./input-guard.mjs' in new['game.js']
    assert b'./save-validation.mjs' in new['game.js']
    assert all(('./'+name).encode() in new['game.js'] for name in ['upgrade-policy.mjs','moj1-commerce-policy.mjs','missile-targets.mjs','enemy-action-policy.mjs','save-validation.mjs'])
    assert b'./engine3d.js' in new['game.js'] and b'./three.module.js' in new['engine3d.js'] and b'./three.core.min.js' in new['three.module.js'] and len(new['three.module.js'])>300000 and len(new['three.core.min.js'])>300000
    assert b'The MIT License' in new['THREE-LICENSE.txt']
    assert b'CC BY 4.0' in new['ASSET-CREDITS.md'] and b'BAMEN' in new['ASSET-CREDITS.md'] and b'Naudaff3D' in new['ASSET-CREDITS.md']
    assert all(len(new[n])>50000 for n in ['weapon-overlay.webp','soldier-enemy.webp','stone-wall.webp','scene-desert.webp','scene-sniper-desert-v2.webp','scene-night.webp','scene-airbase.webp'])
    assert len(new['soldier-rigged-ccby.glb'])>1000000 and len(new['m24-sniper-ccby.glb'])>500000
    assert len(new['arms_basecolor.webp'])>50000 and len(new['arms_normal.webp'])>50000
    assert all(len(new[n])>10000 for n in ['three-addons/loaders/GLTFLoader.js','three-addons/utils/SkeletonUtils.js','three-addons/utils/BufferGeometryUtils.js'])
    assert len(new['three-addons/libs/meshopt_decoder.module.js'])>20000
    assert b'weapon-overlay.webp' in new['index.html'] and b'soldier-enemy.webp' in new['engine3d.js'] and b'missionBackdrop' in new['index.html'] and b'scene-sniper-desert-v2.webp' in new['game.js'] and b'alpha:true' in new['engine3d.js']
    assert b'GLTFLoader' in new['engine3d.js'] and b'soldier-rigged-ccby.glb' in new['engine3d.js'] and b'm24-sniper-ccby.glb' in new['engine3d.js'] and b'MeshoptDecoder' in new['engine3d.js']
    assert (GAME/'.htaccess').is_file() and (GAME/'.htaccess').read_bytes()==inputs['.htaccess'].read_bytes()
    old={name:(GAME/name).read_bytes() for name in ASSETS if (GAME/name).is_file() and not (GAME/name).is_symlink()}
    assert all(name in old for name in ['index.html','game.js','game.css','engine3d.js','three.module.js','three.core.min.js','THREE-LICENSE.txt'])
    for name in set(new)-set(old):
        assert not (GAME/name).exists() and not (GAME/name).is_symlink(),f'new asset already exists: {name}'
    assert MARK.encode() in old['index.html'] and b'RamadanWarDebug' in old['game.js']
    assert all((GAME/name).is_file() and not (GAME/name).is_symlink() for name in old)
    protected={}
    for rel in ['.htaccess','agriculture/index.html','research/index.html','store/index.html']:
        p=ROOT/rel
        if p.is_file() and not p.is_symlink():protected[rel]=digest(p.read_bytes())
    assert len(protected)>=2,'insufficient protected-page baseline'
    for name,data in old.items():
        backup=stage/f'old-{name}'
        assert backup.is_relative_to(stage) and not backup.is_symlink()
        backup.parent.mkdir(parents=True,exist_ok=True)
        backup.write_bytes(data)
        assert digest(backup.read_bytes())==digest(data)
    (stage/'old-home-hash.txt').write_text(digest(home.read_bytes()),encoding='ascii')
    store(stage,{'phase':'prepared','old':{k:digest(v) for k,v in old.items()},'new':{k:digest(v) for k,v in new.items()},'route':digest(inputs['.htaccess'].read_bytes()),'protected':protected})
    print('RAMADAN_WEB_PREPARE=PASS current-card-two-confirmed; old-client-backed-up')

def ensure_publish_capacity(stage, payload_bytes, reserve_bytes=128*1024*1024,
                            statvfs=os.statvfs):
    """Recheck free space immediately before any live file replacement.

    The earlier SSH preflight is not enough if another process fills the disk
    during transfer or backup. Leave headroom for atomic writes and rollback.
    """
    assert stage.is_dir() and not stage.is_symlink()
    assert GAME.is_dir() and not GAME.is_symlink()
    assert isinstance(payload_bytes,int) and payload_bytes>0
    game_fs=statvfs(GAME)
    if game_fs.f_bavail*game_fs.f_frsize < reserve_bytes+2*payload_bytes:
        raise RuntimeError('live game storage fell below safe publish reserve')
    if stage.stat().st_dev != GAME.stat().st_dev:
        stage_fs=statvfs(stage)
        if stage_fs.f_bavail*stage_fs.f_frsize < reserve_bytes:
            raise RuntimeError('staging storage fell below safe rollback reserve')


def publish(stage,run):
    m=metadata(stage);assert m['phase']=='prepared';live_card_check()
    for name,h in m['old'].items():assert digest((GAME/name).read_bytes())==h,'game file changed concurrently: '+name
    for name in set(m['new'])-set(m['old']):assert not (GAME/name).exists() and not (GAME/name).is_symlink(),'new asset appeared concurrently: '+name
    assert digest((GAME/'.htaccess').read_bytes())==m['route'],'game route config changed concurrently'
    for name in m['new']:
        data=(stage/f'incoming/{name}').read_bytes();assert digest(data)==m['new'][name]
    ensure_publish_capacity(stage,sum((stage/f'incoming/{name}').stat().st_size for name in ASSETS))
    try:
        for name in [asset for asset in ASSETS if asset!='index.html']+['index.html']:
            atomic(GAME/name,(stage/f'incoming/{name}').read_bytes(),run)
            assert digest((GAME/name).read_bytes())==m['new'][name]
        m['phase']='published';store(stage,m)
        print('RAMADAN_WEB_CLIENT_UPDATED=PASS; route and card position preserved')
    except BaseException:
        rollback_files(stage,m,run)
        raise

def verify(stage):
    m=metadata(stage);assert m['phase']=='published';live_card_check()
    for name,h in m['new'].items():assert digest((GAME/name).read_bytes())==h,'new game file hash mismatch: '+name
    assert digest((GAME/'.htaccess').read_bytes())==m['route']
    for rel,h in m['protected'].items():assert digest((ROOT/rel).read_bytes())==h,'protected file changed: '+rel
    print('RAMADAN_WEB_CLIENT_AND_PROTECTED_PAGES=PASS')

def rollback_files(stage,m,run):
    """Restore only known release assets; fail if any file cannot be restored.

    An already-restored old asset or an absent new-only asset is safe for
    idempotent retries. Unexpected concurrent writes must remain untouched,
    but MUST NOT be reported as a successful rollback.
    """
    problems=[]
    for name,h in m['new'].items():
        if name not in ASSETS:
            problems.append('unsafe release asset: '+str(name))
            continue
        p=GAME/name
        parts=Path(name).parts
        if (GAME.is_symlink() or any((GAME.joinpath(*parts[:n])).is_symlink()
                                     for n in range(1,len(parts)+1))):
            problems.append('linked release asset parent: '+name)
            continue
        if name in m['old']:
            if p.is_file() and not p.is_symlink():
                current=digest(p.read_bytes())
                if current==m['old'][name]:
                    continue  # Idempotent: already restored or never published.
                if current==h:
                    backup=stage/f'old-{name}'
                    backup_parts=Path('old-'+name).parts
                    linked=any((stage.joinpath(*backup_parts[:n])).is_symlink()
                               for n in range(1,len(backup_parts)+1))
                    if (not backup.is_file() or linked or
                            not backup.resolve().is_relative_to(stage.resolve())):
                        problems.append('rollback backup missing or linked: '+name)
                        continue
                    data=backup.read_bytes()
                    if digest(data)!=m['old'][name]:
                        problems.append('rollback backup SHA-256 mismatch: '+name)
                        continue
                    atomic(p,data,run)
                    if digest(p.read_bytes())!=m['old'][name]:
                        problems.append('rollback restored SHA-256 mismatch: '+name)
                    else:
                        print('RESTORED_OLD_GAME_FILE='+name)
                    continue
            problems.append('rollback conflict, original asset not restored: '+name)
        else:
            if not p.exists() and not p.is_symlink():
                continue  # Idempotent: new-only asset already absent.
            if p.is_file() and not p.is_symlink() and digest(p.read_bytes())==h:
                p.unlink()
                print('REMOVED_NEW_GAME_ASSET='+name)
            else:
                problems.append('rollback conflict, new asset not removed: '+name)
    if problems:
        raise RuntimeError('rollback incomplete: '+'; '.join(problems))

def rollback(stage,run):
    if not (stage/'release.json').is_file():print('ROLLBACK_SKIPPED_NO_RELEASE_STATE');return
    m=metadata(stage);rollback_files(stage,m,run)
    print('OLD_GAME_CLIENT_RESTORED; HOMEPAGE_CARD_UNCHANGED')

def main():
    assert len(sys.argv)==3,'usage: deploy.py prepare|publish|verify|rollback RUN_ID'
    action,run=sys.argv[1:];assert re.fullmatch(r'[0-9]{4,15}',run)
    stage=Path('/home/zomorod2/.zm-ramadan-war-'+run);assert stage.is_dir() and not stage.is_symlink()
    funcs={'prepare':lambda:prepare(stage),'publish':lambda:publish(stage,run),'verify':lambda:verify(stage),'rollback':lambda:rollback(stage,run)}
    assert action in funcs;funcs[action]()
if __name__=='__main__':main()
