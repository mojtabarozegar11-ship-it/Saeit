#!/usr/bin/env python3
"""One-shot protected release: locale-to-Starter30 terms attribution, no checkout code edits."""
from pathlib import Path
from html import escape
from urllib.parse import urlencode
import os,sys,json,hashlib,getpass,tempfile,stat,urllib.request,re
SITE=Path('/home/zomorod2/mojplaywin.com')
LANG=SITE/'moj-prop/languages'
PRODUCT=SITE/'moj-prop/starter-30-trx/index.html'
PRODUCT_JS=SITE/'moj-prop/starter-30-trx/checkout-attribution.js'
PRIOR=Path('/home/zomorod2/.private_mojplaywin_main_agents/mojprop_global_funnel_20261121/release_receipt.json')
PRIVATE=Path('/home/zomorod2/.private_mojplaywin_main_agents/mojprop_locale_starter30_attribution_20261121')
MANIFEST=PRIVATE/'manifest.json'
CODES=('en','zh','hi','es','ar','fr','bn','pt','id','ur','ru','de','ja','ar-eg','mr','vi','te','sw','tr','pcm')
OLD='data-mpw-locale-event="starter30" href="/moj-prop/starter-30-trx/"'
ROOT_LINK='/moj-prop/starter-30-trx/'
def sha(data):return hashlib.sha256(data).hexdigest()
def atom(p,data,mode):
 temp=None
 try:
  with tempfile.NamedTemporaryFile('wb',dir=p.parent,prefix='.mojprop-locale-cta-',delete=False) as f:
   temp=Path(f.name)
   f.write(data);f.flush();os.fsync(f.fileno())
  os.chmod(temp,mode)
  os.replace(temp,p)
 finally:
  if temp is not None and temp.exists():temp.unlink()
def prep():
 if getpass.getuser()!='zomorod2':raise RuntimeError('Unsafe account')
 if PRIVATE.exists() or PRIVATE.is_symlink():raise RuntimeError('Already released; refuse overwrite')
 if not PRIOR.is_file():raise RuntimeError('Prior manifest unavailable')
 record=json.loads(PRIOR.read_text())
 if record.get('status')!='published':raise RuntimeError('Prior release incomplete')
 if not PRODUCT.is_file() or not PRODUCT_JS.is_file():raise RuntimeError('Landing or forwarding asset missing')
 product=PRODUCT.read_text(encoding='utf8')
 js=PRODUCT_JS.read_text(encoding='utf8')
 if product.count('src="/moj-prop/starter-30-trx/checkout-attribution.js"')!=1:
  raise RuntimeError('Attribution script not attached')
 if product.count('href="/mojprop-starter30-checkout/"')!=1:
  raise RuntimeError('Terms page checkout link drift')
 if not all(s in js for s in (
  "var allowed = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content'];",
  "url.pathname !== '/mojprop-starter30-checkout/'",
  "url.searchParams.set(key, inputs[key])",
  "url.origin !== window.location.origin")):
  raise RuntimeError('Forwarding script does not match known safe behavior')
 updates={}
 original={}
 for code in CODES:
  path=LANG/code/'index.html'
  if not path.is_file() or path.is_symlink():raise RuntimeError('Missing/unsafe locale '+code)
  old=path.read_bytes()
  if sha(old)!=record['after'].get(str(path)):
   raise RuntimeError('Locale drift '+code)
  s=old.decode('utf8')
  if s.count(OLD)!=1:raise RuntimeError('Existing CTA drift '+code)
  if s.count('data-mpw-locale-event="program" href="/moj-prop/"')!=1:
   raise RuntimeError('Program CTA unexpectedly changed '+code)
  if s.count('rel="canonical"')!=1 or s.count('id="mojprop-global-cta-events-20261121"')!=1:
   raise RuntimeError('SEO or event hook missing '+code)
  query=urlencode({
   'utm_source':'mojprop_locale',
   'utm_medium':'onsite',
   'utm_campaign':'lang_'+code.replace('-','_'),
   'utm_content':'starter30_terms'
  })
  destination=ROOT_LINK+'?'+query
  replacement='data-mpw-locale-event="starter30" href="'+escape(destination,quote=True)+'"'
  updated=s.replace(OLD,replacement,1)
  if updated.count('rel="canonical"')!=1:
   raise RuntimeError('Canonical drift')
  if 'data-mpw-locale-event="program" href="/moj-prop/"' not in updated:
   raise RuntimeError('Program CTA drift')
  if any(' ' in value for value in query.split('&')):
   raise RuntimeError('Invalid campaign')
  updates[path]=updated.encode('utf8')
  original[str(path)]={'sha':sha(old),'mode':stat.S_IMODE(path.stat().st_mode)}
 if len(updates)!=20:raise RuntimeError('Incomplete locale set')
 return updates,original
def run():
 if len(sys.argv)!=2 or sys.argv[1] not in ('--check','--apply'):raise SystemExit('Usage: --check or --apply')
 updates,original=prep()
 print('READY',len(updates),'LOCALE_TERMS_LINKS','INTEGRITY',True,'CHECKOUT_UNCHANGED',True)
 if sys.argv[1]=='--check':return
 PRIVATE.mkdir(mode=0o700,parents=True)
 os.chmod(PRIVATE,0o700)
 backups=PRIVATE/'backups';backups.mkdir(mode=0o700)
 for i,p in enumerate(updates):
  b=backups/('old_%02d.bin'%i)
  b.write_bytes(p.read_bytes());os.chmod(b,0o600)
  if sha(b.read_bytes())!=original[str(p)]['sha']:raise RuntimeError('Backup checksum failed '+str(p))
  original[str(p)]['backup']=str(b)
 receipt={'status':'prepared','scope':'locale_starter30_terms_link_only','before':original,
          'after':{str(p):sha(data) for p,data in updates.items()},'locale_count':len(updates),
          'no_checkout_payment_db_or_factory_changes':True}
 MANIFEST.write_text(json.dumps(receipt,indent=2)+'\n')
 os.chmod(MANIFEST,0o600)
 for p in updates:
  if sha(p.read_bytes())!=original[str(p)]['sha']:raise RuntimeError('Concurrent modification '+str(p))
 finished=[]
 try:
  for p,data in updates.items():
   atom(p,data,original[str(p)]['mode']);finished.append(p)
  for p,data in updates.items():
   if sha(p.read_bytes())!=sha(data):raise RuntimeError('Post-write mismatch '+str(p))
  receipt['status']='published'
  MANIFEST.write_text(json.dumps(receipt,indent=2)+'\n')
  print('PUBLISHED',len(finished),'LOCALES','BACKUP_SHA_VERIFIED','PRODUCT_JS_EXISTING')
 except BaseException:
  for p in reversed(finished):
   item=original[str(p)]
   if sha(p.read_bytes())==receipt['after'][str(p)]:
    atom(p,Path(item['backup']).read_bytes(),item['mode'])
  raise
if __name__=='__main__':run()
