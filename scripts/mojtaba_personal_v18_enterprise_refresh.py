#!/usr/bin/env python3
"""Additive, reversible dark-gold, SEO and enterprise enquiry upgrade for personal V17 only.

No database writes; never deploys to MojPlayWin root, Zomorod Melal or the VPS factory.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import os
import shutil
import stat
from pathlib import Path

APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
PAGES = {
    "base": "templates/personal_site/base.html",
    "home": "templates/personal_site/core/home.html",
    "posts": "templates/personal_site/core/posts.html",
    "resume": "templates/personal_site/core/resume.html",
    "projects": "templates/personal_site/core/projects.html",
    "contact": "templates/personal_site/core/contact.html",
}
MARK = "mpw-enterprise-v18-20261016"
PRESERVE = (
    "mpw-fifty-editorials-20261015",
    "mpw-academic-profile-20261016",
    "mpw-vancouver-enterprise-20-index-20261016",
    "mpw-vancouver-enterprise-20-series2-index-20261016",
    "mpw-mojtaba-twenty-image-essays-20261016",
    "mpw-enterprise-collaboration-brief-20261016",
    "mpw-five-smart-web-portraits-20261016",
)

SEO = {
    "about": ("About Mojtaba Roozegar | Research, Leadership & Technology",
              "Read Mojtaba Roozegar's biography, academic background, business leadership and approach to intelligent digital projects."),
    "resume": ("Professional Resume | Mojtaba Roozegar — Research & Enterprise",
               "Explore Mojtaba Roozegar's professional profile, education in agricultural economics and cross-sector technology expertise."),
    "projects": ("Intelligent Website Projects & Collaboration | Mojtaba Roozegar",
                 "Discuss enterprise websites, secure Django applications, research-led UX, analytics and practical AI pilots with Mojtaba Roozegar."),
    "activities": ("Work & Research Activities | Mojtaba Roozegar",
                   "Explore agricultural economics, enterprise systems, scientific communication and applied technology research."),
    "posts": ("Research Journal & Intelligent Web Engineering | Mojtaba Roozegar",
              "Read specialist articles about enterprise websites, Django, AI, data, security, agricultural economics and business research."),
    "gallery": ("Professional Photo Gallery | Mojtaba Roozegar",
                "Explore distinct editorial portraits and professional technology illustrations associated with Mojtaba Roozegar's personal work."),
    "contact": ("Enterprise Website Collaboration Enquiries | Mojtaba Roozegar",
                "Start a scoped discussion about secure, intelligent websites, technical pilots and professional collaboration in Vancouver or remotely."),
    "memories": ("Personal Memories & Reflections | Mojtaba Roozegar",
                 "Personal memories and experiences from Mojtaba Roozegar, distinct from his professional research journal."),
    "stories": ("Original Stories & Fiction | Mojtaba Roozegar",
                "Read original fictional writing and creative storytelling by Mojtaba Roozegar."),
    "privacy": ("Privacy & Contact Information | Mojtaba Roozegar",
                "Privacy and contact information for visitors to Mojtaba Roozegar's independent personal site."),
}

CSS = r"""
<style id="mpw-enterprise-v18-20261016" media="all">
:root{color-scheme:dark;--mpw-ink:#101111;--mpw-panel:#1a1b1a;--mpw-edge:#69583c;--mpw-gold:#d9b978;--mpw-ivory:#f1e8d8}
body{background:#101111!important;color:var(--mpw-ivory)}
main{background:radial-gradient(ellipse at 88% 0%,rgba(133,103,55,.12),transparent 48%),#101111;color:var(--mpw-ivory)}
.site-header{background:rgba(15,16,16,.97)!important;border-bottom:1px solid #5b4a31!important;backdrop-filter:blur(18px)}
.site-nav a,.site-header .brand-copy strong,.site-header .brand-copy small{color:#f1e5ce!important}
.site-nav a:hover,.site-nav a:focus-visible,.site-nav .is-active{color:#f4c877!important}
.site-header .nav-toggle{border-color:#a78c58!important}
.site-header .nav-toggle span{background-color:#e7c488!important}
.site-footer{background:#121210!important;color:#eae1d3!important;border-top:1px solid #6b5639}
.site-footer a,.site-footer p,.site-footer h2,.site-footer small{color:#e9dfcb!important}
.site-footer em,.brand-monogram span,.footer-brand span{color:var(--mpw-gold)!important}
body .mpw-inner{color:#e9e0cf!important}
body .mpw-inner h2,body .mpw-inner h3,body .mpw-inner summary{color:#f1d8a8!important}
body .mpw-inner p,body .mpw-inner .mpw-intro{color:#e0d6c8!important}
body .mpw-inner .mpw-card,body .mpw-inner .mpw-essay,body .mpw-inner .mpw-journey{background:#1b1b1a!important;border-color:#625138!important;box-shadow:0 14px 36px rgba(0,0,0,.25)!important}
body .mpw-inner .mpw-card .mpw-copy,body .mpw-inner .mpw-journey{color:#ede3cf!important}
body .mpw-inner .mpw-note{color:#cdbd9e!important}
body .mpw-inner .mpw-kicker{color:#e5c27b!important}
body .mpw-inner a,main a:focus-visible{outline-offset:3px}
body .mpw-inner a{color:#e7bf7d!important}
.mpw-enterprise-v18{box-sizing:border-box;max-width:1200px;margin:40px auto;padding:clamp(22px,3.6vw,45px);border:1px solid #97784b;border-radius:17px;background:linear-gradient(140deg,#1b1c1a,#141412);color:#eee3d0;box-shadow:0 22px 60px rgba(0,0,0,.28)}
.mpw-enterprise-v18 *{box-sizing:border-box}
.mpw-enterprise-v18 .mpw-eyebrow{font:700 12px/1.5 system-ui,sans-serif;letter-spacing:.16em;text-transform:uppercase;color:#e6bd76}
.mpw-enterprise-v18 h2{font:600 clamp(27px,3.8vw,43px)/1.21 Georgia,serif;color:#f1d5a0;margin:10px 0 15px}
.mpw-enterprise-v18 p,.mpw-enterprise-v18 li{color:#e9e0d2;font:15px/1.85 system-ui,sans-serif}
.mpw-enterprise-v18 .mpw-tracks{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:15px;margin:24px 0}
.mpw-enterprise-v18 .mpw-track{background:#24231f;border:1px solid #65523b;border-radius:12px;padding:22px}
.mpw-enterprise-v18 h3{font:600 19px/1.35 Georgia,serif;color:#f4d394;margin:0 0 8px}
.mpw-enterprise-v18 a.mpw-cta{display:inline-flex;align-items:center;background:#d6b477;color:#181713!important;padding:13px 19px;border-radius:9px;font:700 15px/1.4 system-ui,sans-serif;text-decoration:none}
.mpw-enterprise-v18 a.mpw-cta:focus-visible{outline:3px solid white}
.mpw-enterprise-v18 .mpw-disclaimer{font-size:13px;color:#c9bba6}
@media(max-width:760px){.mpw-enterprise-v18{margin:22px 12px;padding:22px}.mpw-enterprise-v18 .mpw-tracks{grid-template-columns:1fr}.site-header .nav-shell{min-width:0}}
@media(prefers-reduced-motion:reduce){.mpw-enterprise-v18 *{scroll-behavior:auto!important;transition:none!important}}
</style>"""

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def seo_fallback(kind: str) -> str:
    chunks = []
    for ix, (route, values) in enumerate(SEO.items()):
        label = values[0] if kind == "title" else values[1]
        chunks.append(("{% if" if ix == 0 else "{% elif") +
                      " request.resolver_match.url_name == '" + route + "' %}" +
                      label)
    if kind == "title":
        chunks.append("{% elif request.resolver_match.url_name == 'post_detail' %}{{ item.title }} | Mojtaba Roozegar Journal")
        chunks.append("{% elif request.resolver_match.url_name == 'project_detail' %}{{ item.title }} | Mojtaba Roozegar Projects")
        fallback = "Mojtaba Roozegar — Personal Website"
    else:
        chunks.append("{% elif request.resolver_match.url_name == 'post_detail' %}Research article by Mojtaba Roozegar: {{ item.title }}. Original analysis and applied perspectives.")
        chunks.append("{% elif request.resolver_match.url_name == 'project_detail' %}Professional project overview by Mojtaba Roozegar: {{ item.title }}.")
        fallback = "Independent professional profile, original research journal and intelligent website collaborations."
    chunks.append("{% else %}" + fallback + "{% endif %}")
    return "".join(chunks)

def replace_once(source: str, before: str, after: str) -> str:
    if source.count(before) != 1:
        raise ValueError("Expected original base pattern absent or repeated: " + before[:48])
    return source.replace(before, after, 1)

def enterprise_block(page: str) -> str:
    content = {
      "home": ("ENTERPRISE DIGITAL COLLABORATION", "Intelligent websites built around business evidence.",
               "A practical proposal for larger organizations: combine accessible interfaces, dependable Django engineering, responsible AI integration, security and measurable operational results."),
      "posts": ("FROM RESEARCH TO DELIVERY", "Turn an expert article into a scoped technical pilot.",
                "These journal studies explain decisions, constraints and verification. A professional pilot converts one validated requirement into a testable deployment without pretending a concept is already a client success."),
      "resume": ("ENTERPRISE CAPABILITIES", "Research, business context and disciplined engineering.",
                 "My academic background in production economics informs requirements, measurements and resource allocation. Website proposals focus on delivery evidence, technical security and honest acceptance criteria, not unsupported partnership claims."),
      "projects": ("VANCOUVER & REMOTE COLLABORATION", "A rigorous first step for an enterprise website.",
                   "For teams exploring accessible B2B portals, knowledge platforms, data dashboards or carefully controlled AI assistants, I propose discovery, a limited pilot and documented handover."),
      "contact": ("SEND A USEFUL PROJECT BRIEF", "Start with the outcome, not the technology.",
                  "A helpful inquiry describes your organization, the main business problem, intended users, desired deadline and the best way to follow up. Please do not include passwords, financial records or confidential customer data."),
    }
    eyebrow, title, intro = content[page]
    tracks = (
      ("01 / DISCOVERY", "Problem & requirements", "Stakeholder goals, accessibility, existing system interfaces, realistic scope and acceptance tests."),
      ("02 / BUILD", "Secure technical pilot", "Django architecture, performance budgets, traceable data flows, human-reviewed AI and QA."),
      ("03 / HANDOVER", "Measured delivery", "Usable documentation, source ownership, monitoring, rollback readiness and an explicit maintenance plan."),
    )
    pieces = [f'<section id="{MARK}-{page}" class="mpw-enterprise-v18" aria-label="Professional intelligent website collaboration">',
              f'<span class="mpw-eyebrow">{eyebrow}</span><h2>{title}</h2><p>{intro}</p>',
              '<div class="mpw-tracks">']
    for number, name, detail in tracks:
        pieces.append(f'<article class="mpw-track"><span class="mpw-eyebrow">{number}</span><h3>{name}</h3><p>{detail}</p></article>')
    pieces.extend(['</div>', '<a class="mpw-cta" href="/mojtaba.roozegar/contact/">Discuss a scoped website project →</a>',
                   '<p class="mpw-disclaimer">Professional collaboration is subject to agreed scope, verified capabilities, contractual terms and applicable legal requirements. No existing client partnership is implied.</p></section>'])
    return "\n".join(pieces)

def safe_paths(app: Path) -> dict[str, Path]:
    if app != APP or app.is_symlink() or not (app / "manage.py").is_file():
        raise ValueError("Only independent personal V17 app is permitted")
    out = {}
    for key, rel in PAGES.items():
        p = app / rel
        if p.is_symlink() or not p.is_file() or p.resolve() != p:
            raise ValueError("Missing unsafe template: " + rel)
        out[key] = p
    return out

def patch(key: str, source: str) -> str:
    if MARK in source:
        raise ValueError("Upgrade already installed: refuse duplicate")
    if key == "base":
        result = source
        result = replace_once(result, '<meta name="theme-color" content="#101c2b">',
                              '<meta name="theme-color" content="#101111">')
        result = replace_once(result, '<meta name="color-scheme" content="light">',
                              '<meta name="color-scheme" content="dark">')
        result = replace_once(result, '{% block title %}Mojtaba Roozegar — Personal Website{% endblock %}',
                              '{% block title %}' + seo_fallback("title") + '{% endblock %}')
        result = replace_once(result, '{% block description %}The personal website of Mojtaba Roozegar: work, journeys, memories, fiction and thoughtful writing.{% endblock %}',
                              '{% block description %}' + seo_fallback("description") + '{% endblock %}')
        result = replace_once(result, '{% block og_title %}Mojtaba Roozegar — Personal Website{% endblock %}',
                              '{% block og_title %}' + seo_fallback("title") + '{% endblock %}')
        result = replace_once(result, '{% block og_description %}An independent personal collection of work, ideas, memories and original stories.{% endblock %}',
                              '{% block og_description %}' + seo_fallback("description") + '{% endblock %}')
        result = replace_once(result, "</head>", CSS + "\n</head>")
        return result
    if source.count("{% block content %}") != 1 or source.count("{% endblock %}") != 1:
        raise ValueError("Unrecognized personal page template")
    if key in ("home","posts"):
        for marker in PRESERVE:
            if source.count(marker) != 1:
                raise ValueError("Protected section absent or duplicated: " + marker)
    if key == "home" and source.count("mpw-primary-personal-profile-20261016") != 1:
        raise ValueError("Owner-selected main profile image marker missing")
    insertion = enterprise_block(key)
    return source.replace("{% endblock %}", insertion + "\n{% endblock %}", 1)

def db_fingerprint(app: Path) -> tuple[str, int, list]:
    import django
    from django.conf import settings
    from django.core.management import call_command
    from core.models import Post
    posts = list(Post.objects.order_by("pk").values())
    public = sum(1 for x in posts if x.get("published"))
    if public < 93:
        raise ValueError("Fewer than 93 published articles; abort")
    blob = json.dumps(posts, sort_keys=True, default=str, ensure_ascii=False).encode()
    return digest(blob), public, posts

def media_inventory(app: Path) -> dict[str, tuple[int, str]]:
    roots = [app / "static" / "personal_site", app / "media", app / "staticfiles" / "personal_site"]
    result = {}
    for root in roots:
        if not root.is_dir() or root.is_symlink(): continue
        for p in root.rglob("*"):
            if p.is_symlink(): raise ValueError("Protected media symlink encountered")
            if p.is_file() and p.suffix.lower() in (".jpg",".jpeg",".png",".webp",".svg",".avif"):
                result[str(p.relative_to(app))] = (p.stat().st_size, digest(p.read_bytes()))
    return result

def django_preflight(app: Path, patched: dict[str,str]) -> None:
    from django.template import engines
    from django.test import RequestFactory
    for name, rendered in patched.items():
        engines["django"].engine.from_string(rendered)
        print("DJANGO_TEMPLATE_PARSES="+name,flush=True)
    if len(patched) != 6: raise ValueError("Wrong scope")

def install(app: Path, backup: Path) -> None:
    import django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
    django.setup()
    paths = safe_paths(app)
    if backup.is_symlink() or backup.exists(): raise ValueError("Backup already exists")
    initial = {name: path.read_text(encoding="utf-8") for name,path in paths.items()}
    new = {name: patch(name, source) for name,source in initial.items()}
    django_preflight(app, new)
    d_before, published, posts = db_fingerprint(app)
    assets_before = media_inventory(app)
    if len(assets_before) < 5: raise ValueError("Protected photographic inventory unusually small")
    backup.mkdir(parents=True, mode=0o700)
    (backup / "templates").mkdir(mode=0o700)
    (backup / "posts.json").write_text(json.dumps(posts,ensure_ascii=False,default=str,indent=1),encoding="utf-8")
    (backup / "posts.json").chmod(0o600)
    manifest = {"before":{}, "after":{}, "database_sha256":d_before,
                "published_posts":published,"assets_sha256":digest(json.dumps(assets_before,sort_keys=True).encode()),
                "assets_count":len(assets_before)}
    for name, path in paths.items():
        saved = backup / "templates" / (name+".html")
        shutil.copy2(path, saved)
        if saved.read_bytes() != path.read_bytes(): raise ValueError("Backup verification failed")
        manifest["before"][name] = digest(initial[name].encode())
        manifest["after"][name] = digest(new[name].encode())
    (backup / "manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    (backup / "manifest.json").chmod(0o600)
    print("PERSONAL_BACKUP_VERIFIED=yes",flush=True)
    print("PROTECTED_ARTICLES="+str(published),flush=True)
    print("PROTECTED_MEDIA_ASSETS="+str(len(assets_before)),flush=True)
    changed=[]
    try:
        for name, path in paths.items():
            if digest(path.read_bytes()) != manifest["before"][name]:
                raise ValueError("Concurrent template edit detected")
            tmp = path.with_name(path.name+".v18-stage")
            if tmp.exists() or tmp.is_symlink(): raise ValueError("Unsafe staging collision")
            tmp.write_text(new[name],encoding="utf-8")
            os.chmod(tmp,path.stat().st_mode & 0o777)
            if digest(tmp.read_bytes()) != manifest["after"][name]: raise ValueError("Staging checksum failed")
            os.replace(tmp,path)
            changed.append(name)
        if db_fingerprint(app)[:2] != (d_before,published): raise ValueError("Database changed")
        assets_after = media_inventory(app)
        if assets_before != assets_after: raise ValueError("A protected media asset changed")
        print("PERSONAL_CONTENT_AND_MEDIA_PRESERVED=yes",flush=True)
    except BaseException:
        for name in changed:
            path=paths[name]
            if digest(path.read_bytes()) == manifest["after"][name]:
                shutil.copy2(backup / "templates" / (name+".html"),path)
        raise
    print("PERSONAL_UPGRADE_INSTALLED=yes",flush=True)
    print("PERSONAL_BACKUP_PATH="+str(backup),flush=True)

def rollback(app: Path, backup: Path) -> None:
    paths=safe_paths(app)
    if backup.is_symlink() or not (backup/"manifest.json").is_file():
        raise ValueError("Verified backup required")
    m=json.loads((backup/"manifest.json").read_text(encoding="utf-8"))
    for name,path in paths.items():
        saved=backup/"templates"/(name+".html")
        if digest(saved.read_bytes())!=m["before"][name]:
            raise ValueError("Corrupt backup")
        if digest(path.read_bytes()) not in (m["before"][name],m["after"][name]):
            raise ValueError("Concurrent edit; refuse overwrite")
    for name,path in paths.items():
        tmp=path.with_name(path.name+".v18-rollback")
        if tmp.exists(): raise ValueError("Rollback conflict")
        shutil.copy2(backup/"templates"/(name+".html"),tmp)
        os.replace(tmp,path)
    print("PERSONAL_ROLLBACK_VERIFIED=yes",flush=True)

def verify(app: Path, backup: Path) -> None:
    import django
    os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings"); django.setup()
    m=json.loads((backup/"manifest.json").read_text(encoding="utf-8"))
    paths=safe_paths(app)
    for name,path in paths.items():
        if digest(path.read_bytes())!=m["after"][name]:
            raise ValueError("Live template hash mismatch: "+name)
    dh,published,_=db_fingerprint(app)
    if dh!=m["database_sha256"] or published!=m["published_posts"]:
        raise ValueError("DB or articles not preserved")
    assets=media_inventory(app)
    if digest(json.dumps(assets,sort_keys=True).encode())!=m["assets_sha256"]:
        raise ValueError("Images changed")
    print("POST_DEPLOY_93_ARTICLES_PRESERVED=yes",flush=True)
    print("POST_DEPLOY_PROTECTED_ASSETS="+str(len(assets)),flush=True)
    print("POST_DEPLOY_ALL_SIX_TEMPLATE_HASHES_VERIFIED=yes",flush=True)

def main() -> None:
    p=argparse.ArgumentParser();p.add_argument("action",choices=("check","install","verify","rollback"))
    p.add_argument("--app",type=Path,default=APP)
    p.add_argument("--backup",type=Path)
    a=p.parse_args()
    if a.action == "rollback":
        if not a.backup: p.error("backup required")
        rollback(a.app,a.backup);return
    if a.action == "verify":
        if not a.backup: p.error("backup required")
        verify(a.app,a.backup);return
    paths=safe_paths(a.app)
    originals={name: path.read_text(encoding="utf-8") for name,path in paths.items()}
    modified={name:patch(name,s) for name,s in originals.items()}
    print("ALLOWLIST_ONLY="+",".join(PAGES),flush=True)
    for name in PAGES:
        assert modified[name].startswith(originals[name].split("{% block content %}")[0]) if name!="base" else True
    if a.action=="install":
        if not a.backup:p.error("backup required")
        install(a.app,a.backup)
    else:
        print("PERSONAL_UPGRADE_PREFLIGHT=yes",flush=True)
if __name__ == "__main__": main()
