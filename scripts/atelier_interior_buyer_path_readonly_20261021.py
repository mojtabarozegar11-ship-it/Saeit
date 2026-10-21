#!/usr/bin/env python3
"""Read-only exact buyer-path view and storefront implementation inspection."""
import os,sys,inspect,re,json
from pathlib import Path
app=Path("/home/zomorod2/Saeit-staging")
if not (app/"manage.py").is_file():raise SystemExit("APP_MISSING")
os.chdir(app);sys.path.insert(0,str(app))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
os.environ["PYTHONDONTWRITEBYTECODE"]="1"
import django;django.setup()
from django.urls import resolve
from core.models import Product
p=Product.objects.get(pk=879)
print("ATELIER_BUY_PATH_PRODUCT="+json.dumps({"active":p.active,"price":str(p.price),"product_type":p.product_type,"metadata_flags":{k:p.metadata.get(k) for k in ["checkout_enabled","payment_live","sales_enabled","quality_approved","catalog_state","digital_delivery"]}}))
for route in ["/store/","/store/product/879/","/store/product/879/checkout/"]:
    match=resolve(route)
    view=match.func
    module=getattr(view,"__module__","")
    qual=getattr(view,"__qualname__","")
    sourcefile=inspect.getsourcefile(view) or ""
    print("ATELIER_ROUTE="+json.dumps({"route":route,"view":module+"."+qual,"file_relative":str(Path(sourcefile).relative_to(app)) if sourcefile.startswith(str(app)) else Path(sourcefile).name}))
    try:
        source=inspect.getsource(view).splitlines()
    except Exception as exc:
        print("ATELIER_SOURCE_UNAVAILABLE="+type(exc).__name__);continue
    selected=[]
    terms=("template","render(","checkout","purchase","cart","metadata","payment","active","store","contact","login","redirect","product")
    for n,line in enumerate(source,1):
        if any(t in line.lower() for t in terms):
            if any(t in line.lower() for t in ("token","secret","password","key=")):continue
            selected.append({"line":n,"text":line.strip()[:180]})
    print("ATELIER_VIEW_KEYLINES="+json.dumps({"route":route,"code_lines":len(source),"matches":selected[:60]}))

from importlib import import_module
for fpath in ["brands/mojplaywin/product.html","brands/mojplaywin/store.html"]:
    candidate=app/"templates"/fpath
    if candidate.is_file():
        lines=candidate.read_text(encoding="utf8",errors="replace").splitlines()
        hits=[{"n":i+1,"text":line[:260]} for i,line in enumerate(lines) if any(term in line.lower() for term in ("contact","checkout","purchase","href","product","store"))]
        print("ATELIER_TEMPLATE="+json.dumps({"path":fpath,"lines":len(lines),"matches":hits[:60]}))
    else:
        print("ATELIER_TEMPLATE_MISSING="+fpath)
for dotted in ["core.brand_views.branded_store_dispatch","mpw_commerce.product_checkout_page.product_checkout_page"]:
    try:
        module,fnname=dotted.rsplit(".",1)
        fn=getattr(import_module(module),fnname)
        code=inspect.getsource(fn).splitlines()
        matches=[{"line":i+1,"text":line.strip()[:230]} for i,line in enumerate(code) if any(word in line.lower() for word in ("checkout","product","render(","template","available","enabled","price","redirect","login","asset","ready","order","address")) and not any(s in line.lower() for s in ("password","token","secret","private_key"))]
        print("ATELIER_EXTRA_VIEW="+json.dumps({"name":dotted,"total_lines":len(code),"matches":matches[:90]}))
    except Exception as ex:
        print("ATELIER_EXTRA_VIEW_ERR="+json.dumps({"name":dotted,"type":type(ex).__name__}))

from config import urls as urlconf
for fn in ["branded_store_dispatch"]:
    try:
        obj=getattr(urlconf,fn)
        code=inspect.getsource(obj).splitlines()
        hits=[{"line":i+1,"text":l.strip()[:220]} for i,l in enumerate(code) if any(t in l.lower() for t in ("render","store","product","template","brand","checkout"))]
        print("ATELIER_STORE_DISPATCH="+json.dumps({"sourcefile":str(Path(inspect.getsourcefile(obj) or "").name),"total_lines":len(code),"matches":hits[:80]}))
    except Exception as e:print("ATELIER_STORE_DISPATCH_ERROR="+type(e).__name__)
from mpw_commerce.product_checkout_page import approved_for_checkout
src=inspect.getsource(approved_for_checkout).splitlines()
print("ATELIER_CHECKOUT_ELIGIBILITY_SOURCE="+json.dumps([l.strip()[:220] for l in src][:90]))
for root in [app/"templates",app/"core"/"templates",app/"mpw_commerce"/"templates"]:
    if root.exists():
        for pattern in ["product.html","product_checkout.html","store.html"]:
            for file in root.rglob(pattern):
                try:
                    rel=str(file.relative_to(app))
                    lines=file.read_text(encoding="utf8",errors="replace").splitlines()
                    hits=[{"n":i+1,"text":line.strip()[:250]} for i,line in enumerate(lines) if any(t in line.lower() for t in ("checkout","purchase","contact","product","href","form","price","sale"))]
                    print("ATELIER_DISCOVERED_TEMPLATE="+json.dumps({"file":rel,"lines":len(lines),"matches":hits[:75]}))
                except Exception as e:print("ATELIER_TEMPLATE_ERR="+type(e).__name__)

module=import_module("mpw_commerce.product_checkout_page")
print("ATELIER_GATE_FLAG_STATES="+json.dumps({"FLAGS":list(getattr(module,"FLAGS",())),"approvals":list(getattr(module,"APPROVAL_FLAGS",())),"gate_result_with_anonymous":bool(approved_for_checkout(type("FakeRequest",(),{"is_secure":lambda self:True,"get_host":lambda self:"mojplaywin.com","user":type("Guest",(),{"is_authenticated":False,"is_active":True})()})(),p))}))
print("ATELIER_EXISTING_KNOWLEDGE_ASSOC="+json.dumps({"article_attached":p.knowledge_article_id is not None,"article_published":bool(getattr(p.knowledge_article,"published",False)) if p.knowledge_article_id else False,"owner_id_present":p.owner_id is not None}))
for fn_name in ["_private_file","approved_for_checkout"]:
    fn=getattr(module,fn_name,None)
    if fn:
        lines=inspect.getsource(fn).splitlines()
        print("ATELIER_COMMERCE_INVARIANT="+json.dumps({"fn":fn_name,"lines":[l.strip()[:220] for l in lines[:115]]}))
import core.cryptopay_checkout as cryptopay_checkout
for dotted in ["mpw_commerce.downloads.download","mpw_commerce.api_checkout.create_order"]:
    try:
        mm,n=dotted.rsplit(".",1); f=getattr(import_module(mm),n)
        lines=inspect.getsource(f).splitlines()
        print("ATELIER_COMMERCE_FUNCTION="+json.dumps({"name":dotted,"lines":len(lines),"match":[l.strip()[:190] for l in lines if any(w in l.lower() for w in ("pdf","zip","file","product","approval","purchase","type","content"))][:50]}))
    except Exception as e:print("ATELIER_COMMERCE_FUNCTION_MISSING="+json.dumps({"fn":dotted,"err":type(e).__name__}))
print("ATELIER_PRODUCT_TYPE_CHOICES="+json.dumps(Product._meta.get_field("product_type").choices))

from django.conf import settings
from mpw_commerce import product_checkout_page as pc_module
suffixes=approved_for_checkout.__globals__["_private_file"].__globals__.get("ACCEPTED_SUFFIXES",())
root=getattr(settings,"MPW_COMMERCE_PRIVATE_ASSET_ROOT",None)
print("ATELIER_COMMERCE_SUFFIX_ROOT="+json.dumps({"suffixes":sorted(str(z) for z in suffixes),"root_configured":isinstance(root,str) and root.startswith("/"),"root_exists":isinstance(root,str) and Path(root).is_dir(),"zip_supported":".zip" in suffixes}))
KnowledgeArticle=Product._meta.get_field("knowledge_article").remote_field.model
print("ATELIER_ARTICLE_MODEL_FIELDS="+json.dumps([f.name for f in KnowledgeArticle._meta.fields]))
print("ATELIER_PREVIOUS_PRODUCT_INVENTORY="+json.dumps([{"id":q.pk,"type":q.product_type,"article":q.knowledge_article_id is not None,"approved":all(q.metadata.get(k) is True for k in pc_module.APPROVAL_FLAGS),"price":str(q.price)} for q in Product.objects.filter(pk__in=[72,225,879])]))

fields=[]
for f in KnowledgeArticle._meta.fields:
    fields.append({"name":f.name,"type":f.get_internal_type(),"null":f.null,"blank":f.blank,"default":str(f.default)[:80],"unique":f.unique})
print("ATELIER_ARTICLE_FIELD_RULES="+json.dumps(fields))
from django.conf import settings
print("ATELIER_LIVE_GATE_FLAGS="+json.dumps({flag:getattr(settings,flag,None) is True for flag in module.FLAGS}))
from mpw_commerce.product_checkout_page import proven_assets
print("ATELIER_LIVE_PROVEN_PAYMENT_ASSETS="+json.dumps({k:v is True for k,v in proven_assets().items() if k in ("ETH","TRX")}))
for path in [app/"core"/"templates"/"brands"/"mojplaywin"/"product.html",app/"core"/"templates"/"mojplaywin"/"store.html"]:
    if path.is_file():
        raw=path.read_text("utf8")
        print("ATELIER_TARGET_TPL_HINT="+json.dumps({"name":path.name,"size":len(raw),"key_positions":{term:raw.find(term) for term in ("{% elif product.pk == 72 or product.pk == 225 %}","mpw-two-books","mpw-book-pay-note","{% endblock %}")},"end_snippet":raw[-650:]}))

import hashlib
production=Path("/home/zomorod2/Saeit")
for rel in ["core/templates/brands/mojplaywin/product.html","core/templates/mojplaywin/store.html","mpw_commerce/product_checkout_page.py"]:
    paths=[app/rel,production/rel]
    print("ATELIER_DEPLOYED_TPL_PARITY="+json.dumps({"rel":rel,"staging":paths[0].is_file(),"production":paths[1].is_file(),"identical":all(t.is_file() for t in paths) and hashlib.sha256(paths[0].read_bytes()).digest()==hashlib.sha256(paths[1].read_bytes()).digest()}))

from django.conf import settings
print("ATELIER_TEMPLATE_RUNTIME="+json.dumps({"debug":settings.DEBUG,"template_backend_count":len(settings.TEMPLATES),"loaders":str(settings.TEMPLATES[0].get("OPTIONS",{}).get("loaders",None))[:280],"app_dirs":settings.TEMPLATES[0].get("APP_DIRS"),"passenger_wsgi":(app/"passenger_wsgi.py").is_file(),"app_tmp_exists":(app/"tmp").is_dir(),"passenger_restart_marker":(app/"tmp"/"restart.txt").is_file(),"app_owner":app.stat().st_uid==(app/"manage.py").stat().st_uid}))
print("ATELIER_READONLY_VIEW_INSPECT=PASS")


# Follow-up: match on-disk Django origins, live route output, and public worker response.
import urllib.request
from hashlib import sha256
from django.template.loader import get_template
from django.test import RequestFactory
for name in ("brands/mojplaywin/product.html", "mojplaywin/store.html"):
    try:
        obj = get_template(name)
        src = obj.template.source
        origin = obj.origin.name
        print("ATELIER_ORIGIN_DIAG=" + json.dumps({
            "name": name, "origin_relative": str(Path(origin).relative_to(app)) if origin.startswith(str(app)) else Path(origin).name,
            "on_disk_sha": sha256(Path(origin).read_bytes()).hexdigest()[:16],
            "compiled_source_sha": sha256(src.encode()).hexdigest()[:16],
            "has_879_marker": ("atelier-original-vector-879" in src or "product.pk == 879" in src),
            "source_matches_disk": src == Path(origin).read_text(encoding="utf8")
        }, sort_keys=True))
    except Exception as ex:
        print("ATELIER_ORIGIN_DIAG_ERROR=" + type(ex).__name__)
import core.mojplaywin_views as mpwv
items = getattr(mpwv,"PRODUCTS",[])
print("ATELIER_INMEMORY_CATALOG="+json.dumps({
    "total":len(items),"atelier":[{"url":str(q.get("url",""))[:160],"action":str(q.get("action_label",""))[:80],"note":str(q.get("availability_note",""))[:160]}
            for q in items if "atelier" in str(q.get("title","")).lower()]},sort_keys=True))
factory = RequestFactory()
req = factory.get("/store/", secure=True, HTTP_HOST="mojplaywin.com")
for label,view,args in (("store",mpwv.store,()),):
    try:
        ans=view(req,*args)
        txt=ans.content.decode("utf8","replace")
        print("ATELIER_INPROCESS_VIEW="+json.dumps({"name":label,"status":ans.status_code,
             "has_product_url":"/store/product/879/" in txt,"has_buy_url":"/store/product/879/checkout/" in txt,
             "has_preview_warning":"preview only" in txt.lower(),
             "has_custom_marker":"atelier-original-vector-879" in txt,
             "html_sha":sha256(txt.encode()).hexdigest()[:16]},sort_keys=True))
    except Exception as ex:
        print("ATELIER_INPROCESS_VIEW_ERROR="+json.dumps({"name":label,"type":type(ex).__name__}))
for route in ("/store/","/store/product/879/"):
    try:
        url="https://mojplaywin.com"+route+"?atelier_owner_diag=20261022"
        request=urllib.request.Request(url,headers={"User-Agent":"Atelier-Owner-ReadOnly-Audit/1.0"})
        with urllib.request.urlopen(request,timeout=20) as resp:
            txt=resp.read(300000).decode("utf8","replace")
            print("ATELIER_ORIGIN_PUBLIC="+json.dumps({"route":route,"status":resp.status,
                "has_product_url":"/store/product/879/" in txt,"has_buy_url":"/store/product/879/checkout/" in txt,
                "has_custom_marker":"atelier-original-vector-879" in txt,
                "cache_control":resp.headers.get("Cache-Control","")[:80],
                "html_sha":sha256(txt.encode()).hexdigest()[:16]},sort_keys=True))
    except Exception as ex:
        print("ATELIER_ORIGIN_PUBLIC_ERROR="+json.dumps({"route":route,"type":type(ex).__name__}))
for root in (app/"core"/"templatetags", app/"core"):
    hits=[]
    try:
        for file in root.rglob("*.py"):
            if len(hits)>=20:break
            if "mpw_managed_offers" in file.read_text(encoding="utf8",errors="replace"):
                hits.append(str(file.relative_to(app)))
        print("ATELIER_MANAGED_OFFERS_SOURCE="+json.dumps({"root":str(root.relative_to(app)),"hits":hits}))
    except Exception as ex:
        print("ATELIER_MANAGED_OFFERS_ERROR="+type(ex).__name__)


# Follow-up: identify public vhost -> actual Passenger root, with no writes or credential reads.
import re
home=Path("/home/zomorod2")
paths=[home/"public_html",home/"mojplaywin.com",home/"domains"/"mojplaywin.com"/"public_html",
       home/"Saeit",home/"Saeit-staging",home/"MojPlayWin",home/"mojplaywin"]
for path in paths:
    print("ATELIER_APP_ROOT_CANDIDATE="+json.dumps({"path":str(path.relative_to(home)),
      "exists":path.exists(),"directory":path.is_dir(),
      "symlink":path.is_symlink(),
      "has_wsgi":(path/"passenger_wsgi.py").is_file(),
      "has_manage":(path/"manage.py").is_file(),
      "has_product_template":(path/"core/templates/brands/mojplaywin/product.html").is_file()},sort_keys=True))
    ht=path/".htaccess"
    if ht.is_file() and not ht.is_symlink():
        print("ATELIER_PUBLIC_HTACCESS="+json.dumps({"path":str(ht.relative_to(home)),
          "directives":[l.strip()[:180] for l in ht.read_text("utf8",errors="replace").splitlines()
          if re.match(r"^\s*(PassengerAppRoot|PassengerPython|PassengerStartupFile|PassengerBaseURI|PassengerEnabled|PassengerAppType|PassengerFriendlyErrorPages|RewriteRule|SetHandler)\b",l,re.I)][:35]},sort_keys=True))
# Ownership-checked process working directories only; no process args/environment displayed.
from collections import Counter
worker_dirs=Counter()
proc=Path("/proc")
if proc.is_dir():
    for item in proc.iterdir():
        if not item.name.isdecimal():continue
        try:
            st=(item/"status").read_text("utf8",errors="replace")
            uidline=next(x for x in st.splitlines() if x.startswith("Uid:"))
            if int(uidline.split()[1])!=os.getuid():continue
            comm=(item/"comm").read_text().strip().lower()
            if not any(q in comm for q in ("python","passenger","lsapi","wsgi","ruby")):continue
            cwd=os.readlink(item/"cwd")
            if cwd.startswith(str(home)):
                worker_dirs[str(Path(cwd).relative_to(home))]+=1
        except (OSError,StopIteration,ValueError):
            continue
print("ATELIER_LIVE_USER_WORKER_CWDS="+json.dumps(dict(worker_dirs.most_common(16))))
# Shallow, pruned discovery of app entrypoints outside the presumed staging root.
entries=[]
ignored={"node_modules",".git","static","media","venv","virtualenv",".cache","assets","backups","logs","tmp","__pycache__","site-packages"}
for root,dirs,files in os.walk(home,topdown=True,followlinks=False):
    rel=Path(root).relative_to(home)
    if len(rel.parts)>=4:
        dirs[:]=[]
        continue
    dirs[:]=[d for d in dirs if d not in ignored and not d.startswith(".")][:85]
    if "passenger_wsgi.py" in files or ("manage.py" in files and rel.parts and rel.parts[0] != "Saeit-staging"):
        entries.append({"directory":str(rel),"wsgi":"passenger_wsgi.py" in files,"manage":"manage.py" in files})
    if len(entries)>=30:break
print("ATELIER_OTHER_APP_ENTRYPOINTS="+json.dumps(entries))
