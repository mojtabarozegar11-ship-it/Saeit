#!/usr/bin/env python3
"""Reconcile existing MOJ PROP language SEO to truly equivalent educational variants.
Protected live one-shot migration; no dynamic/payment/factory routes.
"""
from __future__ import annotations
import getpass, hashlib, importlib.util, json, os, stat, sys, tempfile
from pathlib import Path
from html.parser import HTMLParser
from xml.etree import ElementTree as ET

SITE=Path("/home/zomorod2/mojplaywin.com")
PROP=SITE/"moj-prop"
BASE=PROP/"languages"
PROGRAM=PROP/"index.html"
SITEMAP=PROP/"sitemap.xml"
SELECTOR=BASE/"index.html"
NEW=BASE/"en"/"index.html"
BUILDER=Path("/home/zomorod2/mojprop_multilang_20261121_build.py")
PRIVATE=Path("/home/zomorod2/.private_mojplaywin_main_agents/mojprop_20_languages_equivalence_20261121")
MANIFEST=PRIVATE/"manifest.json"
EXPECTED_PROGRAM_SHA="c4419cae2a69391214146fb7dcc35c83edbfff76a41b26b248f60f7d42f4cce0"
EXPECTED_SITEMAP_SHA="ba4c344763c73731a15f7eaf9bceafa4181097140c955ca669afcb138a31e6fc"
EXPECTED_SELECTOR_SHA="a039c8716d15ff18aad97fa330c54106c28aff3984ed421437890b4c551795ac"

def sha(v):return hashlib.sha256(v).hexdigest()
def safe_replace(src, old, new, label):
 if src.count(old)!=1:raise RuntimeError(label+" unexpected count "+str(src.count(old)))
 return src.replace(old,new,1)
def write_atomic(p,raw,mode=0o644):
 temp=None
 try:
  with tempfile.NamedTemporaryFile(dir=p.parent,prefix=".mojprop-seo-",delete=False) as f:
   temp=Path(f.name);f.write(raw);f.flush();os.fsync(f.fileno())
  os.chmod(temp,mode)
  os.replace(temp,p)
 finally:
  if temp and temp.exists():temp.unlink()

def load_source():
 spec=importlib.util.spec_from_file_location("original_mojprop_20_languages",str(BUILDER))
 mod=importlib.util.module_from_spec(spec)
 assert spec.loader is not None
 spec.loader.exec_module(mod)
 return mod

def prepare():
 if not PROP.is_dir() or PROP.is_symlink() or BASE.is_symlink():
  raise RuntimeError("Unsafe root")
 mod=load_source()
 original_path=mod.path
 original_hreflang=mod.hreflangs()
 new_path=lambda c: "/moj-prop/languages/en/" if c=="en" else original_path(c)
 def valid_hreflangs():
  return "\n".join('<link rel="alternate" hreflang="'+c+'" href="https://mojplaywin.com'+new_path(c)+'">' for c in mod.VALID)+'\n<link rel="alternate" hreflang="x-default" href="https://mojplaywin.com/moj-prop/languages/">'
 mod.path=new_path
 mod.hreflangs=valid_hreflangs
 result={}
 for item in mod.L:
  code=item[0]
  file=BASE/code.lower()/"index.html"
  if file.is_symlink() or not file.is_file():raise RuntimeError("Locale missing or unsafe "+code)
  # Avoid overwriting edits concurrent with previous launch.
  old_module=load_source()
  expected=old_module.localized(item).encode("utf8")
  have=file.read_bytes()
  if have!=expected:
   raise RuntimeError("Locale content drift "+code+" current_sha "+sha(have)+" expected_sha "+sha(expected))
  result[file]=mod.localized(item).encode("utf8")
  if result[file]==have:raise RuntimeError("No locale update "+code)
 if NEW.exists() or NEW.is_symlink() or NEW.parent.exists():
  raise RuntimeError("English guide already exists")
 title="MOJ PROP: Simulated Trading Challenge and Risk Management"
 english_item=[
 "en","English",title,
 "Explore simulated trading evaluations with a virtual reference balance, structured risk controls and a written trading journal. The challenge is about discipline, not promised profit.",
 "MOJ PROP describes a starting virtual reference balance of $1,000 for a simulated evaluation. This is not a customer deposit and it does not automatically grant a live brokerage account. The official English MOJ PROP program page determines eligibility, product terms and availability.",
 "For illustration, 1% of a $1,000 virtual reference balance is $10 of simulated loss exposure, while 3% is $30. Before each practice trade, record the entry rationale, invalidation point, stop level, maximum expected loss, and remaining daily and overall drawdown capacity.",
 "Read the current rules before acting, record hypothetical entries and exits, and review losses, concentration of returns, consistency, and rule adherence. Starter30 is a separate educational product and should not be confused with the proposed primary challenge.",
 "Is this a real funded brokerage account? No. A simulated evaluation by itself guarantees neither profit nor payment nor access to real capital. Verify program status, eligibility and any official server-issued invoice before paying.",
 "Educational information only; not personalized financial advice, an offer of customer capital management, or a guarantee of earnings. Current program terms and availability are controlled by the English official page.",
 "Visit official English MOJ PROP program"
 ]
 eng_guide=mod.localized(english_item)
 if "<h1>"+title+"</h1>" not in eng_guide:
  raise RuntimeError("New English guide invalid")
 result[NEW]=eng_guide.encode("utf8")

 english=PROGRAM.read_bytes()
 if sha(english)!=EXPECTED_PROGRAM_SHA:raise RuntimeError("English primary page drift")
 oldhead="\n"+original_hreflang
 if english.decode().count(oldhead)!=1:
  raise RuntimeError("Original program hreflang not uniquely present")
 # This program is different in depth and intent from the 20 educational landing pages.
 # Keep links to the guide but stop falsely representing it as a translated version.
 english_after=english.decode().replace(oldhead,"",1)
 result[PROGRAM]=english_after.encode("utf8")

 selector=SELECTOR.read_bytes()
 if sha(selector)!=EXPECTED_SELECTOR_SHA:raise RuntimeError("Selector drift")
 selector_new=safe_replace(selector.decode(),'</head>','\n'+valid_hreflangs()+'\n</head>',"selector head")
 oldenglish='<a href="/moj-prop/" lang="en">English</a>'
 newenglish='<a href="/moj-prop/languages/en/" lang="en">English</a>'
 selector_new=safe_replace(selector_new,oldenglish,newenglish,"English guide directory link")
 result[SELECTOR]=selector_new.encode("utf8")

 sitemap=SITEMAP.read_bytes()
 if sha(sitemap)!=EXPECTED_SITEMAP_SHA:raise RuntimeError("Sitemap drift")
 sitemap_new=safe_replace(sitemap.decode(),"</urlset>",'<url><loc>https://mojplaywin.com/moj-prop/languages/en/</loc></url></urlset>',"sitemap close")
 ET.fromstring(sitemap_new)
 if sitemap_new.count("<loc>")!=35:raise RuntimeError("Sitemap URL count unexpected")
 result[SITEMAP]=sitemap_new.encode("utf8")

 # Validate all expected reciprocal variants.
 expected_alts=valid_hreflangs()
 for p,raw in result.items():
  s=raw.decode()
  if p in (PROGRAM,SITEMAP):continue
  if p==SELECTOR:
   if s.count(expected_alts)!=1:raise RuntimeError("Selector alternate mismatch")
   continue
  if p.name!="index.html":raise RuntimeError("Unexpected route")
  if p.parent.name=="pcm":
   if 'hreflang=' in s:raise RuntimeError("Unsupported pidgin code annotated")
  elif s.count(expected_alts)!=1:
   raise RuntimeError("Reciprocal alternate mismatch "+str(p))
  if not ('<link rel="canonical" href="https://mojplaywin.com/moj-prop/languages/'+p.parent.name+'/">' in s):
   raise RuntimeError("Wrong self-canonical "+str(p))
  if s.count('href="/moj-prop/languages/en/"')<1:
   raise RuntimeError("English language choice missing "+str(p))
 return result

def run():
 if getpass.getuser()!="zomorod2":raise RuntimeError("Wrong cPanel account")
 result=prepare()
 original={str(p):{'sha':sha(p.read_bytes()),'bytes':len(p.read_bytes()),'mode':stat.S_IMODE(p.stat().st_mode)} for p in result if p!=NEW}
 receipt={'status':'prepared','scope':'MOJ_PROP_20_language_educational_equivalence_only',
  'before':original,'after':{str(p):sha(data) for p,data in result.items()},
  'new':str(NEW),'count':len(result)}
 print("CANDIDATE_OK",json.dumps({'files':len(result),'locales':20,'sitemap_urls':35,'english_guide':str(NEW)}))
 if sys.argv[1]=="--check":return
 if sys.argv[1]!="--apply":raise RuntimeError("Usage: --check|--apply")
 if PRIVATE.exists() or PRIVATE.is_symlink():raise RuntimeError("Refusing to reuse backup")
 PRIVATE.mkdir(parents=True,mode=0o700)
 os.chmod(PRIVATE,0o700)
 for i,p in enumerate([x for x in result if x!=NEW]):
  b=PRIVATE/("original_"+str(i).zfill(2)+".bin")
  b.write_bytes(p.read_bytes());os.chmod(b,0o600)
  if sha(b.read_bytes())!=original[str(p)]['sha']:
   raise RuntimeError("Backup SHA mismatch "+str(p))
  original[str(p)]['backup']=str(b)
 MANIFEST.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
 os.chmod(MANIFEST,0o600)
 for p in result:
  if p==NEW:continue
  if sha(p.read_bytes())!=original[str(p)]['sha']:
   raise RuntimeError("Concurrent changes; refusing publish")
 completed=[]
 try:
  NEW.parent.mkdir(mode=0o755)
  write_atomic(NEW,result[NEW])
  completed.append(NEW)
  for p,raw in result.items():
   if p==NEW:continue
   write_atomic(p,raw,original[str(p)]['mode'])
   completed.append(p)
  for p,raw in result.items():
   if sha(p.read_bytes())!=sha(raw):raise RuntimeError("Post-publish SHA mismatch "+str(p))
  receipt['status']='published'
  MANIFEST.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
  print("PUBLISHED_EQUIVALENT_20_LOCALES=YES","BACKUP_VERIFIED=YES","FILES",len(result))
 except Exception:
  # Restore modified originals only if they still match bytes we wrote.
  for p in reversed(completed):
   if p==NEW:continue
   if sha(p.read_bytes())==receipt['after'][str(p)]:
    write_atomic(p,Path(original[str(p)]['backup']).read_bytes(),original[str(p)]['mode'])
  raise

if __name__=="__main__":
 if len(sys.argv)!=2:raise SystemExit("Usage: --check or --apply")
 run()
