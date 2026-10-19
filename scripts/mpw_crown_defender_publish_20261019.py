#!/usr/bin/env python3
"""Isolated release of one MojPlayWin Crown Defender game on the main domain.

Only one new static game HTML, an exact /games/crown-defender/ GET rewrite,
and an additive studio editorial play link. Backup and hash-guarded rollback.
No shared Django, Passenger, store, payment, database, or child-site edits.
"""
import hashlib,json,os,re,shutil,stat,sys,tempfile
from pathlib import Path

HOME=Path('/home/zomorod2');ROOT=HOME/'mojplaywin.com';HT=ROOT/'.htaccess'
GAME_DIR=ROOT/'design-preview-20261017/mpw-crown-defender-20261019'
GAME=GAME_DIR/'index.html'
STUDIO=ROOT/'design-preview-20261017/mpw-ten-editorials-20261018/pages/studio.html'
ROUTE='/games/crown-defender/'
MARKER='MPW_CROWN_DEFENDER_ISOLATED_20261019'
STUDIO_MARKER='mpw-crown-defender-featured-20261019'
ROUTES=f"# {MARKER}_BEGIN\nRewriteCond %{{REQUEST_METHOD}} ^GET$\nRewriteCond %{{REQUEST_URI}} ^/games/crown-defender/?$\nRewriteRule ^.*$ /design-preview-20261017/mpw-crown-defender-20261019/index.html [END,QSD]\n# {MARKER}_END\n"
PROMO='''
<!-- MPW_CROWN_DEFENDER_STUDIO_PROMO_20261019 -->
<section id="mpw-crown-defender-featured-20261019" aria-label="Play Crown Defender" style="clear:both;margin:24px auto;padding:clamp(18px,3vw,35px);max-width:1200px;border:1px solid #d9ac62;border-radius:19px;color:#fff3df;background:linear-gradient(120deg,#0a1020,#25365a 56%,#21190d);box-shadow:0 15px 48px #0005">
  <p style="margin:0;color:#f5d58c;letter-spacing:.16em;font-size:.76rem;font-weight:800">NOW PLAYABLE · AN ORIGINAL MOJPLAYWIN GAME</p>
  <h2 style="margin:8px 0;font-size:clamp(1.5rem,3vw,2.7rem);color:#ffe2a1">Crown Defender</h2>
  <p style="color:#e0e4ee;max-width:70ch">Pilot a royal defense ship, survive escalating enemy waves, unlock power-ups, challenge armored bosses, and beat your personal best. Free on desktop and mobile. No sign-up or payment.</p>
  <a href="/games/crown-defender/" style="display:inline-block;background:linear-gradient(125deg,#ffe8a6,#d9a248);color:#16120b;padding:12px 20px;border-radius:12px;text-decoration:none;font-weight:850">▶ PLAY CROWN DEFENDER FREE</a>
</section>
'''

def sha(blob):return hashlib.sha256(blob).hexdigest()
def stop(msg):raise RuntimeError(msg)
def runpaths(run):
    if not re.fullmatch(r'[0-9]{9,20}',run):stop('Unsafe GitHub run ID')
    return (HOME/f'.mpw-crown-game-stage-{run}.html',HOME/f'.mpw-crown-game-backup-{run}')
def atomic(path,contents,mode):
    if path.is_symlink():stop('Refuse symlink file')
    fd,tmp=tempfile.mkstemp(prefix='.mpw-crown-atomic-',dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as f:f.write(contents);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)
def safe_read(path):
    if not path.is_file() or path.is_symlink():stop('Missing or unsafe file '+str(path))
    return path.read_bytes()
def validate(blob):
    if not 25000<=len(blob)<=65000:stop('Game size outside envelope')
    s=blob.decode('utf-8')
    markers=('CROWN DEFENDER','id="game"','id="start"','id="pause"','id="fullscreen"',
             'id="autofire"','id="left"','id="right"','id="fire"','requestAnimationFrame',
             'localStorage','function gameOver','function hit','function spawnBoss','function reset')
    if any(mark not in s for mark in markers):stop('Incomplete playable game')
    if s.count('<script>')!=1 or s.count('</script>')!=1 or s.count('<canvas')!=1:
        stop('Unexpected HTML game structure')
    if re.search(r'https?://(?!mojplaywin\.com)',s):stop('Third-party network dependency forbidden')
    if '<iframe' in s.lower() or 'eval(' in s:stop('Unsafe code')
    return sha(blob)
def guarded():
    if not ROOT.is_dir() or ROOT.is_symlink() or ROOT.resolve()!=ROOT:stop('Wrong docroot')
    if not (ROOT/'design-preview-20261017').is_dir():stop('Missing safe static parent')
    if GAME_DIR.exists() or GAME_DIR.is_symlink():stop('A game already occupies the target path')
    if not STUDIO.is_file() or STUDIO.is_symlink():stop('Verified studio snapshot not found')
    for p in (STUDIO.parent, STUDIO.parent.parent,STUDIO.parent.parent.parent):
        if p.is_symlink():stop('Symlink in studio parent path')
    before_ht=safe_read(HT);before_studio=safe_read(STUDIO)
    rules=before_ht.decode('utf-8')
    if rules.count('RewriteEngine On')!=1 or len(rules)>450000:stop('Unexpected rewrite configuration')
    if MARKER in rules or ROUTE in rules:stop('New exact route already present')
    raw=before_studio.decode('utf-8')
    if STUDIO_MARKER in raw or 'MPW_CROWN_DEFENDER_STUDIO_PROMO_20261019' in raw:stop('Featured play link already exists')
    if raw.count('class="mpw-ten-card"')!=10:stop('Studio previously published ten guides changed')
    if 'mpw-research30-' not in raw:stop('Existing scholarly editorials in studio not found')
    if len(re.findall(r'<main\b',raw,re.I))!=1 or len(re.findall(r'</main\s*>',raw,re.I))!=1:stop('Unexpected semantic main')
    if len(re.findall(r'<h1\b',raw,re.I))!=1:stop('Unexpected Studio H1')
    if not 10000<len(before_studio)<1300000:stop('Studio page unexpected length')
    return before_ht,before_studio

def compose(ht,studio):
    t=ht.decode('utf-8').replace('RewriteEngine On','RewriteEngine On\n'+ROUTES,1)
    if t.replace('\n'+ROUTES,'',1)!=ht.decode('utf-8'):stop('Rewrite not exactly reversible')
    old=studio.decode('utf-8')
    main=re.search(r'<main\b[^>]*>',old,re.I)
    if not main:stop('Studio main missing')
    pos=old.find('</section>',main.end())
    if pos<0 or pos-main.end()>15000:stop('Studio first hero section changed')
    pos+=len('</section>')
    new=old[:pos]+PROMO+old[pos:]
    if new.replace(PROMO,'',1)!=old:stop('Studio promo not reversible')
    if new.count('class="mpw-ten-card"')!=10 or new.count('mpw-research30-')!=old.count('mpw-research30-'):
        stop('Old editorials modified')
    if len(re.findall(r'<h1\b',new,re.I))!=1:stop('Studio H1 changed')
    return t.encode(),new.encode()

def install(run,expect):
    stage,bkdir=runpaths(run)
    if not re.fullmatch(r'[a-f0-9]{64}',expect):stop('Bad checksum')
    source=safe_read(stage)
    if validate(source)!=expect:stop('Staged game checksum mismatch')
    original_ht,original_studio=guarded()
    ht_updated,studio_updated=compose(original_ht,original_studio)
    if bkdir.exists() or bkdir.is_symlink():stop('Backup already exists')
    bkdir.mkdir(mode=0o700)
    for name,raw in [('htaccess',original_ht),('studio',original_studio)]:
        with (bkdir/name).open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        (bkdir/name).chmod(0o600)
    rec={'run':run,'before_ht':sha(original_ht),'after_ht':sha(ht_updated),
         'before_studio':sha(original_studio),'after_studio':sha(studio_updated),'game':expect}
    (bkdir/'manifest.json').write_text(json.dumps(rec),'utf-8')
    (bkdir/'manifest.json').chmod(0o600)
    if sha(safe_read(HT))!=rec['before_ht'] or sha(safe_read(STUDIO))!=rec['before_studio']:
        stop('Concurrent site edit; refuse publication')
    created=False
    try:
        GAME_DIR.mkdir(mode=0o755)
        created=True
        atomic(GAME,source,0o644)
        if sha(safe_read(GAME))!=expect:stop('Game file failed validation')
        atomic(STUDIO,studio_updated,stat.S_IMODE(STUDIO.stat().st_mode))
        atomic(HT,ht_updated,stat.S_IMODE(HT.stat().st_mode))
        if sha(safe_read(STUDIO))!=rec['after_studio'] or sha(safe_read(HT))!=rec['after_ht']:
            stop('Final write checksum differs')
    except BaseException:
        if sha(safe_read(HT))==rec['after_ht']:atomic(HT,original_ht,stat.S_IMODE(HT.stat().st_mode))
        if sha(safe_read(STUDIO))==rec['after_studio']:atomic(STUDIO,original_studio,stat.S_IMODE(STUDIO.stat().st_mode))
        if created and GAME.is_file() and not GAME.is_symlink() and sha(GAME.read_bytes())==expect:
            GAME.unlink();GAME_DIR.rmdir()
        raise
    stage.unlink()
    print(json.dumps({'result':'CROWN_DEFENDER_PRODUCTION_INSTALLED','game_bytes':len(source),
          'route':ROUTE,'studio_featured':True,'isolated_only':True,
          'other_routes_edited':False,'passenger_restarted':False,'backup_ready':True}))

def status(run):
    _,bkdir=runpaths(run)
    m=json.loads((bkdir/'manifest.json').read_text('utf-8')) if (bkdir/'manifest.json').is_file() else {}
    check=bool(m) and GAME.is_file() and not GAME.is_symlink() and sha(GAME.read_bytes())==m['game'] and sha(safe_read(HT))==m['after_ht'] and sha(safe_read(STUDIO))==m['after_studio']
    print(json.dumps({'result':'CROWN_DEFENDER_READONLY_STATUS','installed':check,'backups':bool(m),'route':ROUTE}))

def rollback(run):
    _,bkdir=runpaths(run)
    m=json.loads((bkdir/'manifest.json').read_text('utf-8'))
    originals=[(HT,safe_read(bkdir/'htaccess'),'ht'),(STUDIO,safe_read(bkdir/'studio'),'studio')]
    for p,b,name in originals:
        if sha(b)!=m['before_'+name]:stop('Corrupt original backup '+name)
        present=sha(safe_read(p))
        if present not in (m['before_'+name],m['after_'+name]):stop('Concurrent '+name+' edit; refuse rollback')
    if GAME.is_file() and not GAME.is_symlink() and sha(GAME.read_bytes())!=m['game']:
        stop('Game asset modified; refuse deletion')
    for p,original,name in originals:
        if sha(safe_read(p))==m['after_'+name]:atomic(p,original,stat.S_IMODE(p.stat().st_mode))
    if GAME.is_file() and not GAME.is_symlink() and sha(GAME.read_bytes())==m['game']:
        GAME.unlink();GAME_DIR.rmdir()
    print(json.dumps({'result':'CROWN_DEFENDER_SCOPE_ROLLBACK_COMPLETE','others_unchanged':True}))

if __name__=='__main__':
    if len(sys.argv)<3:stop('Usage install run sha | status run | rollback run')
    action,run=sys.argv[1:3]
    if action=='install' and len(sys.argv)==4:install(run,sys.argv[3])
    elif action=='status' and len(sys.argv)==3:status(run)
    elif action=='rollback' and len(sys.argv)==3:rollback(run)
    else:stop('Unsupported command')
