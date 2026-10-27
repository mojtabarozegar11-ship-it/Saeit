#!/usr/bin/env python3
"""Narrow, hash-guarded reversible web-client update for the existing game route."""
from pathlib import Path
import hashlib, json, os, re, sys

ROOT=Path('/home/zomorod2/public_html')
ROW='ZM-R25'; GAME_ID='ZM-R25-GAME-RAMADAN-WAR-20261022'; GAME=ROOT/'ramadan-war'
MARK='ZM-RAMADAN-WAR-WEB-CARD-20261022'
ASSETS=['index.html','game.js','save-validation.mjs','input-guard.mjs','missile-targets.mjs','enemy-action-policy.mjs','upgrade-policy.mjs','moj1-commerce-policy.mjs','game.css','engine3d.js','three.module.js','three.core.min.js','THREE-LICENSE.txt','ASSET-CREDITS.md','weapon-overlay.webp','soldier-enemy.webp','stone-wall.webp','scene-desert.webp','scene-sniper-desert-v2.webp','scene-night.webp','scene-airbase.webp','soldier-rigged-ccby.glb','m24-sniper-ccby.glb','arms_basecolor.webp','arms_normal.webp','three-addons/loaders/GLTFLoader.js','three-addons/utils/BufferGeometryUtils.js','three-addons/utils/SkeletonUtils.js','three-addons/libs/meshopt_decoder.module.js']

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
    assert not tmp.exists() and not tmp.is_symlink(),f'temporary path exists: {tmp}'
    tmp.write_bytes(data);os.chmod(tmp,0o644)
    assert digest(tmp.read_bytes())==digest(data)
    os.replace(tmp,path)
def metadata(stage): return json.loads((stage/'release.json').read_text('utf-8'))
def store(stage,value):
    p=stage/'release.json.tmp';p.write_text(json.dumps(value,sort_keys=True),encoding='utf-8');os.replace(p,stage/'release.json')
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
    assert b'./save-validation.mjs' in new['game.js'] and b'validateCampaignSave' in new['save-validation.mjs']
    assert b'./input-guard.mjs' in new['game.js'] and b'keyboardAction' in new['input-guard.mjs']
    assert b'./missile-targets.mjs' in new['game.js'] and b'removeEnemyAndRetargetMissiles' in new['missile-targets.mjs']
    assert b'./enemy-action-policy.mjs' in new['game.js'] and b'canEnemyAct' in new['enemy-action-policy.mjs']
    assert b'./upgrade-policy.mjs' in new['game.js'] and b'applyEarnedUpgrade' in new['upgrade-policy.mjs']
    assert b'./moj1-commerce-policy.mjs' in new['game.js'] and b'checkoutEnabled:false' in new['moj1-commerce-policy.mjs']
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

def publish(stage,run):
    m=metadata(stage);assert m['phase']=='prepared';live_card_check()
    for name,h in m['old'].items():assert digest((GAME/name).read_bytes())==h,'game file changed concurrently: '+name
    for name in set(m['new'])-set(m['old']):assert not (GAME/name).exists() and not (GAME/name).is_symlink(),'new asset appeared concurrently: '+name
    assert digest((GAME/'.htaccess').read_bytes())==m['route'],'game route config changed concurrently'
    for name in m['new']:
        data=(stage/f'incoming/{name}').read_bytes();assert digest(data)==m['new'][name]
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
    # Preflight the ENTIRE rollback before changing any bytes. If even one
    # backup is corrupt, deleting newly staged modules would leave the new
    # game.js importing missing files. Concurrent edits also abort the whole
    # rollback rather than creating a mixed-version client.
    if set(m['new'])!=set(ASSETS) or not set(m['old']).issubset(set(ASSETS)) or GAME.is_symlink() or stage.is_symlink():
        print('ROLLBACK_ABORT_INVALID_MANIFEST');return False
    restore=[];remove=[]
    for name,new_hash in m['new'].items():
        p=GAME/name
        parent=p.parent
        if not p.is_relative_to(GAME) or p.is_symlink():
            print('ROLLBACK_ABORT_UNSAFE_PATH='+name);return False
        while parent!=GAME:
            if parent.is_symlink():
                print('ROLLBACK_ABORT_UNSAFE_PARENT='+name);return False
            parent=parent.parent
        if name in m['old']:
            if not p.is_file():
                print('ROLLBACK_ABORT_MISSING_LIVE_FILE='+name);return False
            current=digest(p.read_bytes())
            if current==m['old'][name]:
                continue  # Already restored by an earlier partial rollback.
            if current!=new_hash:
                print('ROLLBACK_ABORT_CONCURRENT_EDIT='+name);return False
            backup=stage/f'old-{name}'
            if not backup.is_relative_to(stage) or not backup.is_file() or backup.is_symlink():
                print('ROLLBACK_ABORT_INVALID_BACKUP='+name);return False
            backup_parent=backup.parent
            while backup_parent!=stage:
                if backup_parent.is_symlink():
                    print('ROLLBACK_ABORT_UNSAFE_BACKUP_PARENT='+name);return False
                backup_parent=backup_parent.parent
            original=backup.read_bytes()
            if digest(original)!=m['old'][name]:
                print('ROLLBACK_ABORT_INVALID_BACKUP='+name);return False
            # A leftover temporary file would make atomic() fail halfway through
            # a multi-file rollback. Reject it before restoring any asset.
            tmp=p.with_name('.'+p.name+'.ramadan-'+run)
            if tmp.exists() or tmp.is_symlink():
                print('ROLLBACK_ABORT_TEMP_PATH_COLLISION='+name);return False
            restore.append((name,p,original))
        elif p.exists():
            if not p.is_file() or digest(p.read_bytes())!=new_hash:
                print('ROLLBACK_ABORT_CONCURRENT_NEW_ASSET='+name);return False
            remove.append((name,p))
    for name,p,original in restore:
        atomic(p,original,run)
        print('RESTORED_OLD_GAME_FILE='+name)
    for name,p in remove:
        p.unlink()
        print('REMOVED_NEW_GAME_ASSET='+name)
    return True

def rollback(stage,run):
    if not (stage/'release.json').is_file():print('ROLLBACK_SKIPPED_NO_RELEASE_STATE');return
    m=metadata(stage)
    if rollback_files(stage,m,run):
        print('OLD_GAME_CLIENT_RESTORED; HOMEPAGE_CARD_UNCHANGED')
    else:
        print('ROLLBACK_INCOMPLETE_MANUAL_REVIEW_REQUIRED')

def main():
    assert len(sys.argv)==3,'usage: deploy.py prepare|publish|verify|rollback RUN_ID'
    action,run=sys.argv[1:];assert re.fullmatch(r'[0-9]{4,15}',run)
    stage=Path('/home/zomorod2/.zm-ramadan-war-'+run);assert stage.is_dir() and not stage.is_symlink()
    funcs={'prepare':lambda:prepare(stage),'publish':lambda:publish(stage,run),'verify':lambda:verify(stage),'rollback':lambda:rollback(stage,run)}
    assert action in funcs;funcs[action]()
if __name__=='__main__':main()
