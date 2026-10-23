#!/usr/bin/env python3
"""Add ten verified new English destinations to existing two *static* MojPlayWin hubs.

No Django templates, central /games/, store, Passenger or subsite changed.
Refuse concurrent changes and rollback only exact newly introduced HTML.
"""
import hashlib,json,os,re,sys
from pathlib import Path
ROOT=Path('/home/zomorod2/mojplaywin.com')
HOME=Path('/home/zomorod2')
REL=('game-releases/20261021/index.html','mpw-editorial/index.html')
NEW=ROOT/'game-releases/20261023'
SLUGS=('windward-regatta','lexicon-sprint','grid-dominion','metro-vault','cargo-switchyard','invoice-craft','csv-workbench','image-slimmer','schema-builder','contrast-studio')
LABELS=('Windward Regatta','Lexicon Sprint','Grid Dominion','Metro Vault','Cargo Switchyard','Invoice Craft','CSV Workbench','Image Slimmer','Schema Builder','Contrast Studio')
MARK=b'mpw-ten-distinct-20261023-navigation'
SECTION=('''<section id="mpw-ten-distinct-20261023-navigation" aria-labelledby="mpw-ten-nav-title" style="max-width:1190px;margin:42px auto;padding:26px;color:#e7f7fa;background:#102b3d;border:1px solid #6291a7;border-radius:17px;font:16px/1.7 system-ui,Arial,sans-serif">
<span style="color:#fed092;font-size:12px;font-weight:800;letter-spacing:0.15em">NEW · 2026 BROWSER RELEASE</span>
<h2 id="mpw-ten-nav-title" style="font-size:clamp(23px,3vw,35px);margin:7px 0">5 New Games & 5 Practical Tools</h2>
<p style="color:#bcd6df;margin-bottom:18px">Play five distinct English games and use five working privacy-first browser tools, free and without an account.</p>
<nav aria-label="MojPlayWin new games and tools" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:10px">
'''+''.join('<a style="display:block;padding:12px 14px;border-radius:10px;border:1px solid #668ba5;color:#e9f8ff;text-decoration:none;background:#173a50" href="/game-releases/20261023/'+slug+'/index.html">'+('PLAY · ' if i<5 else 'USE · ')+label+'</a>\n' for i,(slug,label) in enumerate(zip(SLUGS,LABELS)))+'''</nav><p style="margin:15px 0 0"><a style="color:#ffd28f;font-weight:800" href="/game-releases/20261023/index.html">Browse the full 10-experience collection →</a></p>
</section>
''').encode('utf8')
def hash(data):return hashlib.sha256(data).hexdigest()
def stage(run):return HOME/('.mpw-tenlab-nav-'+run)
def manifest(run):return stage(run)/'manifest.json'
def stored(run):return json.loads(manifest(run).read_text('utf8'))
def save(run,v):p=manifest(run);t=p.with_suffix('.temp');t.write_text(json.dumps(v,sort_keys=True),encoding='utf8');os.replace(t,p)
def srcfile(rel):
 p=ROOT/rel
 if p.is_symlink() or not p.is_file():raise RuntimeError('missing or symlinked: '+rel)
 return p
def ensure_new():
 assert NEW.is_dir() and not NEW.is_symlink()
 for slug in SLUGS:
  p=NEW/slug/'index.html'
  if not p.is_file() or p.is_symlink() or b'<html lang="en">' not in p.read_bytes():raise RuntimeError('new game or tool absent: '+slug)
def updated(raw):
 assert MARK not in raw, 'navigation already inserted'
 assert raw.count(b'</body>')==1 and b'MojPlayWin' in raw
 return raw.replace(b'</body>',SECTION+b'</body>',1)
def write(path,blob,run):
 if path.is_symlink():raise RuntimeError('symlink target refused')
 tmp=path.with_name('.'+path.name+'.tennav-'+run)
 if tmp.exists() or tmp.is_symlink():raise RuntimeError('temporary path occupied')
 with open(tmp,'xb') as fd:
  fd.write(blob);fd.flush();os.fsync(fd.fileno())
 os.chmod(tmp,0o644);os.replace(tmp,path)
def prepare(run):
 ensure_new()
 if not stage(run).is_dir() or stage(run).is_symlink() or manifest(run).exists():raise RuntimeError('unsafe stage')
 m={'phase':'prepared','files':{},'original':{}}
 for rel in REL:
  original=srcfile(rel).read_bytes();n=updated(original)
  if len(original)<1200:raise RuntimeError('unexpected previous hub size')
  backup=stage(run)/('saved-'+str(REL.index(rel))+'.html')
  backup.write_bytes(original)
  m['files'][rel]={'old':hash(original),'new':hash(n)}
 for rel in ('passenger_wsgi.py','.htaccess'):
  p=srcfile(rel);m['original'][rel]=hash(p.read_bytes())
 save(run,m)
 print('MPW_TENLAB_ADDITIVE_CARDS_PREPARED=PASS')
def immutable(m):
 for rel,h in m['original'].items():
  if hash(srcfile(rel).read_bytes())!=h:raise RuntimeError('protected core changed '+rel)
def install(run):
 m=stored(run);assert m['phase']=='prepared'
 ensure_new();immutable(m)
 for rel,e in m['files'].items():
  if hash(srcfile(rel).read_bytes())!=e['old']:raise RuntimeError('hub changed concurrently')
 for rel,e in m['files'].items():
  n=updated(srcfile(rel).read_bytes())
  if hash(n)!=e['new']:raise RuntimeError('prepared hub bytes changed')
  write(srcfile(rel),n,run)
  m['phase']='installing';save(run,m)
 m['phase']='installed';save(run,m)
 print('MPW_TENLAB_NEW_LINKS_ADDED_TO_BOTH_EXISTING_STATIC_HUBS=PASS')
def verify(run):
 m=stored(run)
 assert m['phase']=='installed'
 immutable(m)
 for rel,e in m['files'].items():
  b=srcfile(rel).read_bytes()
  assert hash(b)==e['new']
  assert b.count(MARK)==1
  assert all(b.count(('/game-releases/20261023/'+slug+'/index.html').encode())==1 for slug in SLUGS)
 print('MPW_TENLAB_TEN_NEW_CARDS_LIVE_STATIC_HUBS=PASS')
def rollback(run):
 if not manifest(run).exists():return
 m=stored(run)
 for i,rel in enumerate(REL):
  e=m['files'][rel];p=srcfile(rel)
  old=(stage(run)/('saved-'+str(i)+'.html')).read_bytes()
  if hash(old)!=e['old']:raise RuntimeError('backup corrupt')
  current=hash(p.read_bytes())
  if current==e['new']:write(p,old,run)
  elif current!=e['old']:raise RuntimeError('external edits detected; cannot rollback '+rel)
 m['phase']='rolled_back';save(run,m)
 print('MPW_TENLAB_NAV_ONLY_ROLLBACK=PASS')
def selftest():
 sample=b'<html><head><title>MojPlayWin</title></head><body><main>Hello</main></body></html>'
 b=updated(sample);assert b.replace(SECTION,b'',1)==sample
 assert b.count(MARK)==1 and len(set(SLUGS))==10 and len(set(LABELS))==10
 try:updated(b);raise AssertionError('repeat must refuse')
 except AssertionError as e:
  if str(e)=='repeat must refuse':raise
 print('MPW_TENLAB_NAV_APPEND_ONLY_SELFTEST=PASS')
if __name__=='__main__':
 assert len(sys.argv)>=2 and sys.argv[1] in ('selftest','prepare','install','verify','rollback')
 if sys.argv[1]=='selftest':selftest()
 else:
  assert len(sys.argv)==3 and re.fullmatch(r'\d{7,17}',sys.argv[2])
  globals()[sys.argv[1]](sys.argv[2])
