#!/usr/bin/env python3
"""Protected one-shot personal site hardening, content architecture, UX and SEO.
Only independent Django V17 files; preserves DB, publications, and media.
"""
from __future__ import annotations
import argparse, hashlib, html, json, os, re, stat, shutil, sys, tempfile
from pathlib import Path

APP=Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
MARK="mpw-complete-standard-20261019"
PATHS={
 "base":"templates/personal_site/base.html",
 "home":"templates/personal_site/core/home.html",
 "about":"templates/personal_site/core/about.html",
 "posts":"templates/personal_site/core/posts.html",
 "gallery":"templates/personal_site/core/gallery.html",
 "contact":"templates/personal_site/core/contact.html",
 "privacy":"templates/personal_site/core/privacy.html",
 "views":"core/views.py",
 "admin":"core/admin.py",
}
CSS=r"""
<style id="mpw-complete-standard-20261019">
html{scroll-padding-top:90px;overflow-x:clip}
body{min-width:0;overflow-wrap:break-word}
main img{max-width:100%;height:auto}
main video,main iframe{max-width:100%}
main pre,main table{max-width:100%;overflow-x:auto}
main :focus-visible{outline:3px solid #f5d38e!important;outline-offset:4px}
.mpw-complete-toc{box-sizing:border-box;max-width:1150px;margin:1.5rem auto 2.2rem;padding:clamp(1.1rem,2.8vw,2.3rem);border-radius:20px;border:1px solid rgba(212,174,115,.63);background:linear-gradient(140deg,rgba(40,38,32,.94),rgba(18,19,19,.98));box-shadow:0 18px 55px rgba(0,0,0,.25);color:#f0e4d0}
.mpw-complete-toc h2{font:600 clamp(1.35rem,3vw,1.9rem)/1.25 Georgia,serif;color:#f3d99e;margin:0 0 .6rem}
.mpw-complete-toc p{font:400 1rem/1.7 system-ui,sans-serif;color:#e8dccb}
.mpw-complete-toc-links{display:flex;gap:.6rem;flex-wrap:wrap;margin-top:1rem}
.mpw-complete-toc-links a{display:inline-flex;align-items:center;min-height:44px;border:1px solid #8f764d;border-radius:9px;background:#312b22;color:#f3dfbb!important;text-decoration:none!important;padding:.65rem .9rem;font:600 .9rem/1.35 system-ui,sans-serif}
.mpw-complete-toc-links a:hover{background:#4a3821}
.mpw-complete-disclosure{max-width:1150px;box-sizing:border-box;margin:1.1rem auto;background:#1b1c1a;border:1px solid #8f744c;border-radius:15px;color:#eee3d1;overflow:clip}
.mpw-complete-disclosure>summary{cursor:pointer;display:list-item;list-style:disclosure-closed inside;padding:1.1rem 1.4rem;color:#f4d6a0;font:600 clamp(1rem,2vw,1.3rem)/1.4 system-ui,sans-serif}
.mpw-complete-disclosure[open]>summary{border-bottom:1px solid #66583d;list-style:disclosure-open inside}
.mpw-complete-disclosure>section{margin-top:0!important}
.mpw-complete-privacy{max-width:950px;margin:1.3rem auto;padding:1rem 1.3rem;border:1px solid #74613f;border-radius:12px;background:#1b1b1b;color:#e6dac6}
.mpw-complete-privacy a{color:#f3d08f!important}
.mpw-complete-honeypot{position:absolute!important;left:-10000px!important;width:1px!important;height:1px!important;overflow:hidden!important}
@media(max-width:780px){.mpw-complete-toc,.mpw-complete-disclosure{margin-left:12px;margin-right:12px}.mpw-complete-toc-links{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.mpw-complete-toc-links a{min-width:0;overflow-wrap:anywhere}}
@media(max-width:420px){.mpw-complete-toc-links{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){html:focus-within{scroll-behavior:auto!important}*,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}}
@supports(content-visibility:auto){main section:nth-of-type(n+5){content-visibility:auto;contain-intrinsic-size:auto 480px}}
</style>"""
TOC="""
<nav class="mpw-complete-toc" id="mpw-complete-standard-20261019-toc" aria-label="Browse professional topics">
<h2>Find the information you need</h2>
<p>The biography, résumé and research journal have dedicated pages. Expand a topic below for its full original material.</p>
<div class="mpw-complete-toc-links">
<a href="/mojtaba.roozegar/about/">Biography</a>
<a href="/mojtaba.roozegar/resume/">Academic and professional résumé</a>
<a href="/mojtaba.roozegar/works-activities/">Experience</a>
<a href="/mojtaba.roozegar/blog/">Research and articles</a>
<a href="/mojtaba.roozegar/gallery/">Photos</a>
<a href="/mojtaba.roozegar/contact/">Contact</a>
<a href="/mojtaba.roozegar/privacy/">Privacy</a>
</div></nav>
"""
ARTICLE="""<aside class="mpw-complete-privacy" aria-label="Research reading note"><strong>Research integrity:</strong> Articles distinguish proposals and personal analysis from independently verified outcomes. Refer to each article's evidence and limitations before applying its recommendations.</aside>"""
CONTACT_NOTE="""<aside class="mpw-complete-privacy" aria-label="Contact and privacy guidance">Please describe your project without sending passwords or confidential documents. Submitted contact details are used for replying to your inquiry. <a href="/mojtaba.roozegar/privacy/">Read the privacy notice.</a></aside>"""
POLICY_NOTE="""<section class="mpw-complete-privacy" aria-label="Data handling details"><h2>Contact request handling</h2><p>Use the contact page to request access, correction or deletion of information you submitted. The website owner reviews legitimate requests. A fixed automatic deletion period is not claimed until a corresponding retention process is implemented and tested.</p></section>"""
CANON="""def posts(request):
    page = Paginator(Post.objects.filter(published=True), 6).get_page(request.GET.get('page'))
    canonical = request.build_absolute_uri(request.path)
    if page.number > 1:
        canonical += '?page=' + str(page.number)
    return render(request, 'personal_site/core/posts.html',
                  {'items': page, 'canonical_url': canonical})
"""
FORM_GUARD="""
# Personal-contact-only guard: refuse oversized requests and automated honeypot fills.
_original_personal_contact = contact
def contact(request):
    if request.method == 'POST':
        if request.META.get('CONTENT_LENGTH','').isdigit() and int(request.META['CONTENT_LENGTH']) > 32768:
            from django.http import HttpResponse
            return HttpResponse(status=413)
        if request.POST.get('contact_website', '').strip():
            from django.http import HttpResponse
            return HttpResponse(status=400)
    return _original_personal_contact(request)
"""
ADMIN_NOTE="""
# Expose existing personal-site records in the authenticated Django admin only.
from django.apps import apps as _mpw_apps
from django.contrib import admin as _mpw_admin
for _mpw_model in _mpw_apps.get_app_config('core').get_models():
    if _mpw_model.__name__ in ('ContactMessage', 'Post', 'GalleryItem', 'SiteProfile') and not _mpw_admin.site.is_registered(_mpw_model):
        _mpw_admin.site.register(_mpw_model)
"""
def sha(data):return hashlib.sha256(data).hexdigest()
def files(app):
    if app!=APP or app.is_symlink() or not (app/"manage.py").is_file():
        raise RuntimeError("Not the independent personal V17 app")
    d={}
    for name,rel in PATHS.items():
        p=app/rel
        if not p.is_file() or p.is_symlink() or p.resolve()!=p:
            raise RuntimeError("Missing or unsafe site-owned file "+rel)
        d[name]=p
    return d

def lazy(source,skip=1):
    counter=0
    def edit(m):
        nonlocal counter
        v=m.group(0);counter+=1
        if counter<=skip:return v
        if not re.search(r'\bloading\s*=',v,re.I):v=v[:-1]+' loading="lazy">'
        if not re.search(r'\bdecoding\s*=',v,re.I):v=v[:-1]+' decoding="async">'
        return v
    return re.sub(r'<img\b[^>]*>',edit,source,flags=re.I)

def section_wrap(source,marker,title):
    where=source.find(marker)
    if where<0:return source,False
    start=source.rfind('<section',0,where)
    if start<0 or where-start>12000:return source,False
    depth=0;end=None
    for hit in re.finditer(r'</?section\b[^>]*>',source[start:],re.I):
        depth += (-1 if hit.group(0).lower().startswith('</') else 1)
        if depth==0:
            end=start+hit.end()
            break
    if not end or where>=end or end-start>180000:return source,False
    # The original HTML remains server-rendered and indexable; native details
    # make large topic archives easier for screenreader and keyboard users.
    beginning='<details class="mpw-complete-disclosure"><summary>'+html.escape(title)+'</summary>\n'
    ending='\n</details>'
    return source[:start]+beginning+source[start:end]+ending+source[end:],True

def patch(key,raw):
    if MARK in raw:raise RuntimeError("Already installed: "+key)
    if key=="base":
        if raw.count("</head>")!=1 or "mpw-standard-20261019" not in raw:raise RuntimeError("Unexpected base")
        return raw.replace("</head>",CSS+"\n</head>",1)
    if key=="home":
        token='{% block content %}'
        if raw.count(token)!=1 or "mpw-standard-20261019-navigation" not in raw:
            raise RuntimeError("Expected last protected personal release missing")
        raw=raw.replace(token,token+"\n"+TOC,1)
        groups=[
          ("mpw-fifty-editorials-20261015","Professional perspectives and original essays"),
          ("mpw-academic-profile-20261016","Academic background and professional reference"),
          ("mpw-vancouver-enterprise-20-index-20261016","Enterprise website research collection I"),
          ("mpw-vancouver-enterprise-20-series2-index-20261016","Enterprise website research collection II"),
        ]
        total=0
        for marker,title in groups:
            raw,ok=section_wrap(raw,marker,title);total+=bool(ok)
        print("HOME_LONG_SECTIONS_GROUPED="+str(total),flush=True)
        return lazy(raw,2)
    if key=="about":
        return lazy(raw,1)
    if key=="posts":
        if "mpw-standard-20261019" in raw:
            # marker belongs only in shared base, not expected here
            raise RuntimeError("Unexpected journal marker conflict")
        if "{% block content %}" not in raw:raise RuntimeError("Missing journal content")
        return raw.replace("{% block content %}","{% block content %}\n"+ARTICLE,1)
    if key=="gallery":
        return lazy(raw,0)
    if key=="contact":
        n=raw.count("</form>")
        if n!=1:raise RuntimeError("Unexpected contact form count "+str(n))
        guard='<div class="mpw-complete-honeypot" aria-hidden="true"><label for="mpw-contact-website">Leave this field empty</label><input id="mpw-contact-website" type="text" name="contact_website" tabindex="-1" autocomplete="off"></div>'
        raw=raw.replace("</form>",guard+"</form>",1)
        if "{% block content %}" not in raw:raise RuntimeError("Missing contact block")
        return raw.replace("{% block content %}","{% block content %}\n"+CONTACT_NOTE,1)
    if key=="privacy":
        if "{% block content %}" not in raw:raise RuntimeError("Missing privacy block")
        return raw.replace("{% block content %}","{% block content %}\n"+POLICY_NOTE,1)
    if key=="views":
        expr="def posts(request): return render(request,'personal_site/core/posts.html',{'items':Paginator(Post.objects.filter(published=True),6).get_page(request.GET.get('page'))})"
        if raw.count(expr)!=1 or raw.count("def contact(request)")!=1:
            raise RuntimeError("Unexpected Django posts/contact source; refusing unsafe edit")
        return raw.replace(expr,CANON,1)+"\n"+FORM_GUARD
    if key=="admin":
        if "_mpw_apps.get_app_config('core')" in raw:raise RuntimeError("Admin already extended")
        return raw+"\n"+ADMIN_NOTE
    raise RuntimeError("Not allowed: "+key)

def setup_django(app):
    sys.path.insert(0,str(app))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    import django
    django.setup()

def planned(app):
    ps=files(app)
    before={k:p.read_text(encoding="utf-8") for k,p in ps.items()}
    after={k:patch(k,text) for k,text in before.items()}
    setup_django(app)
    from django.template import engines
    engine=engines["django"].engine
    for k,body in after.items():
        if k not in ("views","admin"):engine.from_string(body)
        else:compile(body,k,"exec")
        print("ONE_STAGE_PREFLIGHT_OK="+k,flush=True)
    if after["views"].count("def posts(request):")!=1:
        raise RuntimeError("Duplicated posts handler")
    return before,after

def atomic(path,data):
    fd,tmp=tempfile.mkstemp(prefix=".mpw-complete-",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as f:
            os.fchmod(f.fileno(),stat.S_IMODE(path.stat().st_mode))
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.lexists(tmp):os.unlink(tmp)

def read_manifest(app,backup):
    if backup.is_symlink() or not backup.is_dir():raise RuntimeError("Unsafe backup")
    m=backup/"manifest.json"
    if m.is_symlink() or not m.is_file():raise RuntimeError("No manifest")
    data=json.loads(m.read_text("utf-8"))
    if data.get("app")!=str(app) or set(data.get("files",{}))!=set(PATHS):raise RuntimeError("Manifest scope mismatch")
    return data

def install(app,backup):
    before,after=planned(app)
    if backup.exists() or backup.is_symlink():raise RuntimeError("Backup already exists")
    backup.mkdir(parents=True,mode=0o700)
    ps=files(app);meta={"app":str(app),"files":{}}
    for k,p in ps.items():
        d=before[k].encode("utf8");b=backup/(k+".original")
        with b.open("xb") as f:
            os.fchmod(f.fileno(),0o600);f.write(d);f.flush();os.fsync(f.fileno())
        if b.read_bytes()!=d:raise RuntimeError("Backup corrupted")
        meta["files"][k]={"before":sha(d),"after":sha(after[k].encode("utf8"))}
    with (backup/"manifest.json").open("x") as f:
        os.fchmod(f.fileno(),0o600);json.dump(meta,f,indent=2);f.flush();os.fsync(f.fileno())
    try:
        for k,p in ps.items():
            if sha(p.read_bytes())!=meta["files"][k]["before"]:
                raise RuntimeError("Concurrent mutation: "+k)
            atomic(p,after[k].encode("utf8"))
        verify(app,backup)
    except BaseException:
        rollback(app,backup)
        raise
    print("ONE_STAGE_STANDARDS_INSTALLED=YES",flush=True)
    print("ONE_STAGE_BACKUP="+str(backup),flush=True)

def verify(app,backup):
    meta=read_manifest(app,backup)
    for k,p in files(app).items():
        if sha(p.read_bytes())!=meta["files"][k]["after"]:
            raise RuntimeError("Live file checksum mismatch "+k)
        if sha((backup/(k+".original")).read_bytes())!=meta["files"][k]["before"]:
            raise RuntimeError("Backup integrity failed "+k)
    print("ONE_STAGE_ALL_NINE_FILES_VERIFIED=YES",flush=True)

def rollback(app,backup):
    meta=read_manifest(app,backup)
    ps=files(app)
    for k,p in ps.items():
        orig=(backup/(k+".original")).read_bytes()
        if sha(orig)!=meta["files"][k]["before"]:raise RuntimeError("Invalid backup "+k)
        if sha(p.read_bytes()) not in (meta["files"][k]["before"],meta["files"][k]["after"]):
            raise RuntimeError("Concurrent edit; refuse rollback "+k)
    for k,p in ps.items():
        if sha(p.read_bytes())==meta["files"][k]["after"]:
            atomic(p,(backup/(k+".original")).read_bytes())
    print("ONE_STAGE_ROLLBACK_SUCCESS=YES",flush=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=("check","install","verify","rollback"))
    parser.add_argument("--app",type=Path,default=APP)
    parser.add_argument("--backup",type=Path)
    a=parser.parse_args()
    if a.action=="check":planned(a.app);print("ONE_STAGE_SAFE_PREFLIGHT=YES")
    else:
        if not a.backup:parser.error("--backup required")
        {"install":install,"verify":verify,"rollback":rollback}[a.action](a.app,a.backup)
if __name__=="__main__":main()
