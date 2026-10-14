#!/usr/bin/env python3
"""Read-only, no Django startup: compare deployed Zomorod code to on-host V91 variants."""
import ast,collections,hashlib,json,os,pathlib,re,socket,sqlite3,time
from pathlib import Path
H=Path("/home/zomorod2")
ROOTS={
 "LIVE_ZOMOROD":H/"Saeit",
 "V91_ORIGINAL":H/"saeit_v91"/"zomorodmelal",
 "V91_RUNTIME_STAGE":H/"saeit_v91_runtime_stage_20261012"/"zomorodmelal",
 "V91_STAFF_ISOLATED":H/"Saeit-staging"/"v91_personnel_isolated"/"staff-22790e223ec4cfc1"/"zomorodmelal",
 "GENERAL_STAGING":H/"Saeit-staging",
}
EXTS={".py",".html",".htm",".css",".js",".mjs",".json",".webp",".png",".jpg",".jpeg",".svg",".xml",".ico",".yaml",".yml",".txt",".md",".woff2"}
CODE_EXTS={".py",".html",".htm",".css",".js",".mjs",".json",".yaml",".yml",".xml"}
SKIP_DIRS={".git",".venv","venv","node_modules","__pycache__","backups","backup","media","staticfiles","dist","build",".pytest_cache",".mypy_cache","gallery","uploads","logs",".next","out","tmp","temp","releases","site-packages","storage","archives","artifacts"}
SKIP_FILES={".env",".env.local",".env.production","db.sqlite3","db.sqlite3-journal","secrets.json","credentials.json"}
MAX_SIZE=15_000_000
KEY_PATHS=[
"manage.py","passenger_wsgi.py","config/settings.py","config/urls.py","portal/models.py","portal/admin.py","portal/urls.py","portal/views.py",
"core/models.py","core/admin.py","core/urls.py","core/views.py","command_center/urls.py","command_center/views.py","command_center/models.py",
"moj/modern_site.py","moj/site_views.py","moj/site_builder.py","moj/json_content_admin.py","moj/gallery_reports_20261014.py",
"templates/modern/pages/company-gallery.html","templates/modern/partials/zomorod_gallery_20261014.html","templates/modern/zomorod_report_20261014.html",
"static/site/company/company-logo.png","static/site/company/company-hero.webp","static/site/company-gallery.css",".htaccess",
]
CHECK_TOKENS=["company-gallery","workshop-login","personnel/site-builder","admin/site-content","mojtaba.roozegar","staff/command-center","newsletter","blog","language","media/","knowledge/","api/v1/","payment","robots.txt","sitemap.xml"]
def say(kind,value):
 print("AUDIT_JSON "+json.dumps({"kind":kind,"data":value},ensure_ascii=False,sort_keys=True,default=str),flush=True)
MAX_FILES_PER_ROOT=1200
MAX_ROOT_SECONDS=18
ALLOWED_TOP={"config","portal","core","moj","command_center","templates","static","tests","scripts","deploy","editorial","financial_core"}
MANIFEST_STAT={}
def manifest(root):
 files={}
 start=time.monotonic()
 stats={"limit_files":MAX_FILES_PER_ROOT,"limit_sec":MAX_ROOT_SECONDS,"truncated":False,"visited_dirs":0}
 if not root.is_dir():return files
 def record(p):
  if p.is_symlink() or not p.is_file():return
  try:
   if p.name in SKIP_FILES or p.name.startswith(".env") or (p.suffix.lower() not in EXTS and p.name!=".htaccess"):return
   n=p.stat().st_size
   if n>1_500_000:return
   rel=str(p.relative_to(root))
   if rel not in files:
    h=hashlib.sha256(p.read_bytes()).hexdigest()
    files[rel]={"sha":h,"size":n,"ext":p.suffix.lower()}
  except (OSError,PermissionError):pass
 for name in KEY_PATHS:
  record(root/name)
 for path in root.iterdir():
  if path.is_file() and not path.name.startswith("."):
   record(path)
 for dirpath,dirs,names in os.walk(root,followlinks=False):
  stats["visited_dirs"]+=1
  rel=Path(dirpath).relative_to(root)
  depth=len(rel.parts) if str(rel)!="." else 0
  if depth>5:
   dirs[:]=[]
   continue
  if depth==0:
   dirs[:]=sorted(d for d in dirs if d in ALLOWED_TOP)
  else:
   dirs[:]=sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith("."))
  for name in names:
   if name.startswith(".") and name!=".htaccess":continue
   record(Path(dirpath)/name)
   if len(files)>=MAX_FILES_PER_ROOT or (time.monotonic()-start)>MAX_ROOT_SECONDS:
    stats["truncated"]=True
    MANIFEST_STAT[str(root)]=stats
    return files
  if (time.monotonic()-start)>MAX_ROOT_SECONDS:
   stats["truncated"]=True
   MANIFEST_STAT[str(root)]=stats
   return files
 MANIFEST_STAT[str(root)]=stats
 return files

def excerpt_models(root):
 out={}
 for relative in ["portal/models.py","core/models.py","command_center/models.py"]:
  p=root/relative
  if p.is_file():
   try:
    t=ast.parse(p.read_text(encoding="utf-8",errors="replace"))
    out[relative]=[n.name for n in t.body if isinstance(n,ast.ClassDef)][:120]
   except Exception as e:out[relative]="SYNTAX_ERROR "+type(e).__name__
 return out
def routes(root):
 p=root/"config/urls.py"
 if not p.is_file():return {}
 t=p.read_text(errors="replace")
 return {"bytes":len(t),"literal_path_matches":sorted(set(re.findall(r'path\s*\(\s*["\x27]([^"\x27]*)',t)))[:140],
         "keywords":{term:(term in t) for term in CHECK_TOKENS},
         "includes":[x.strip()[:100] for x in t.splitlines() if re.search(r'include\(|urlpatterns\s*\+?=',x)][:16]}
def migration_names(root):
 found={}
 for app in ["portal","core","command_center","moj"]:
  p=root/app/"migrations"
  if p.exists():
   names=sorted(f.name for f in p.glob("*.py") if not f.name.startswith("__"))
   found[app]={"count":len(names),"head":names[:5],"tail":names[-7:]}
 return found
def syntax(root,files):
 good=0; errors=[]
 for name,meta in files.items():
  if not name.endswith(".py") or meta["size"]>1_000_000:continue
  try:compile((root/name).read_bytes(),name,"exec");good+=1
  except (SyntaxError,ValueError,UnicodeError) as e:errors.append({"file":name,"error":type(e).__name__,"line":getattr(e,"lineno",None)})
 return {"checked_py":good+len(errors),"syntax_errors":errors[:22],"error_count":len(errors)}
def scripts(root):
 hits=[]
 for f in ["config/settings.py","config/urls.py","passenger_wsgi.py","portal/urls.py","moj/modern_site.py"]:
  p=root/f
  if not p.is_file():continue
  text=p.read_text(errors="replace")
  hits.append({"file":f,"bytes":len(text),"has_DJANGO_SETTINGS_MODULE":"DJANGO_SETTINGS_MODULE" in text,
               "has_SQLite":"sqlite3" in text,"has_MYSQL":"mysql" in text.lower(),"has_POSTGRES":"postgres" in text.lower(),
               "has_DEBUG":"DEBUG" in text,"contains_gallery":"company-gallery" in text,
               "contains_admin":"admin.site.urls" in text})
 return hits
def compare(live,other):
 a=set(live);b=set(other)
 both=a&b;changed=sorted(x for x in both if live[x]["sha"]!=other[x]["sha"])
 missing=sorted(a-b); added=sorted(b-a)
 def cats(paths):return dict(sorted(collections.Counter(Path(p).suffix.lower() or "[none]" for p in paths).items()))
 def ordered(paths,match):return [p for p in paths if match(p)][:22]
 return {"shared":len(both),"same":len(both)-len(changed),"changed":len(changed),
         "live_only":len(missing),"candidate_only":len(added),
         "changed_by_ext":cats(changed),"live_only_by_ext":cats(missing),"candidate_only_by_ext":cats(added),
         "removed_live_py":ordered(missing,lambda x:x.endswith(".py")),
         "removed_live_html":ordered(missing,lambda x:x.endswith(".html")),
         "removed_live_frontend":ordered(missing,lambda x:x.endswith((".css",".js"))),
         "candidate_extra_py":ordered(added,lambda x:x.endswith(".py")),
         "candidate_extra_html":ordered(added,lambda x:x.endswith(".html")),
         "changed_python_samples":ordered(changed,lambda x:x.endswith(".py")),
         "changed_html_samples":ordered(changed,lambda x:x.endswith(".html")),
         "key_paths":{p:("SAME" if p in live and p in other and live[p]["sha"]==other[p]["sha"] else "MODIFIED" if p in live and p in other else "MISSING_FROM_CANDIDATE" if p in live else "NEW_IN_CANDIDATE" if p in other else "BOTH_ABSENT") for p in KEY_PATHS}}
def db_metadata():
 root=ROOTS["LIVE_ZOMOROD"]
 return {"db_files":[{"name":x.name,"bytes":x.stat().st_size} for x in root.iterdir() if x.is_file() and x.suffix in (".sqlite3",".db")][:15] if root.is_dir() else []}
say("RUN",{"host":socket.gethostname(),"user":os.environ.get("USER",""),"utc":time.strftime("%Y-%m-%d %H:%M:%SZ",time.gmtime()),"write_mode":"NONE","shell_access":"SSH_READ_ONLY"})
ht=H/"public_html"/".htaccess"
if ht.is_file():
 t=ht.read_text(errors="replace")
 say("PASSENGER_LIVE",{"public_html_exists":True,"app_root_match_live":"PassengerAppRoot /home/zomorod2/Saeit" in t,"passenger_directives":[x.strip() for x in t.splitlines() if re.match(r'^\s*Passenger(AppRoot|BaseURI|StartupFile|Enabled)\b',x)][:12]})
else:say("PASSENGER_LIVE",{"public_html_exists":False})
inventories={}
for label,root in ROOTS.items():
 files=manifest(root)
 inventories[label]=files
 counts=collections.Counter(p["ext"] for p in files.values())
 say("ROOT",{"id":label,"exists":root.is_dir(),"path":str(root),"realpath":str(root.resolve()) if root.exists() else "",
           "file_count":len(files),"bounded_sampling":MANIFEST_STAT.get(str(root),{}),"by_ext":dict(counts),"manage_exists":(root/"manage.py").is_file(),
           "migration_inventory":migration_names(root),"model_classes":excerpt_models(root),"urls":routes(root),
           "source_flags":scripts(root),"syntax":syntax(root,files)})
live=inventories["LIVE_ZOMOROD"]
for label,files in inventories.items():
 if label=="LIVE_ZOMOROD" or not files:continue
 say("DIFF",{"vs":label,**compare(live,files)})
say("PROTECTED_LIVE",{"gallery_images":[p.name for p in sorted((ROOTS["LIVE_ZOMOROD"]/"gallery"/"2026"/"10").glob("zomorod-gallery-*.webp"))][:20],
 "gallery_report_module_exists":(ROOTS["LIVE_ZOMOROD"]/"moj"/"gallery_reports_20261014.py").is_file(),
 "gallery_report_template_exists":(ROOTS["LIVE_ZOMOROD"]/"templates"/"modern"/"zomorod_report_20261014.html").is_file(),
 "gallery_db_metadata":db_metadata()})
say("AUDIT_COMPLETE",{"comparison_roots":list(ROOTS),"no_changes_to_host":True})
