#!/usr/bin/env python3
"""Narrow, hash-guarded reversible web-client update for the existing game route."""
from pathlib import Path
import hashlib, json, os, re, sys

ROOT=Path('/home/zomorod2/public_html')
ROW='ZM-R25'; GAME_ID='ZM-R25-GAME-RAMADAN-WAR-20261022'; GAME=ROOT/'ramadan-war'
MARK='ZM-RAMADAN-WAR-WEB-CARD-20261022'

def digest(data): return hashlib.sha256(data).hexdigest()
def atomic(path,data,run):
    assert not path.is_symlink(),f'symlink refused: {path}'
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
    assert len(cards)==23 and cards[0].get('id')=='ZM-R25-GAME-FARM-DOMINION-20261019'
    assert cards[1].get('id')==GAME_ID and cards[1].get('canonicalUrl')=='/ramadan-war/'
    assert cards[2].get('slug')=='website-design'
    return home

def prepare(stage):
    assert ROOT.is_dir() and not ROOT.is_symlink() and GAME.is_dir() and not GAME.is_symlink()
    home=live_card_check()
    inputs={name:(stage/f'incoming/{name}') for name in ['index.html','game.js','game.css','.htaccess']}
    assert all(p.is_file() and not p.is_symlink() for p in inputs.values())
    assert inputs['.htaccess'].read_text('utf-8')=='PassengerEnabled off\nDirectoryIndex index.html\n'
    new={name:inputs[name].read_bytes() for name in ['index.html','game.js','game.css']}
    assert len(new['index.html'])>1000 and MARK.encode() in new['index.html']
    assert b'RamadanWarDebug' in new['game.js'] and b'./game.js' in new['index.html'] and b'./game.css' in new['index.html']
    assert (GAME/'.htaccess').is_file() and (GAME/'.htaccess').read_bytes()==inputs['.htaccess'].read_bytes()
    old={name:(GAME/name).read_bytes() for name in new}
    assert MARK.encode() in old['index.html'] and b'RamadanWarDebug' in old['game.js']
    assert all((GAME/name).is_file() and not (GAME/name).is_symlink() for name in new)
    protected={}
    for rel in ['.htaccess','agriculture/index.html','research/index.html','store/index.html']:
        p=ROOT/rel
        if p.is_file() and not p.is_symlink():protected[rel]=digest(p.read_bytes())
    assert len(protected)>=2,'insufficient protected-page baseline'
    for name,data in old.items():(stage/f'old-{name}').write_bytes(data)
    (stage/'old-home-hash.txt').write_text(digest(home.read_bytes()),encoding='ascii')
    store(stage,{'phase':'prepared','old':{k:digest(v) for k,v in old.items()},'new':{k:digest(v) for k,v in new.items()},'route':digest(inputs['.htaccess'].read_bytes()),'protected':protected})
    print('RAMADAN_WEB_PREPARE=PASS current-card-two-confirmed; old-client-backed-up')

def publish(stage,run):
    m=metadata(stage);assert m['phase']=='prepared';live_card_check()
    for name,h in m['old'].items():assert digest((GAME/name).read_bytes())==h,'game file changed concurrently: '+name
    assert digest((GAME/'.htaccess').read_bytes())==m['route'],'game route config changed concurrently'
    for name in m['new']:
        data=(stage/f'incoming/{name}').read_bytes();assert digest(data)==m['new'][name]
    try:
        for name in ['game.css','game.js','index.html']:
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
    for name,h in m['new'].items():
        p=GAME/name
        if p.is_file() and not p.is_symlink() and digest(p.read_bytes())==h:
            atomic(p,(stage/f'old-{name}').read_bytes(),run);print('RESTORED_OLD_GAME_FILE='+name)
        else:print('ROLLBACK_SKIPPED_UNEXPECTED_GAME_FILE='+name)

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
