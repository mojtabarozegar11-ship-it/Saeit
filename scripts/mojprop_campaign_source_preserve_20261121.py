#!/usr/bin/env python3
"""One-shot 20-language SEO campaign-preservation fix, with SHA backup.
Only preserves bounded non-personal attribution across internal page links.
No payment logic, personal data, local storage, database, factory or email changes.
"""
from __future__ import annotations
import os,sys,hashlib,json,getpass,tempfile,stat,subprocess
from pathlib import Path
ROOT=Path('/home/zomorod2/mojplaywin.com/moj-prop/languages')
OLD_RECEIPT=Path('/home/zomorod2/.private_mojplaywin_main_agents/mojprop_locale_starter30_attribution_20261121/manifest.json')
PRIVATE=Path('/home/zomorod2/.private_mojplaywin_main_agents/mojprop_attribution_source_preserve_20261121')
RECEIPT=PRIVATE/'manifest.json'
HUB=ROOT/'index.html'
JS=ROOT/'source-preserve.js'
HUB_SHA='655a9a968c617ab7f2f347e26f98dca1f268b3048d60a324bc42c0956845330b'
CODES=('en','zh','hi','es','ar','fr','bn','pt','id','ur','ru','de','ja','ar-eg','mr','vi','te','sw','tr','pcm')
INCLUDE='<script defer src="/moj-prop/languages/source-preserve.js"></script>'
SCRIPT=r'''(function(){
"use strict";
// Preserve only approved campaign names. No visitor identity, cookies or storage.
var allowed=/^[A-Za-z0-9_.:-]+$/;
function safe(s,max){return typeof s==="string"&&s.length>0&&s.length<=max&&allowed.test(s)?s:"";}
var query=new URLSearchParams(window.location.search);
var source=safe(query.get("utm_source"),40);
if(!source||source==="mojprop_locale")return;
var medium=safe(query.get("utm_medium"),40)||"referral";
var campaign=safe(query.get("utm_campaign"),80)||"unknown";
var content=safe(query.get("utm_content"),80);
var m=window.location.pathname.match(/^\/moj-prop\/languages\/([a-z-]+)\/$/);
var code=m&&m[1]!=="source-preserve.js"?m[1]:null;
var locales="|en|zh|hi|es|ar|fr|bn|pt|id|ur|ru|de|ja|ar-eg|mr|vi|te|sw|tr|pcm|";
if(code&&locales.indexOf("|"+code+"|")<0)return;
var all=document.querySelectorAll("a[href]");
for(var i=0;i<all.length;i++){
 var a=all[i],href=a.getAttribute("href"),url;
 if(!href||href[0]!=="/"||href[1]==="/")continue;
 try{url=new URL(href,window.location.origin);}catch(ignore){continue;}
 if(url.origin!==window.location.origin)continue;
 var isLanguage=/^\/moj-prop\/languages\/(?:[a-z-]+\/)?$/.test(url.pathname);
 var isStarter=!!code&&url.pathname==="/moj-prop/starter-30-trx/"&&
     a.getAttribute("data-mpw-locale-event")==="starter30";
 var isProgram=!!code&&url.pathname==="/moj-prop/"&&
     a.getAttribute("data-mpw-locale-event")==="program";
 if(!isLanguage&&!isStarter&&!isProgram)continue;
 var outCampaign=(isStarter||isProgram)?
   ("lang_"+code.replace("-","_")+"__"+campaign).slice(0,80):campaign;
 url.searchParams.set("utm_source",source);
 url.searchParams.set("utm_medium",medium);
 url.searchParams.set("utm_campaign",outCampaign);
 if(isStarter){url.searchParams.set("utm_content","starter30_terms");}
 else if(content){url.searchParams.set("utm_content",content);}
 a.setAttribute("href",url.pathname+url.search+url.hash);
}
})();'''
def sha(v):return hashlib.sha256(v).hexdigest()
def atom(path,data,mode):
 temp=None
 try:
  with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.mpw-source-preserve-',mode='wb',delete=False) as f:
   temp=Path(f.name);f.write(data);f.flush();os.fsync(f.fileno())
  os.chmod(temp,mode)
  os.replace(temp,path)
 finally:
  if temp and temp.exists():temp.unlink()
def prepare():
 if getpass.getuser()!='zomorod2':raise RuntimeError('Not expected hosting owner')
 if PRIVATE.exists() or PRIVATE.is_symlink():raise RuntimeError('Already performed; refuse overwrite')
 if JS.exists() or JS.is_symlink():raise RuntimeError('New JS destination already present')
 if sha(HUB.read_bytes())!=HUB_SHA or HUB.is_symlink():raise RuntimeError('Chooser drift')
 if not OLD_RECEIPT.is_file():raise RuntimeError('Missing earlier release manifest')
 previous=json.loads(OLD_RECEIPT.read_text())
 if previous['status']!='published':raise RuntimeError('Earlier release not published')
 updates={}
 for code in (None,)+CODES:
  p=HUB if code is None else ROOT/code/'index.html'
  b=p.read_bytes()
  if p.is_symlink():raise RuntimeError('Symlink page rejected')
  if code and sha(b)!=previous['after'].get(str(p)):raise RuntimeError('Concurrent locale edits '+code)
  html=b.decode('utf8')
  if html.count('</body></html>')!=1:raise RuntimeError('Unexpected closing body '+str(p))
  if INCLUDE in html:raise RuntimeError('Already included')
  if code:
   if html.count('data-mpw-locale-event="program"')!=1 or html.count('data-mpw-locale-event="starter30"')!=1:
    raise RuntimeError('CTA changed '+code)
  elif html.count('href="/moj-prop/languages/en/"')!=1:
   raise RuntimeError('Language selector changed')
  next_html=html.replace('</body></html>',INCLUDE+'</body></html>',1)
  if next_html.count('rel="canonical"')!=1:raise RuntimeError('Canonical mismatch')
  updates[p]=next_html.encode('utf8')
 if len(updates)!=21:raise RuntimeError('Expected 21 HTML files')
 # Syntax parse is safe and read-only; script does not touch external domains.
 test=subprocess.run(['node','--check'],input=SCRIPT,capture_output=True,text=True,timeout=8)
 if test.returncode!=0:raise RuntimeError('Node syntax invalid '+test.stderr[:200])
 return updates
def run():
 if len(sys.argv)!=2 or sys.argv[1] not in ('--check','--apply'):raise SystemExit('usage: --check|--apply')
 changes=prepare()
 print('READY',len(changes),'HTML_FILES','SAFE_SCRIPT',len(SCRIPT),'PRESERVES_EXTERNAL_CAMPAIGN',True)
 if sys.argv[1]=='--check':return
 PRIVATE.mkdir(mode=0o700,parents=True);os.chmod(PRIVATE,0o700)
 copies=PRIVATE/'backups';copies.mkdir(mode=0o700)
 before={}
 for i,p in enumerate(changes):
  old=p.read_bytes()
  file=copies/('original_%02d.bin'%i)
  file.write_bytes(old);os.chmod(file,0o600)
  if sha(file.read_bytes())!=sha(old):raise RuntimeError('Backup verification failed')
  before[str(p)]={'sha':sha(old),'mode':stat.S_IMODE(p.stat().st_mode),'backup':str(file)}
 receipt={'status':'prepared','before':before,'after':{str(p):sha(v) for p,v in changes.items()},
  'new_js':str(JS),'js_sha':sha(SCRIPT.encode()),'scope':'preserve_external_social_campaign_20_language_funnel'}
 RECEIPT.write_text(json.dumps(receipt,indent=2)+'\n');os.chmod(RECEIPT,0o600)
 done=[]
 try:
  for p in changes:
   if sha(p.read_bytes())!=before[str(p)]['sha']:raise RuntimeError('Concurrent file mutation')
  atom(JS,SCRIPT.encode('utf8'),0o644)
  done.append(JS)
  for p,data in changes.items():
   atom(p,data,before[str(p)]['mode'])
   done.append(p)
  if sha(JS.read_bytes())!=receipt['js_sha']:raise RuntimeError('JS publish mismatch')
  for p,data in changes.items():
   if sha(p.read_bytes())!=sha(data):raise RuntimeError('HTML publish mismatch')
  receipt['status']='published'
  RECEIPT.write_text(json.dumps(receipt,indent=2)+'\n')
  print('PUBLISHED',len(changes),'HTML','JS',1,'BACKUPS',len(before),'SHA_OK')
 except Exception:
  for p in reversed(done):
   if p==JS:
    if p.exists() and sha(p.read_bytes())==receipt['js_sha']:p.unlink()
   elif sha(p.read_bytes())==receipt['after'][str(p)]:
    v=before[str(p)]
    atom(p,Path(v['backup']).read_bytes(),v['mode'])
  raise
if __name__=='__main__':run()
