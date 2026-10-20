#!/usr/bin/env python3
"""Safely place two personal-site photos above one intro. Home page only."""
import hashlib,json,os,re,stat,sys,tempfile
from pathlib import Path
APP=Path('/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17')
PAGE=APP/'templates/personal_site/core/home.html'
MARK='mpw-two-profile-portraits-20261020'
CSS="""<style id="mpw-two-profile-portraits-20261020">
#mpw-primary-personal-profile-20261016{max-width:1180px!important;display:block!important;box-sizing:border-box}
#mpw-primary-personal-profile-20261016 .mpw-profile-photo-pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));align-items:center;gap:clamp(15px,3vw,36px)}
#mpw-primary-personal-profile-20261016 .mpw-profile-photo-pair>figure{margin:0!important;max-width:100%!important;min-width:0!important;flex:none!important;align-self:center}
#mpw-primary-personal-profile-20261016 .mpw-profile-photo-pair>figure img{display:block;width:100%;height:auto;max-height:530px;object-fit:contain}
#mpw-primary-personal-profile-20261016 .mpw-profile-photo-pair .hero-visual{position:relative;display:block;width:100%!important;max-width:100%!important;height:530px;min-height:0!important;margin:0 auto;flex:none}
#mpw-primary-personal-profile-20261016 .mpw-profile-photo-pair .portrait-arch{max-width:100%}
#mpw-primary-personal-profile-20261016 .mpw-profile-photo-pair .portrait-arch img{max-width:100%}
section.hero .hero-layout{display:block!important;max-width:1050px}
section.hero .hero-content{max-width:100%;margin:0 auto;text-align:center}
section.hero .hero-content .hero-rule{margin-left:auto;margin-right:auto}
section.hero .hero-content .hero-actions{justify-content:center}
@media(max-width:700px){#mpw-primary-personal-profile-20261016 .mpw-profile-photo-pair{grid-template-columns:1fr;gap:18px}#mpw-primary-personal-profile-20261016 .mpw-profile-photo-pair>figure{width:min(100%,380px);justify-self:center}#mpw-primary-personal-profile-20261016 .mpw-profile-photo-pair .hero-visual{width:min(100%,420px)!important;height:430px}section.hero .hero-content{padding:14px 0}}
</style>"""
RX=re.compile(r'<section\b(?=[^>]*\bid="mpw-primary-personal-profile-20261016")[^>]*>.*?</section>',re.S)
def digest(b):return hashlib.sha256(b).hexdigest()
def target():
    if APP.is_symlink() or not (APP/'manage.py').is_file() or not PAGE.is_file() or PAGE.is_symlink() or PAGE.resolve()!=PAGE:raise RuntimeError('Personal app identity mismatch')
    return PAGE
def div_at(s,p):
    if not s.startswith('<div class="hero-visual"',p):raise RuntimeError('Hero visual changed')
    d=0
    for m in re.finditer(r'</?div\b[^>]*>',s[p:],re.I):
        d+=-1 if m.group().startswith('</') else 1
        if d==0:return s[p:p+m.end()],p+m.end()
    raise RuntimeError('Unbalanced hero div')
def patch(s):
    if MARK in s:raise RuntimeError('Already patched')
    if any(s.count(x)!=1 for x in ('id="mpw-primary-personal-profile-20261016"','class="hero-visual"','PROFESSIONAL PROFILE','id="hero-title"','mpw-complete-standard-20261019-toc')):raise RuntimeError('Current homepage markers differ; no mutation')
    m=RX.search(s)
    if m is None:raise RuntimeError('Primary section missing')
    block=m.group()
    head=re.match(r'<section\b[^>]*>',block,re.S)
    figs=re.findall(r'<figure\b[^>]*>.*?</figure>',block,re.S)
    if head is None or len(figs)!=1 or 'official_profile_20261016/portrait' not in figs[0] or 'Discuss a professional collaboration' not in block:raise RuntimeError('Primary source changed')
    pos=s.index('<div class="hero-visual">')
    vis,end=div_at(s,pos)
    if m.end()>=pos or vis.count('<img')!=1 or '<h1 id="hero-title"' not in s[m.end():pos]:raise RuntimeError('Hero structure changed: order=%s img=%s heading=%s'%(m.end()<pos,vis.count('<img'),'<h1 id="hero-title"' in s[m.end():pos]))
    newblock=head.group()+'\n'+CSS+'\n<div class="mpw-profile-photo-pair">\n'+figs[0]+'\n'+vis+'\n</div>\n</section>'
    a=s[:m.start()]+newblock+s[m.end():pos]+s[end:]
    if a.count('<img')!=s.count('<img') or a.count('{%')!=s.count('{%') or 'PROFESSIONAL PROFILE' in a:raise RuntimeError('Unintended template content change')
    if not a.index('official_profile_20261016/portrait')<a.index('class="hero-visual"')<a.index('id="hero-title"'):raise RuntimeError('Required order failed')
    return a
def validate(s):
    sys.path.insert(0,str(APP));os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
    import django;django.setup()
    from django.template import engines
    engines['django'].engine.from_string(s)
def atomic(p,b):
    fd,tmp=tempfile.mkstemp(prefix='.mpw-portraits-',dir=p.parent)
    try:
        with os.fdopen(fd,'wb') as f:
            os.fchmod(f.fileno(),stat.S_IMODE(p.stat().st_mode));f.write(b);f.flush();os.fsync(f.fileno())
        os.replace(tmp,p)
    finally:
        if os.path.lexists(tmp):os.unlink(tmp)
def backup(id):
    if not re.fullmatch(r'[0-9]{6,24}',id):raise RuntimeError('Invalid run ID')
    return Path('/home/zomorod2/.backups')/('mojtaba-two-portraits-'+id)
def install(id):
    p=target();before=p.read_bytes();after=patch(before.decode('utf8')).encode('utf8');validate(after.decode('utf8'))
    d=backup(id)
    if d.exists() or d.is_symlink():raise RuntimeError('Backup directory exists')
    d.mkdir(parents=True,mode=0o700)
    with (d/'home.before').open('xb') as f:
        os.fchmod(f.fileno(),0o600);f.write(before);f.flush();os.fsync(f.fileno())
    if (d/'home.before').read_bytes()!=before:raise RuntimeError('Backup verification failed')
    (d/'manifest.json').write_text(json.dumps({'path':str(p),'before':digest(before),'after':digest(after)}),encoding='utf8')
    if digest(p.read_bytes())!=digest(before):raise RuntimeError('Concurrent change')
    atomic(p,after)
    if digest(p.read_bytes())!=digest(after):raise RuntimeError('Post-write checksum mismatch')
    print('TWO_PORTRAITS_INSTALLED=YES BACKUP='+str(d),flush=True)
def rollback(id):
    p=target();d=backup(id)
    if d.is_symlink() or not (d/'manifest.json').is_file():raise RuntimeError('Backup unavailable')
    m=json.loads((d/'manifest.json').read_text('utf8'));orig=(d/'home.before').read_bytes()
    if m['path']!=str(p) or digest(orig)!=m['before'] or digest(p.read_bytes()) not in (m['before'],m['after']):raise RuntimeError('Unsafe rollback')
    if digest(p.read_bytes())==m['after']:atomic(p,orig)
    if digest(p.read_bytes())!=m['before']:raise RuntimeError('Rollback checksum mismatch')
    print('TWO_PORTRAITS_ROLLBACK=VERIFIED',flush=True)
if __name__=='__main__':
    if len(sys.argv)<2:raise SystemExit('check/install/rollback')
    if sys.argv[1]=='check':
        validate(patch(target().read_text('utf8')));print('TWO_PORTRAITS_PREFLIGHT=PASS')
    elif sys.argv[1]=='install' and len(sys.argv)==3:install(sys.argv[2])
    elif sys.argv[1]=='rollback' and len(sys.argv)==3:rollback(sys.argv[2])
    else:raise SystemExit('Unsupported action')
