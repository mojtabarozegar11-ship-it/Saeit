#!/usr/bin/env python3
"""One reversible, checked P0-P3 Zomorod Melal publication; no DB or payment mutations."""
from __future__ import annotations
import hashlib,json,os,pwd,re,sys,tempfile
from pathlib import Path
ROOT=Path('/home/zomorod2/public_html')
PRIVATE=Path('/home/zomorod2/.private/zomorod-business/app.php')
BACK=Path('/home/zomorod2/.backups/zomorod-one-stage-p0p3-20261019')
MARK='zm-priority-p0p3-20261019'
STATIC=('about/index.html','research/index.html','knowledge/index.html','agriculture/index.html','search/index.html','topics/index.html','store/index.php','tala/index.html','en/market/index.html','en/auctions/index.html')
FILES=[ROOT/p for p in STATIC]+[PRIVATE,ROOT/'.htaccess']
BASE_STYLE=r'''<style id="zm-priority-p0p3-20261019">
/* Additive site repair. Strictly confined to the specific page where included. */
html body #main a.zm-link,html body #main a.zm-link:hover,html body #main a.zm-link:focus-visible{
 color:#123d31!important;background-color:#f3d995!important;text-shadow:none!important;
 border-radius:8px;
}
html body #main a[href]{min-height:38px;max-width:100%;overflow-wrap:anywhere}
html body a:focus-visible,html body button:focus-visible{
 outline:3px solid #ffe79a!important;outline-offset:3px!important;
}
.zm-p0p3-skip-nav{display:contents}
.zm-p0p3-secondary-hero{font-size:clamp(30px,4.5vw,64px)!important;line-height:1.18!important;letter-spacing:-.02em;margin-block:0.6em!important;}
@media(max-width:700px){
 html body #main :is(.zm-card,.zm-article,.zm-history-card){backdrop-filter:blur(2px);-webkit-backdrop-filter:blur(2px)}
}
@media(prefers-reduced-motion:reduce){
 html body #main :is(.zm-card,.zm-article,.zm-history-card){animation:none!important;transition:none!important}
}
</style>'''
VARIANTS={
 'agriculture/index.html':r'''<style id="zm-p0p3-agriculture">
  html body a.pill{color:#183528!important;background:#e9eee5!important;text-shadow:none!important}
  html body a.pill:focus-visible{outline:3px solid #ffd875!important}
 </style>''',
 'search/index.html':r'''<style id="zm-p0p3-search">
  html body form button,html body button[type="submit"]{background:#73581e!important;color:#fff!important;text-shadow:none!important}
  html body form button:focus-visible{outline:3px solid #ffda75!important}
 </style>''',
 'topics/index.html':r'''<style id="zm-p0p3-topics">
  html body a[href="/topics/sitemap.xml"]{color:#ffe7a3!important;text-decoration:underline!important;text-underline-offset:4px}
  html body a[href="/topics/sitemap.xml"]:focus-visible{outline:3px solid #fff0b0}
 </style>''',
 'tala/index.html':r'''<style id="zm-p0p3-tala">
  html body footer{color:#c9c1ae!important}
  html body footer span{color:#c9c1ae!important}
  html body a[href*="gold-api.com"],html body a[href*="frankfurter.dev"]{text-decoration:underline!important;text-underline-offset:3px}
  html body a[href*="gold-api.com"]:focus-visible,html body a[href*="frankfurter.dev"]:focus-visible{outline:2px solid #fff3bd!important}
 </style>''',
 'store/index.php':r'''<style id="zm-p0p3-store">
  html body a[href],html body button{min-height:40px;max-width:100%;overflow-wrap:anywhere}
  html body a:focus-visible{outline:3px solid #ffe7a3}
 </style>''',
}
DESCS={
 'en/market/index.html':'Explore Zomorod Melal market research, value chains, product pathways and commercial opportunities. Availability, delivery and transaction terms require independent confirmation.',
 'en/auctions/index.html':'Review Zomorod Melal tender and procurement opportunities, eligibility considerations and process guidance. Listings and execution conditions are subject to verification.'
}
def sha(b):return hashlib.sha256(b).hexdigest()
def backup_dir(run):
 if not re.fullmatch(r'[0-9]{1,20}',run):raise RuntimeError('Invalid run ID')
 return BACK/run
def safe():
 if pwd.getpwuid(os.getuid()).pw_name!='zomorod2':raise RuntimeError('Wrong server account')
 if not ROOT.is_dir() or ROOT.is_symlink() or BACK.is_symlink():raise RuntimeError('Unsafe location')
 for p in FILES:
  if not p.is_file() or p.is_symlink() or p.parent.is_symlink():raise RuntimeError('Missing or unsafe target '+str(p))
def with_style(s,name):
 if s.count('</head>')!=1:raise RuntimeError('Invalid head in '+name)
 styles=BASE_STYLE+VARIANTS.get(name,'')
 return s.replace('</head>',styles+'</head>',1)
def wrap_skip(s):
 anchor=re.search(r'<a\b[^>]*class="(?:zm-skip|zm-v7-skip)"[^>]*href="#main"[^>]*>[^<]*</a>',s)
 if not anchor:
  anchor=re.search(r'<a\b[^>]*href="#main"[^>]*class="(?:zm-skip|zm-v7-skip)"[^>]*>[^<]*</a>',s)
 if anchor:
  target=anchor.group(0)
  wrapper='<nav class="zm-p0p3-skip-nav" aria-label="پرش به محتوای اصلی">'+target+'</nav>'
  s=s[:anchor.start()]+wrapper+s[anchor.end():]
 return s
def main_anchor(s):
 if 'id="main"' in s:return s
 m=re.search(r'<main\b[^>]*>',s)
 if not m:raise RuntimeError('Main absent for skip target')
 start=m.group(0)
 if ' id=' in start:raise RuntimeError('Main has another id; manual review needed')
 return s[:m.start()]+start[:-1]+' id="main" tabindex="-1">'+s[m.end():]
def proper_h1(s,name):
 matches=list(re.finditer(r'<h1\b[^>]*>[\s\S]*?</h1>',s,re.I))
 if len(matches)!=2:raise RuntimeError('Unexpected H1 count '+name)
 m=matches[1];v=m.group(0)
 n=v.replace('<h1','<h2 class="zm-p0p3-secondary-hero"',1).replace('</h1>','</h2>',1)
 return s[:m.start()]+n+s[m.end():]
def add_canonical(s,url):
 if re.search(r'<link\b[^>]*rel=["\']canonical["\']',s,re.I):return s
 return s.replace('</head>','<link rel="canonical" href="'+url+'"></head>',1)
def static_patch(name,data):
 s=data.decode('utf-8')
 if MARK in s:raise RuntimeError('Already patched '+name)
 if s.count('</head>')!=1 or s.count('</body>')!=1:raise RuntimeError('Unexpected HTML '+name)
 if len(data)<2500:raise RuntimeError('Truncated '+name)
 if name in ('about/index.html','knowledge/index.html'):s=proper_h1(s,name)
 if name in ('agriculture/index.html','search/index.html'):
  if not re.search(r'<a\b[^>]*href="#main"',s):raise RuntimeError('Skip link absent '+name)
  s=main_anchor(s)
 if name in ('about/index.html','research/index.html','agriculture/index.html','search/index.html'):s=wrap_skip(s)
 if name=='search/index.html':
  if 'name="description"' not in s:s=s.replace('</head>','<meta name="description" content="جست‌وجوی مطالب، پژوهش‌ها، حوزه‌های تخصصی و خدمات شرکت کشت و صنعت زمرد ملل."></head>',1)
 if name=='store/index.php':s=add_canonical(s,'https://zomorodmelal.ir/store/')
 if name=='tala/index.html':s=add_canonical(s,'https://zomorodmelal.ir/tala/')
 if name in DESCS:
  desc='This page introduces an area of work. It does not guarantee availability, delivery or project completion. Confirm the scope and terms before making a decision.'
  if desc not in s[:s.index('</head>')]:raise RuntimeError('Expected English description absent from head '+name)
  s=s.replace(desc,DESCS[name],1)
 s=with_style(s,name)
 return s.encode('utf-8')
def private_patch(data):
 s=data.decode('utf-8')
 if MARK in s:raise RuntimeError('Already applied to private app')
 if 'function layoutStart' not in s or 'function formBegin' not in s:raise RuntimeError('Wrong private application')
 for a,b in [
  ('<label>توکن فعال‌سازی</label><input name="setup_token"','<label for="zm-setup-token">توکن فعال‌سازی</label><input id="zm-setup-token" name="setup_token"'),
  ('<label>نام کاربری مدیر</label><input name="username"','<label for="zm-setup-user">نام کاربری مدیر</label><input id="zm-setup-user" name="username"'),
  ('<label>گذرواژه جدید</label><input name="password"','<label for="zm-setup-password">گذرواژه جدید</label><input id="zm-setup-password" name="password"')]:
  if s.count(a)!=1:raise RuntimeError('Unexpected setup label count '+a[:35])
  s=s.replace(a,b,1)
 # Only colors for the unauthenticated bootstrap page; preserve all server-side logic.
 old='main{max-width:1260px;margin:auto;padding:26px 20px 70px}'
 if s.count(old)!=1:raise RuntimeError('Private app layout structure changed')
 s=s.replace(old,old+'.sign p,.sign code{color:#f2efdc!important}',1)
 return s.encode('utf-8')
HTACCESS=r'''
# ZM_P0P3_SECURITY_REPORTONLY_20261019 - reversible, non-enforcing pilot
<IfModule mod_headers.c>
Header always set Strict-Transport-Security "max-age=300"
Header always set X-Content-Type-Options "nosniff"
Header always set Content-Security-Policy-Report-Only "base-uri 'self'; object-src 'none'"
</IfModule>
'''
def ht_patch(data):
 s=data.decode('utf-8')
 if 'ZM_P0P3_SECURITY_REPORTONLY_20261019' in s:raise RuntimeError('Already installed htaccess')
 if 'PassengerAppRoot' not in s or 'RewriteRule ^$ index.html' not in s:raise RuntimeError('Protected htaccess changed')
 return (s.rstrip('\n')+'\n'+HTACCESS).encode()
def change(p,data):
 if p==PRIVATE:return private_patch(data)
 if p.name=='.htaccess':return ht_patch(data)
 return static_patch(str(p.relative_to(ROOT)),data)
def atomic(p,data,mode):
 temp=None
 try:
  with tempfile.NamedTemporaryFile(dir=p.parent,prefix='.zm-single-fix-',delete=False) as f:
   temp=Path(f.name);f.write(data);f.flush();os.fsync(f.fileno())
  os.chmod(temp,mode);os.replace(temp,p)
 finally:
  if temp and temp.exists():temp.unlink()
def plan():
 safe()
 out=[]
 for p in FILES:
  before=p.read_bytes();after=change(p,before)
  if before==after:raise RuntimeError('No change '+str(p))
  out.append({'path':str(p),'size':len(before),'new_size':len(after),'before':sha(before),'after':sha(after)})
 print('BATCH_PLAN='+json.dumps(out,ensure_ascii=False),flush=True)
def apply(run):
 safe();output=backup_dir(run)
 if output.exists() or output.is_symlink():raise RuntimeError('Backup already exists')
 originals={};changes={};rows=[]
 for p in FILES:
  before=p.read_bytes();new=change(p,before)
  originals[p]=before;changes[p]=new
  rows.append({'path':str(p),'before':sha(before),'after':sha(new),'mode':p.stat().st_mode&0o777})
 output.mkdir(parents=True,mode=0o700)
 for i,p in enumerate(FILES):
  atomic(output/('snapshot-'+str(i)+'.bin'),originals[p],0o600)
  if sha((output/('snapshot-'+str(i)+'.bin')).read_bytes())!=rows[i]['before']:raise RuntimeError('Backup verify failure '+str(p))
 (output/'manifest.json').write_text(json.dumps({'files':rows},ensure_ascii=False),encoding='utf-8')
 for p in FILES:
  if sha(p.read_bytes())!=sha(originals[p]):raise RuntimeError('Concurrent modification '+str(p))
 for p,row in zip(FILES,rows):
  atomic(p,changes[p],row['mode'])
  if sha(p.read_bytes())!=row['after']:raise RuntimeError('Atomic write failed '+str(p))
 print('BATCH_ALL_FILES_INSTALLED='+str(len(FILES)),flush=True)
def verify(run):
 safe();output=backup_dir(run)
 rows=json.loads((output/'manifest.json').read_text())['files']
 if len(rows)!=len(FILES):raise RuntimeError('Partial manifest')
 for i,row in enumerate(rows):
  p=Path(row['path'])
  if p!=FILES[i] or sha(p.read_bytes())!=row['after'] or sha((output/('snapshot-'+str(i)+'.bin')).read_bytes())!=row['before']:raise RuntimeError('Mismatch '+str(p))
 print('BATCH_SOURCE_PRESERVATION_AND_CHECKSUMS=passed',flush=True)
def rollback(run):
 safe();output=backup_dir(run)
 if not (output/'manifest.json').is_file():print('BATCH_NOT_APPLIED=yes');return
 rows=json.loads((output/'manifest.json').read_text())['files']
 errors=[]
 for i,row in enumerate(rows):
  p=Path(row['path']);back=(output/('snapshot-'+str(i)+'.bin')).read_bytes()
  if p!=FILES[i] or sha(back)!=row['before']:errors.append('Bad backup '+str(p));continue
  actual=sha(p.read_bytes())
  if actual==row['before']:continue
  if actual!=row['after']:errors.append('Changed concurrently '+str(p));continue
  atomic(p,back,row['mode'])
  if sha(p.read_bytes())!=row['before']:errors.append('Restore mismatch '+str(p))
 if errors:raise RuntimeError('Rollback incomplete: '+';'.join(errors))
 print('BATCH_ALL_ORIGINAL_FILES_RESTORED=yes',flush=True)
def selftest():
 # Static safety and determinism, without needing or leaking live source.
 assert 'Content-Security-Policy-Report-Only' in HTACCESS
 assert 'max-age=300' in HTACCESS
 for key in STATIC:assert key.endswith(('.html','.php'))
 assert 'rel="canonical"' in add_canonical('<html><head></head></html>','https://zomorodmelal.ir/tala/')
 assert 'zm-p0p3-secondary-hero' in proper_h1('<h1>first</h1><h1>second</h1>','dummy')
 assert 'id="main"' in main_anchor('<main class="frame"></main>')
 assert 'zm-p0p3-skip-nav' in wrap_skip('<a class="zm-skip" href="#main">Jump</a>')
 print('P0_P3_BATCH_SELFTEST=passed',flush=True)
if __name__=='__main__':
 command=sys.argv[1] if len(sys.argv)>1 else ''
 if command=='selftest':selftest()
 elif command=='plan':plan()
 elif command=='apply' and len(sys.argv)==3:apply(sys.argv[2])
 elif command=='verify' and len(sys.argv)==3:verify(sys.argv[2])
 elif command=='rollback' and len(sys.argv)==3:rollback(sys.argv[2])
 else:raise SystemExit('selftest | plan | apply RUN | verify RUN | rollback RUN')
