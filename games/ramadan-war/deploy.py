#!/usr/bin/env python3
"""Narrow, reversible cPanel release: one game directory and one homepage card."""
from pathlib import Path
import hashlib, json, os, re, shutil, sys

ROOT=Path('/home/zomorod2/public_html')
ROW='ZM-R25'
GAME_ID='ZM-R25-GAME-RAMADAN-WAR-20261022'
CARD_SLUG='ramadan-war'
MARK='ZM-RAMADAN-WAR-WEB-CARD-20261022'
GAME=ROOT/'ramadan-war'

def digest(data): return hashlib.sha256(data).hexdigest()
def atomic(path,data,run):
    assert not path.is_symlink(),f'symlink refused: {path}'
    tmp=path.with_name('.'+path.name+'.ramadan-'+run)
    assert not tmp.exists() and not tmp.is_symlink(),f'temporary path exists: {tmp}'
    tmp.write_bytes(data); os.chmod(tmp,0o644)
    assert digest(tmp.read_bytes())==digest(data)
    os.replace(tmp,path)
def manifest(source):
    text=source.decode('utf-8')
    marker=r'(window\.ZOMOROD_ORBIT_DATA=)(\{.*?\})(;</script>)'
    matches=list(re.finditer(marker,text,re.S))
    assert len(matches)==1,'home orbit manifest must occur exactly once'
    m=matches[0]; data=json.loads(m.group(2))
    rows=[r for r in data.get('rows',[]) if r.get('id')==ROW]
    assert len(rows)==1,'technology and digital-services row changed'
    row=rows[0]
    assert row.get('title')=='فناوری اطلاعات و خدمات دیجیتال' and row.get('index')==25
    cards=row.get('cards',[])
    assert len(cards)==22,'unexpected card count; refusing to overwrite a concurrent change'
    assert cards[0].get('id')=='ZM-R25-GAME-FARM-DOMINION-20261019'
    assert cards[1].get('slug')=='website-design','second card no longer matches the requested insertion point'
    assert not any(c.get('slug')==CARD_SLUG or c.get('id')==GAME_ID for c in cards)
    assert not any(c.get('canonicalUrl')=='/ramadan-war/' for r in data['rows'] for c in r.get('cards',[]))
    original=[c.get('id') for c in cards]
    entry={'id':GAME_ID,'title':'جنگ رمضان | شوتر موشکی و پهپادی','slug':CARD_SLUG,
      'image':'data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCA1NjAgMzIwIj48ZGVmcz48bGluZWFyR3JhZGllbnQgaWQ9ImEiIHgyPSIxIiB5Mj0iMSI+PHN0b3Agc3RvcC1jb2xvcj0iIzE2MzUyYyIvPjxzdG9wIG9mZnNldD0iMSIgc3RvcC1jb2xvcj0iIzExMWYxYSIvPjwvbGluZWFyR3JhZGllbnQ+PC9kZWZzPjxyZWN0IHdpZHRoPSI1NjAiIGhlaWdodD0iMzIwIiBmaWxsPSJ1cmwoI2EpIi8+PGNpcmNsZSBjeD0iNDQwIiBjeT0iNjUiIHI9IjQ4IiBmaWxsPSIjZWRkMDliIiBvcGFjaXR5PSIuNyIvPjxwYXRoIGQ9Ik0wIDI0MCBRMTQwIDE4MCAyODAgMjIwIFQ1NjAgMTg1VjMyMEgwWiIgZmlsbD0iIzQ5NjY0OSIvPjxwYXRoIGQ9Ik0yODAgMjQwIGwxNiAtNjAgMTYgNjAgLTMwIC0yMCB6IiBmaWxsPSIjZjFkODg2Ii8+PHBhdGggZD0iTTI5MCAyMzAgbC0yMCAtNjAgLTQgMzAgIiBzdHJva2U9IiNmZmRkOTkiIHN0cm9rZS13aWR0aD0iNiIvPjx0ZXh0IHg9IjI4MCIgeT0iMjkwIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmaWxsPSIjZmZlOWFiIiBmb250LXNpemU9IjIzIiBmb250LWZhbWlseT0iVGRob21hIj7Yp9mE2YjYr9mE2KfZhiDYt9mE2KfZh9mFINmB2YjYs9uM2LHYs9mBPC90ZXh0Pjwvc3ZnPg==',
      'imageStatus':'procedural_game_artwork','canonicalUrl':'/ramadan-war/','livePage':True,'previousCanonicalUrl':None}
    cards.insert(1,entry)
    assert [c.get('id') for c in cards[:1]]==original[:1] and [c.get('id') for c in cards[2:]]==original[1:]
    packed=json.dumps(data,ensure_ascii=False,separators=(',',':'))
    assert '</script' not in packed.lower()
    out=(text[:m.start(2)]+packed+text[m.end(2):]).encode('utf-8')
    assert out.decode('utf-8').replace(packed,m.group(2),1)==text,'change escaped the homepage data manifest'
    return out
def metadata(stage): return json.loads((stage/'release.json').read_text('utf-8'))
def store(stage,value):
    p=stage/'release.json.tmp';p.write_text(json.dumps(value,sort_keys=True),encoding='utf-8');os.replace(p,stage/'release.json')
def prepare(stage):
    assert ROOT.is_dir() and not ROOT.is_symlink()
    home=ROOT/'index.html'; assert home.is_file() and not home.is_symlink()
    game_source=stage/'incoming/index.html'; assert game_source.is_file() and game_source.stat().st_size>5000
    route_source=stage/'incoming/.htaccess';assert route_source.is_file() and route_source.read_text('utf-8')=='PassengerEnabled off\nDirectoryIndex index.html\n'
    source=game_source.read_bytes();route=route_source.read_bytes(); assert b'RamadanWarDebug' in source and b'ZM-RAMADAN-WAR-WEB-CARD-20261022' in source
    assert not GAME.exists() and not GAME.is_symlink(),'game route already exists; refusing to replace it'
    old=home.read_bytes();new=manifest(old)
    protected={}
    for rel in ['.htaccess','agriculture/index.html','research/index.html','store/index.html']:
        p=ROOT/rel
        if p.is_file() and not p.is_symlink(): protected[rel]=digest(p.read_bytes())
    assert len(protected)>=2,'insufficient protected-page baseline'
    (stage/'old-home.html').write_bytes(old);(stage/'new-home.html').write_bytes(new)
    store(stage,{'phase':'prepared','oldHome':digest(old),'newHome':digest(new),'game':digest(source),'route':digest(route),'protected':protected})
    print('RAMADAN_WEB_PREPARE=PASS current-card-2 preserved-card-1-and-rest')
def publish(stage,run):
    m=metadata(stage);assert m['phase']=='prepared'
    home=ROOT/'index.html';assert digest(home.read_bytes())==m['oldHome'],'homepage changed concurrently'
    source=(stage/'incoming/index.html').read_bytes();assert digest(source)==m['game']
    assert not GAME.exists() and not GAME.is_symlink()
    try:
        GAME.mkdir(mode=0o755)
        atomic(GAME/'.htaccess',(stage/'incoming/.htaccess').read_bytes(),run)
        atomic(GAME/'index.html',source,run)
        assert digest((GAME/'index.html').read_bytes())==m['game']
        assert digest((GAME/'.htaccess').read_bytes())==m['route']
        atomic(home,(stage/'new-home.html').read_bytes(),run)
        assert digest(home.read_bytes())==m['newHome']
        m['phase']='published';store(stage,m)
        print('RAMADAN_WEB_AND_SECOND_CARD_PUBLISHED=PASS')
    except BaseException:
        if GAME.is_dir() and not GAME.is_symlink():
            for name,key in [('index.html','game'),('.htaccess','route')]:
                p=GAME/name
                if p.is_file() and not p.is_symlink() and digest(p.read_bytes())==m[key]:p.unlink()
            if not any(GAME.iterdir()):GAME.rmdir()
        raise
def verify(stage):
    m=metadata(stage);assert m['phase']=='published'
    assert digest((ROOT/'index.html').read_bytes())==m['newHome']
    assert digest((GAME/'index.html').read_bytes())==m['game']
    assert digest((GAME/'.htaccess').read_bytes())==m['route']
    for rel,h in m['protected'].items():assert digest((ROOT/rel).read_bytes())==h,'protected file changed: '+rel
    data=json.loads(re.search(r'window\.ZOMOROD_ORBIT_DATA=(\{.*?\});</script>',(ROOT/'index.html').read_text('utf-8'),re.S).group(1))
    row=next(r for r in data['rows'] if r.get('id')==ROW)
    assert row['cards'][1]['id']==GAME_ID and row['cards'][1]['canonicalUrl']=='/ramadan-war/'
    assert row['cards'][2]['slug']=='website-design' and len(row['cards'])==23
    print('RAMADAN_WEB_HASHES_AND_CARD_ORDER=PASS')
def rollback(stage):
    if not (stage/'release.json').is_file(): print('ROLLBACK_SKIPPED_NO_RELEASE_STATE');return
    m=metadata(stage);home=ROOT/'index.html'
    if home.is_file() and not home.is_symlink() and digest(home.read_bytes())==m.get('newHome'):
        atomic(home,(stage/'old-home.html').read_bytes(),stage.name[-12:]);print('HOMEPAGE_RESTORED=PASS')
    else: print('HOMEPAGE_ROLLBACK_SKIPPED_UNEXPECTED_CONTENT')
    if GAME.is_dir() and not GAME.is_symlink():
        removed=False
        for name,key in [('index.html','game'),('.htaccess','route')]:
            p=GAME/name
            if p.is_file() and not p.is_symlink() and digest(p.read_bytes())==m.get(key):p.unlink();removed=True
        if not any(GAME.iterdir()):GAME.rmdir()
        print('GAME_ROUTE_REMOVED=PASS' if removed else 'GAME_ROLLBACK_SKIPPED_UNEXPECTED_CONTENT')
    else: print('GAME_ROLLBACK_SKIPPED_UNEXPECTED_CONTENT')
def main():
    assert len(sys.argv)==3,'usage: deploy.py prepare|publish|verify|rollback RUN_ID'
    action,run=sys.argv[1:];assert re.fullmatch(r'[0-9]{4,15}',run)
    stage=Path('/home/zomorod2/.zm-ramadan-war-'+run);assert stage.is_dir() and not stage.is_symlink()
    funcs={'prepare':lambda:prepare(stage),'publish':lambda:publish(stage,run),'verify':lambda:verify(stage),'rollback':lambda:rollback(stage)}
    assert action in funcs;funcs[action]()
if __name__=='__main__':main()
