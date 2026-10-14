#!/usr/bin/env python3
# Static-only fine-grained compatibility audit. No Django startup, no database access.
import ast,hashlib,json,re
from pathlib import Path
H=Path("/home/zomorod2")
ROOTS={"LIVE":H/"Saeit","V91_MAIN":H/"saeit_v91"/"zomorodmelal","V91_STAGED":H/"saeit_v91_runtime_stage_20261012"/"zomorodmelal","V91_STAFF":H/"Saeit-staging"/"v91_personnel_isolated"/"staff-22790e223ec4cfc1"/"zomorodmelal"}
PROTECTED=[
"config/urls.py","config/settings.py","config/wsgi.py","passenger_wsgi.py","portal/models.py","portal/admin.py","portal/urls.py","portal/views.py",
"command_center/urls.py","command_center/views.py","moj/modern_site.py","moj/localized_site.py","moj/site_builder.py","moj/json_content_admin.py",
"moj/gallery_reports_20261014.py","moj/templates/site_builder/dashboard.html",
"templates/modern/pages/company-gallery.html","templates/modern/partials/zomorod_gallery_20261014.html","templates/modern/zomorod_report_20261014.html",
"templates/portal/base.html","templates/admin/index.html",
"static/site/modern.css","static/site/modern.js","static/site/home-luxury.css","static/site/company-gallery.css",
"static/site/company/company-hero.webp","gallery/2026/10/zomorod-gallery-01-digital-management.webp",
]
def say(kind,row):print("COMPAT_JSON "+json.dumps({"kind":kind,"info":row},ensure_ascii=False,sort_keys=True))
def read(root,p):
 try:
  f=root/p
  if f.is_file() and f.stat().st_size<3_000_000:return f.read_text(encoding="utf-8",errors="replace")
 except Exception:pass
 return ""
def hashes(root,names):
 out={}
 for name in names:
  p=root/name
  if p.is_file() and not p.is_symlink():
   try:out[name]=hashlib.sha256(p.read_bytes()).hexdigest()[:16]
   except Exception:pass
 return out
def setting_fields(root):
 s=read(root,"config/settings.py")
 if not s:return {"present":False}
 apps=[]
 try:
  tree=ast.parse(s)
  for n in ast.walk(tree):
   if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="INSTALLED_APPS" for t in n.targets):
    try:apps=ast.literal_eval(n.value)
    except: apps=[]
 except:pass
 checks=["DEBUG","ALLOWED_HOSTS","CSRF_TRUSTED_ORIGINS","INSTALLED_APPS","MIDDLEWARE","MEDIA_ROOT","MEDIA_URL","STATIC_URL","STATIC_ROOT","DATABASES","ROOT_URLCONF","TEMPLATES","SESSION_COOKIE_SECURE","CSRF_COOKIE_SECURE","SECURE_SSL_REDIRECT"]
 return {"present":True,"bytes":len(s),"database_backends_referenced":sorted(set(re.findall(r'django\.db\.backends\.[a-z0-9_]+',s,re.I))),
         "env_database_names":sorted(set(re.findall(r'["\x27](?:DATABASE_URL|DB_ENGINE|DB_HOST|MYSQL_HOST|MYSQL_DATABASE|MYSQL_USER|POSTGRES_DB|PGHOST|DJANGO_DATABASE_URL)["\x27]',s))),
         "debug_literal":re.findall(r'\bDEBUG\s*=\s*(True|False)\b',s)[:3],
         "config_fields_present":{k:bool(re.search(r'\b'+k+r'\s*=',s)) for k in checks},
         "apps":apps[:40] if isinstance(apps,(tuple,list)) else []}
def route_details(root):
 s=read(root,"config/urls.py")
 return {"source_bytes":len(s),"has_admin_root":bool(re.search(r'path\s*\(\s*["\x27]admin/',s)),"has_admin_staff":bool(re.search(r'path\s*\(\s*["\x27]staff/',s)),
         "has_dynamic_modern_pages":"moj.modern_site" in s,
         "has_portal_url_include":"portal.urls" in s,
         "has_public_gallery_report":"company-gallery/report/" in s,
         "has_seo_routes":"sitemap.xml" in s or "robots.txt" in s,
         "has_live_command_center":"staff/command-center/" in s,
         "has_site_builder":"site-builder/" in s,
         "direct_media_static_helper":"static(settings.MEDIA_URL" in s,
         "has_auth_hook":"admin.site.urls" in s}
def section(root):
 items={}
 for key in ["original logo","live gallery six articles","public frontend","django admin","live page builder","workbench v91","staff command center","marketing and seo","payments"]:
  names={
   "original logo":["static/site/company/company-logo.png","static/site/company/company-hero.webp"],
   "live gallery six articles":["moj/gallery_reports_20261014.py","templates/modern/zomorod_report_20261014.html","templates/modern/partials/zomorod_gallery_20261014.html"],
   "public frontend":["moj/modern_site.py","templates/modern/pages/company-gallery.html","static/site/modern.css"],
   "django admin":["portal/admin.py","config/urls.py"],
   "live page builder":["moj/site_builder.py","moj/templates/site_builder/dashboard.html"],
   "workbench v91":["workbench_v91/urls.py","workbench_v91/views.py"],
   "staff command center":["command_center/urls.py","command_center/views.py"],
   "marketing and seo":["moj/localized_site.py","moj/seo.py","static/robots.txt"],
   "payments":["portal/bankshahr_services.py","portal/payment_integrity.py"],
  }[key]
  items[key]={p:(root/p).is_file() for p in names}
 return items
def migration_fingerprints(root):
 p=root/"portal"/"migrations"
 if not p.is_dir():return {}
 return {f.name:hashlib.sha256(f.read_bytes()).hexdigest()[:12] for f in p.glob("0*.py") if f.is_file()}
migbase=migration_fingerprints(ROOTS["LIVE"])
for name,root in ROOTS.items():
 say("RUNTIME_DETAIL",{"root":name,"settings":setting_fields(root),"routing":route_details(root),"feature_files":section(root),"fingerprints":hashes(root,PROTECTED),
    "portal_migrations_count":len(migration_fingerprints(root)),
    "portal_migrations_equal_to_live":migration_fingerprints(root)==migbase})
say("TARGETED_COMPAT_AUDIT_COMPLETE",{"no_writes":True,"no_django_import":True,"no_db_connection":True})
