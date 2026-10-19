#!/usr/bin/env python3
"""Regression follow-through for remaining sitewide accessibility issues; reversible."""
from __future__ import annotations
import os,pwd,re,sys,hashlib,json,tempfile
from pathlib import Path
ROOT=Path('/home/zomorod2/public_html')
DIR=Path('/home/zomorod2/.backups/zomorod-p0p3-final-a11y-20261019')
FILES=[ROOT/x for x in ['about/index.html','research/index.html','agriculture/index.html']]
MARKER='zm-p0p3-final-a11y-20261019'
STYLES={
'about/index.html':'''<style id="zm-p0p3-final-a11y-20261019">body #main .zm-card > span{color:#ffe8ae!important;text-shadow:0 1px 2px #092a1d!important}</style>''',
'research/index.html':'''<style id="zm-p0p3-final-a11y-20261019">body .zm-footer-main a[href="/"]{color:#163c2f!important;text-decoration:underline!important}body #main .zm-card > span{color:#ffe8ae!important;text-shadow:0 1px 2px #092a1d!important}</style>''',
'agriculture/index.html':'''<style id="zm-p0p3-final-a11y-20261019">body a:focus-visible{outline:3px solid #ffdf8f;outline-offset:2px}</style>''',
}
def digest(b):return hashlib.sha256(b).hexdigest()
def directory(run):
 if not re.fullmatch(r'[0-9]{1,20}',run):raise RuntimeError('Invalid run id')
 return DIR/run
def guard():
 if pwd.getpwuid(os.getuid()).pw_name!='zomorod2':raise RuntimeError('Unexpected account')
 for p in FILES:
  if not p.is_file() or p.is_symlink() or p.parent.is_symlink():raise RuntimeError('Invalid target '+str(p))
def transform(p,old):
 name=str(p.relative_to(ROOT));s=old.decode('utf-8')
 if MARKER in s or 'zm-priority-p0p3-20261019' not in s:raise RuntimeError('Unexpected base batch '+name)
 if s.count('</head>')!=1:raise RuntimeError('Invalid head '+name)
 if name=='about/index.html':
  tag='<h4>پژوهش و فناوری</h4>'
  if s.count(tag)!=1:raise RuntimeError('Missing first history heading')
  s=s.replace(tag,'<h3 class="zm-p0p3-history-heading">پژوهش و فناوری</h3>',1)
  mark='<aside><span>THE APPROACH</span>'
  if s.count(mark)!=1:raise RuntimeError('Missing nested landmark')
  s=s.replace(mark,'<aside role="note"><span>THE APPROACH</span>',1)
  s=s.replace('</head>','<style id="zm-p0p3-history-heading">.zm-p0p3-history-heading{font-size:17px;line-height:1.6;margin:0 0 8px;color:#f6dfa3}</style></head>',1)
 if name=='research/index.html':
  head='<header class="zm-v7-header" role="banner">'
  if s.count(head)!=1:raise RuntimeError('Expected one duplicate banner')
  s=s.replace(head,'<header class="zm-v7-header" role="none">',1)
  foot='<footer class="zm-footer">'
  if s.count(foot)!=1:raise RuntimeError('Expected one nested footer')
  s=s.replace(foot,'<footer class="zm-footer" role="none">',1)
 if name=='agriculture/index.html':
  # The original inline SVG/legacy stylesheet can override later author CSS; pin the short pill labels themselves.
  source='<a class="pill" href='
  assert s.count(source)>=3
  s=s.replace(source,'<a class="pill" style="color:#17372a!important;background-color:#e9eee5!important" href=')
  head='<header class="zm-v7-header" role="banner">'
  if s.count(head)!=1:raise RuntimeError('Expected one duplicate banner')
  s=s.replace(head,'<header class="zm-v7-header" role="none">',1)
  foot='<footer class="foot">'
  if s.count(foot)!=1:raise RuntimeError('Expected duplicate footer')
  s=s.replace(foot,'<footer class="foot" role="none">',1)
 return s.replace('</head>',STYLES[name]+'</head>',1).encode('utf-8')
def atomic(p,data,mode):
 tmp=None
 try:
  with tempfile.NamedTemporaryFile(dir=p.parent,prefix='.zm-p0p3-final-',delete=False) as f:
   tmp=Path(f.name);f.write(data);f.flush();os.fsync(f.fileno())
  os.chmod(tmp,mode);os.replace(tmp,p)
 finally:
  if tmp and tmp.exists():tmp.unlink()
def plan():
 guard()
 for p in FILES:
  b=p.read_bytes();n=transform(p,b)
  print('FINAL_PATCH_PLAN='+json.dumps({'path':str(p),'old':digest(b),'new':digest(n)},ensure_ascii=False),flush=True)
def apply(run):
 guard();out=directory(run)
 if out.exists():raise RuntimeError('Backup already exists')
 originals={p:p.read_bytes() for p in FILES}
 nexts={p:transform(p,originals[p]) for p in FILES}
 out.mkdir(parents=True,mode=0o700)
 rows=[]
 for i,p in enumerate(FILES):
  mode=p.stat().st_mode&0o777
  atomic(out/('before-'+str(i)+'.bin'),originals[p],0o600)
  assert digest((out/('before-'+str(i)+'.bin')).read_bytes())==digest(originals[p])
  rows.append({'file':str(p),'old':digest(originals[p]),'new':digest(nexts[p]),'mode':mode})
 (out/'manifest.json').write_text(json.dumps(rows,ensure_ascii=False))
 for p in FILES:
  if digest(p.read_bytes())!=digest(originals[p]):raise RuntimeError('Concurrent update')
 for p,row in zip(FILES,rows):
  atomic(p,nexts[p],row['mode'])
  assert digest(p.read_bytes())==row['new']
 print('FINAL_P0P3_A11Y_FILES_PUBLISHED='+str(len(FILES)),flush=True)
def verify(run):
 out=directory(run);rows=json.loads((out/'manifest.json').read_text())
 for i,row in enumerate(rows):
  assert str(FILES[i])==row['file']
  assert digest(FILES[i].read_bytes())==row['new']
  assert digest((out/('before-'+str(i)+'.bin')).read_bytes())==row['old']
 print('FINAL_A11Y_CHECKSUM_VERIFIED=yes',flush=True)
def rollback(run):
 out=directory(run)
 if not (out/'manifest.json').is_file():return
 rows=json.loads((out/'manifest.json').read_text());errors=[]
 for i,row in enumerate(rows):
  p=FILES[i];saved=(out/('before-'+str(i)+'.bin')).read_bytes()
  if digest(saved)!=row['old']:errors.append('backup damaged '+str(p));continue
  if digest(p.read_bytes())==row['old']:continue
  if digest(p.read_bytes())!=row['new']:errors.append('concurrent update '+str(p));continue
  atomic(p,saved,row['mode'])
 if errors:raise RuntimeError('Rollback incomplete: '+repr(errors))
 print('FINAL_A11Y_ORIGINAL_RESTORED=yes',flush=True)
if __name__=='__main__':
 cmd=sys.argv[1] if len(sys.argv)>1 else ''
 if cmd=='plan':plan()
 elif cmd=='apply':apply(sys.argv[2])
 elif cmd=='verify':verify(sys.argv[2])
 elif cmd=='rollback':rollback(sys.argv[2])
 elif cmd=='selftest':
  assert len(FILES)==3 and all(MARKER in v for v in STYLES.values());print('FINAL_A11Y_SELFTEST=passed')
 else:raise SystemExit('selftest|plan|apply RUN|verify RUN|rollback RUN')
