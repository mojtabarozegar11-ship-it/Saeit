#!/usr/bin/env python3
"""One-transaction, reversible fix for Zomorod residual WCAG regions + minimally enforcing CSP."""
from __future__ import annotations
import hashlib,json,os,pwd,re,sys,tempfile
from pathlib import Path
ROOT=Path('/home/zomorod2/public_html')
BACKUP=Path('/home/zomorod2/.backups/zomorod-final-safe-hardening-20261019')
FILES=[ROOT/'research/index.html',ROOT/'agriculture/index.html',ROOT/'.htaccess']
OLD_HEADER='<header class="zm-v7-header" role="none">'
NEW_HEADER='<header class="zm-v7-header" role="navigation" aria-label="هویت و ناوبری زمرد ملل">'
OLD_POLICY='Header always set Content-Security-Policy-Report-Only "base-uri \'self\'; object-src \'none\'"'
NEW_POLICY='Header always append Content-Security-Policy "base-uri \'self\'; object-src \'none\'"'
OLD_HSTS='Header always set Strict-Transport-Security "max-age=300"'
NEW_HSTS='Header always set Strict-Transport-Security "max-age=86400"'
ADD='Header always set Referrer-Policy "strict-origin-when-cross-origin"'
IDENTIFIER='ZM_FINAL_SECURITY_HARDENING_20261019'
def sha(data):return hashlib.sha256(data).hexdigest()
def outdir(run):
 if not re.fullmatch(r'[0-9]{1,20}',run):raise RuntimeError('Bad run id')
 return BACKUP/run
def guard():
 if pwd.getpwuid(os.getuid()).pw_name!='zomorod2':raise RuntimeError('Wrong account')
 if ROOT.is_symlink() or BACKUP.is_symlink():raise RuntimeError('Unsafe folder')
 for p in FILES:
  if not p.is_file() or p.is_symlink() or p.parent.is_symlink():raise RuntimeError('Unsafe target: '+str(p))
def transform(path,old):
 s=old.decode('utf-8')
 if path.name=='.htaccess':
  for oldstring in [OLD_POLICY,OLD_HSTS]:
   if s.count(oldstring)!=1:raise RuntimeError('Header baseline mismatch')
  if IDENTIFIER in s:raise RuntimeError('Already installed')
  assert 'PassengerAppRoot' in s and 'RewriteRule ^$ index.html' in s
  s=s.replace(OLD_POLICY,NEW_POLICY,1).replace(OLD_HSTS,NEW_HSTS,1)
  s=s.rstrip('\n')+'\n# '+IDENTIFIER+'\n'+ADD+'\n'
 else:
  if 'zm-p0p3-final-a11y-20261019' not in s:raise RuntimeError('Unexpected existing version')
  if s.count(OLD_HEADER)!=1:raise RuntimeError('Could not identify precisely one site identity header')
  if 'zm-v7-chain' not in s or 'role="contentinfo"' not in s:raise RuntimeError('Expected safe landmarks absent')
  s=s.replace(OLD_HEADER,NEW_HEADER,1)
 return s.encode('utf-8')
def atomic(path,data,mode):
 temp=None
 try:
  with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.zm-hardening-',delete=False) as f:
   temp=Path(f.name);f.write(data);f.flush();os.fsync(f.fileno())
  os.chmod(temp,mode);os.replace(temp,path)
 finally:
  if temp and temp.exists():temp.unlink()
def selftest():
 assert NEW_POLICY.startswith('Header always append Content-Security-Policy ')
 assert "'unsafe-inline'" not in NEW_POLICY and "'unsafe-eval'" not in NEW_POLICY
 assert 'includeSubDomains' not in NEW_HSTS
 page='<html><head></head><body><header class="zm-v7-header" role="none"><nav class="zm-v7-chain"></nav></header><footer role="contentinfo"></footer><!-- zm-p0p3-final-a11y-20261019 --></body></html>'
 assert NEW_HEADER in transform(FILES[0],page.encode()).decode()
 sample=('PassengerAppRoot "test"\nRewriteRule ^$ index.html [END]\n'+OLD_POLICY+'\n'+OLD_HSTS+'\n').encode()
 x=transform(FILES[2],sample).decode()
 assert NEW_POLICY in x and NEW_HSTS in x and ADD in x
 print('FINAL_HARDENING_SELFTEST=passed',flush=True)
def plan():
 guard()
 for p in FILES:
  before=p.read_bytes();after=transform(p,before)
  print('HARDENING_PLAN='+json.dumps({'file':str(p),'old':sha(before),'new':sha(after),'bytes_delta':len(after)-len(before)},ensure_ascii=False),flush=True)
def install(run):
 guard()
 d=outdir(run)
 if d.exists() or d.is_symlink():raise RuntimeError('Duplicate backup')
 original={p:p.read_bytes() for p in FILES}
 changes={p:transform(p,original[p]) for p in FILES}
 d.mkdir(parents=True,mode=0o700)
 manifest=[]
 for i,p in enumerate(FILES):
  atomic(d/('before-'+str(i)+'.bin'),original[p],0o600)
  assert sha((d/('before-'+str(i)+'.bin')).read_bytes())==sha(original[p])
  manifest.append({'file':str(p),'before':sha(original[p]),'after':sha(changes[p]),'mode':p.stat().st_mode&0o777})
 (d/'manifest.json').write_text(json.dumps(manifest))
 for p in FILES:
  if sha(p.read_bytes())!=sha(original[p]):raise RuntimeError('Concurrent change detected')
 for p,m in zip(FILES,manifest):
  atomic(p,changes[p],m['mode'])
  assert sha(p.read_bytes())==m['after']
 print('FINAL_HARDENING_APPLIED='+str(len(FILES)),flush=True)
def verify(run):
 guard();d=outdir(run);data=json.loads((d/'manifest.json').read_text())
 for i,m in enumerate(data):
  p=FILES[i]
  if m['file']!=str(p) or sha(p.read_bytes())!=m['after'] or sha((d/('before-'+str(i)+'.bin')).read_bytes())!=m['before']:
   raise RuntimeError('Checksum verification failure '+str(p))
 print('FINAL_HARDENING_SHA_VERIFIED=yes',flush=True)
def rollback(run):
 guard();d=outdir(run)
 if not (d/'manifest.json').is_file():print('NO_HARDENING_TO_REVERT=yes');return
 manifest=json.loads((d/'manifest.json').read_text());issues=[]
 for i,m in enumerate(manifest):
  p=FILES[i];saved=(d/('before-'+str(i)+'.bin')).read_bytes()
  if sha(saved)!=m['before']:issues.append('bad backup '+str(p));continue
  current=sha(p.read_bytes())
  if current==m['before']:continue
  if current!=m['after']:issues.append('concurrent change '+str(p));continue
  atomic(p,saved,m['mode'])
  if sha(p.read_bytes())!=m['before']:issues.append('restore mismatch '+str(p))
 if issues:raise RuntimeError('Rollback incomplete: '+repr(issues))
 print('FINAL_HARDENING_ROLLBACK_COMPLETE=yes',flush=True)
if __name__=='__main__':
 cmd=sys.argv[1] if len(sys.argv)>1 else ''
 if cmd=='selftest':selftest()
 elif cmd=='plan':plan()
 elif cmd=='apply':install(sys.argv[2])
 elif cmd=='verify':verify(sys.argv[2])
 elif cmd=='rollback':rollback(sys.argv[2])
 else:raise SystemExit('selftest | plan | apply RUN | verify RUN | rollback RUN')
