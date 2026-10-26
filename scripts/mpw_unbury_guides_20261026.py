#!/usr/bin/env python3
"""Unbury the ten original MojPlayWin field guides and the old site directory.

The source has ten complete articles in a collapsed homepage section and the
whole directory in another collapsed section. Publish each full article at its
own stable indexable URL; replace the two collapsible blobs with visible links.
Use the live canonical homepage nav, preserve all original article content,
homepage fragment IDs, URLs, existing routes, and protected sibling sites.
Only exact MojPlayWin main-site paths are changed. A SHA backup supports rollback.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

ACCOUNT=Path("/home/zomorod2")
ROOT=ACCOUNT/"mojplaywin.com"
HOME=ROOT/"design-preview-20261017/production-home-20261017.html"
SITEMAP=ROOT/"design-preview-20261017/_mpw_sitemap_three_indexable_20261017.php"
BASE=ROOT/"mpw-editorial"
OLD=BASE/"field-guides/20261023"
OLD_CONFIG=OLD/".htaccess"
GUIDES=BASE/"field-guides/original-ten"
DIRECTORY=BASE/"site-directory"
NAV_CSS=BASE/"revenue/assets/mpw-one-shell-20261026.css"
STYLESHEET=GUIDES/"assets/mpw-field-guides-20261026.css"
HOME_MARK='data-mpw-unburied-guides="20261026"'
SITEMAP_MARK="// MPW_12_STANDALONE_LEGACY_PAGES_20261026"
PREVIOUS_MAP="// MPW_MAIN_NAV_SITEMAP_20261026: indexable navigational destinations"
HEADER_RE=re.compile(r'<header\b[^>]*class="mw-site-nav"[^>]*>[\s\S]*?</header>',re.I)
ARTICLE_RE=re.compile(r'<article class="mw-card" id="(home-guide-[a-z0-9-]+)">([\s\S]*?)</article>',re.I)
SLUGS=(
 "vertical-slice","accessible-play","ai-workflow-risk","ai-privacy",
 "demo-proof","product-readiness","web-discovery","support-library",
 "vancouver-pilot-plan","agro-scenario-dashboard",
)
STYLE=r"""/* MojPlayWin extracted original guides: scoped to new main-site pages. */
*{box-sizing:border-box}
body.mpw-field-guide-site{margin:0;background:radial-gradient(ellipse at 75% 0%,#243128 0%,transparent 55%),#0c1015;color:#f3ecde;font:16px/1.7 system-ui,Arial,sans-serif}
.mpw-field-guide-site a{color:#efcb81}
.mpw-field-guide-site a:focus-visible{outline:3px solid #f5d893;outline-offset:3px}
.fg-skip{position:absolute;left:-9999px;top:0;padding:12px;background:#fff;color:#111!important}
.fg-skip:focus{left:8px;z-index:999}
.fg-main{width:min(1100px,calc(100% - 28px));margin:32px auto 58px}
.fg-breadcrumb{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:0 0 20px;font-size:.92rem}
.fg-card,.fg-article{background:#171c23;border:1px solid #6b5940;border-radius:20px;overflow:hidden;box-shadow:0 18px 38px #0005}
.fg-article>img{width:100%!important;height:clamp(230px,32vw,400px)!important;object-fit:cover!important;display:block}
.fg-article>.mw-card-copy{padding:clamp(22px,4vw,44px)}
.fg-article small{display:block;color:#e0bc78;letter-spacing:.09em;font-weight:800;text-transform:uppercase}
.fg-article h1,.fg-main h1{font-size:clamp(1.85rem,4.5vw,3rem);line-height:1.18;color:#f4d9a3;margin:13px 0 18px}
.fg-article h2{font-size:clamp(1.2rem,2.5vw,1.5rem);color:#efcd8e;margin:25px 0 9px}
.fg-article p,.fg-card p,.fg-main>p{max-width:80ch;line-height:1.75;color:#e4ded4}
.fg-article li{margin:7px 0}.fg-article ol{padding-left:25px}
.fg-readable{display:block;padding:4px 0 18px;border-top:1px solid #68533a;margin-top:24px}
.fg-next{padding:24px 0;display:flex;flex-wrap:wrap;gap:18px}
.fg-grid,.fg-index-page .mw-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin:24px 0}
.fg-card{padding:21px;min-width:0}.fg-card img{width:100%;height:160px;object-fit:cover;border-radius:12px}
.fg-card h2,.fg-card h3{font-size:1.2rem;line-height:1.35;margin:14px 0 8px}
.fg-card a{font-weight:800;text-underline-offset:4px}
.fg-index-page .mw-card{min-width:0;border:1px solid #716246;background:#192028;border-radius:16px;padding:24px}
.fg-index-page .mw-links{display:flex;flex-wrap:wrap;gap:10px}
.fg-index-page .mw-links a{display:inline-flex;padding:9px 11px;border-radius:8px;border:1px solid #796547;text-decoration:none}
.fg-index-page .mw-card-copy h3{margin:0 0 16px;color:#edcb8c}
.fg-footer{width:min(1100px,calc(100% - 28px));margin:0 auto 36px;border-top:1px solid #6b5940;padding:20px 0;display:flex;flex-wrap:wrap;gap:20px}
.fg-footer a{font-weight:700}
@media(max-width:720px){.fg-grid,.fg-index-page .mw-grid{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;animation:none!important;transition:none!important}}
"""
HOME_STYLE="""<style id="mpw-home-unburied-guides-css-20261026">
.mpw-unburied-section{box-sizing:border-box;max-width:1240px;margin:32px auto;padding:clamp(18px,3vw,32px);border:1px solid #806842;border-radius:20px;background:#151a1f;color:#f4ead8}
.mpw-unburied-section *{box-sizing:border-box}
.mpw-unburied-section h2{font-size:clamp(1.5rem,3vw,2.1rem);color:#f2d18d}
.mpw-unburied-section p{color:#dbd6c8;line-height:1.7}
.mpw-unburied-section .mpw-unburied-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px;margin:20px 0}
.mpw-unburied-section .mpw-unburied-item{padding:15px;border:1px solid #615036;border-radius:12px;background:#24272c}
.mpw-unburied-section .mpw-unburied-item h3{font-size:1rem;line-height:1.4;margin:0}
.mpw-unburied-section a{display:inline-block;color:#f0c67c;text-underline-offset:4px;min-height:44px;padding:9px 0}
.mpw-unburied-section a:focus-visible{outline:3px solid #f5d893}
@media(max-width:680px){.mpw-unburied-section .mpw-unburied-grid{grid-template-columns:1fr}}
</style>"""

def fail(msg):raise RuntimeError(msg)
def sha(b):return hashlib.sha256(b).hexdigest()
def clean(s):return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",s))).strip()
def destination(slug):return "/mpw-editorial/field-guides/original-ten/"+slug+"/"
def title_and_desc(inner):
    m=re.search(r"<h3>([\s\S]*?)</h3>",inner,re.I)
    p=re.search(r"<p>([\s\S]*?)</p>",inner,re.I)
    if not m or not p:fail("Old guide lacks title or summary")
    return clean(m.group(1)),clean(p.group(1))
def escape(s):return html.escape(s,quote=True)

def span_balanced_details(doc,marker):
    token='<details class="mpw-content-fold" data-mpw-fold="'+marker+'">'
    if doc.count(token)!=1:fail("Expected one folded main-home block "+marker)
    start=doc.index(token)
    depth=0
    for m in re.finditer(r"</?details\b[^>]*>",doc[start:],re.I):
        tag=m.group(0)
        depth+=(-1 if tag.startswith("</") else 1)
        if depth==0:return start,start+m.end(),doc[start:start+m.end()]
        if depth<0:break
    fail("Unbalanced HTML details for "+marker)

def parse_home(home):
    s0,e0,old_guides=span_balanced_details(home,"mpw-home-ten-guides")
    s1,e1,old_directory=span_balanced_details(home,"site-directory")
    if not (s0<e0<s1<e1):fail("Homepage fold sequence has changed")
    cards=ARTICLE_RE.findall(old_guides)
    if len(cards)!=10 or old_guides.count('<article class="mw-card" id="home-guide-')!=10:
        fail("Exactly ten original guides required")
    if [p.removeprefix("home-guide-") for p,_ in cards]!=list(SLUGS):
        fail("Original guide order/identity unexpectedly changed")
    if old_guides.count("<section")!=1 or old_directory.count("<section")!=1:
        fail("Unexpected nested homepage sections")
    dm=re.search(r'<section class="mw-section" id="site-directory"[\s\S]*?</section>',old_directory,re.I)
    if not dm or old_directory.count('id="site-directory"')!=1:fail("Site directory extract changed")
    if len(re.findall(r'<a href="/[^"]+"',dm.group(0)))<15:
        fail("Old complete site directory is missing entries")
    return (s0,e0,s1,e1,cards,dm.group(0))

def header_from_home(home):
    found=list(HEADER_RE.finditer(home))
    if len(found)!=1:fail("Main site nav must be unique")
    nav=found[0].group(0)
    for marker in ('aria-label="Primary MojPlayWin navigation"',
                   'href="/services/"','data-mpw-earning-directory="v1"'):
        if marker not in nav:fail("Official header has drifted: "+marker)
    return nav.replace('<header class="mw-site-nav"',
        '<header class="mw-site-nav mpw-unified-shell" data-mpw-extracted-guides="20261026"',1)

def doc_shell(title,description,url,header,content):
    return ('<!doctype html><html lang="en" dir="ltr"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="robots" content="index,follow,max-image-preview:large">'
        '<title>'+escape(title)+' | MojPlayWin</title>'
        '<meta name="description" content="'+escape(description[:155])+'">'
        '<link rel="canonical" href="https://mojplaywin.com'+url+'">'
        '<meta property="og:title" content="'+escape(title)+'">'
        '<meta property="og:description" content="'+escape(description[:200])+'">'
        '<meta property="og:type" content="article">'
        '<link rel="stylesheet" href="/mpw-editorial/revenue/assets/mpw-one-shell-20261026.css">'
        '<link rel="stylesheet" href="/mpw-editorial/field-guides/original-ten/assets/mpw-field-guides-20261026.css">'
        '</head><body class="mpw-field-guide-site"><a class="fg-skip" href="#content">Skip to content</a>'
        +header+content+
        '<footer class="fg-footer" aria-label="MojPlayWin site navigation">'
        '<a href="/">Home</a><a href="/mpw-editorial/field-guides/original-ten/">Original guides</a>'
        '<a href="/mpw-editorial/site-directory/">Site directory</a>'
        '<a href="/services/">Services</a><a href="/store/">Store</a>'
        '<a href="/contact/">Contact</a></footer></body></html>')

def render_article(slug,inner,header):
    title,description=title_and_desc(inner)
    doc=inner
    h3=re.search(r"<h3>([\s\S]*?)</h3>",doc,re.I)
    doc=doc[:h3.start()]+'<h1>'+h3.group(1)+'</h1>'+doc[h3.end():]
    intro=re.compile(r"<details>\s*<summary\b[^>]*>[\s\S]*?</summary>",re.I)
    doc,num=intro.subn('<section class="fg-readable" aria-label="Full practical guide">',doc,count=1)
    if num!=1 or doc.count("</details>")!=1:
        fail("Original guide expansion is not unambiguous: "+slug)
    doc=doc.replace("</details>","</section>",1)
    doc=doc.replace("<h4>","<h2>").replace("</h4>","</h2>")
    content=('<main id="content" class="fg-main"><nav class="fg-breadcrumb" aria-label="Breadcrumb">'
             '<a href="/">Home</a> / <a href="/mpw-editorial/field-guides/original-ten/">Original guides</a>'
             ' / <span>'+escape(title)+'</span></nav>'
             '<article class="fg-article" data-mpw-full-guide="20261026">'+doc+'</article>'
             '<div class="fg-next"><a href="/mpw-editorial/field-guides/original-ten/">Browse all ten guides</a>'
             '<a href="/mpw-editorial/site-directory/">Explore all site pages</a></div></main>')
    return doc_shell(title,description,destination(slug),header,content).encode("utf-8")

def render_guide_hub(cards,header):
    listing=[]
    for identity,inner in cards:
        slug=identity.removeprefix("home-guide-")
        title,description=title_and_desc(inner)
        im=re.search(r'<img\b[^>]*\bsrc="([^"]+)"',inner,re.I)
        image_tag=('<img src="'+escape(im.group(1))+'" alt="" loading="lazy" decoding="async">' if im else '')
        listing.append('<article class="fg-card">'+image_tag+'<h2><a href="'+destination(slug)+'">'
                       +escape(title)+'</a></h2><p>'+escape(description)+'</p></article>')
    content=('<main id="content" class="fg-main"><nav class="fg-breadcrumb" aria-label="Breadcrumb">'
        '<a href="/">Home</a> / Original guides</nav>'
        '<h1>Ten original MojPlayWin field guides</h1>'
        '<p>Full, independently accessible guides to game design, AI, digital products,'
        ' web services, international collaboration and agricultural decision-making.'
        ' Each contains a practical method, example and quality checklist.</p>'
        '<div class="fg-grid">'+''.join(listing)+'</div>'
        '<p><a href="/mpw-editorial/field-guides/20261023/index.html">Browse the 50 existing technical field guides</a></p>'
        '<p><a href="/mpw-editorial/site-directory/">Browse all other MojPlayWin pages</a></p></main>')
    return doc_shell("Ten original field guides","Ten complete MojPlayWin practical learning guides.",
                     "/mpw-editorial/field-guides/original-ten/",header,content).encode("utf-8")

def render_site_directory(section,header):
    section=section.replace('<h2 id="mw-directory-title">','<h1 id="mw-directory-title">',1)
    section=section.replace('</h2>','</h1>',1)
    if section.count('<h1')!=1:fail("Site-directory heading duplication")
    content=('<main id="content" class="fg-main fg-index-page"><nav class="fg-breadcrumb" aria-label="Breadcrumb">'
             '<a href="/">Home</a> / Site directory</nav>'+section+
             '<p><a href="/mpw-editorial/field-guides/original-ten/">Ten original field guides</a></p>'
             '<section class="fg-card"><h2>Fifty existing Field Studio technical guides</h2>'
             '<p>Browse the preserved 2026-10-23 collection of 50 independently published guides, with a related browser game.</p>'
             '<p><a href="/mpw-editorial/field-guides/20261023/index.html">Open the original Field Studio collection</a></p></section></main>')
    return doc_shell("All MojPlayWin pages","Browse independent MojPlayWin pages and specialist sections.",
                     "/mpw-editorial/site-directory/",header,content).encode("utf-8")

def patch_home(home,cards,spans):
    s0,e0,s1,e1=spans
    if HOME_MARK in home:fail("Homepage already extracted")
    chunks=[]
    for identity,inner in cards:
        slug=identity.removeprefix("home-guide-")
        title,_=title_and_desc(inner)
        chunks.append('<article class="mpw-unburied-item" id="'+identity+'"><h3><a href="'
          +destination(slug)+'">'+escape(title)+'</a></h3></article>')
    hub=('<section class="mpw-unburied-section" id="mpw-home-ten-guides" '
         +HOME_MARK+' aria-labelledby="mpw-field-guide-links-title">'
         '<h2 id="mpw-field-guide-links-title">Ten independent field guides</h2>'
         '<p>Each original learning guide now has its own complete page,'
         ' including practical methods, examples and checklists.</p>'
         '<div class="mpw-unburied-grid">'+''.join(chunks)+'</div>'
         '<p><a href="/mpw-editorial/field-guides/original-ten/">Open the original field-guide library</a></p>'
         '<p><a href="/mpw-editorial/field-guides/20261023/index.html">Explore 50 earlier Field Studio guides</a></p></section>')
    directory=('<section class="mpw-unburied-section" id="site-directory" '
             'aria-labelledby="mpw-home-page-directory-title">'
             '<h2 id="mpw-home-page-directory-title">All MojPlayWin pages</h2>'
             '<p>The complete site directory is now a standalone, accessible page.</p>'
             '<p><a href="/mpw-editorial/site-directory/">Explore the complete site directory</a></p>'
             '</section>')
    after=home[:s0]+hub+home[e0:s1]+directory+home[e1:]
    if after.count('id="mpw-home-ten-guides"')!=1 or after.count('id="site-directory"')!=1:
        fail("Homepage sections duplicated")
    if after.count('id="home-guide-')!=10:fail("Original fragment IDs lost")
    if 'data-mpw-fold="mpw-home-ten-guides"' in after or 'data-mpw-fold="site-directory"' in after:
        fail("Collapsed original content was not removed from homepage")
    if after.count("</head>")!=1:fail("Unexpected homepage head")
    return after.replace("</head>",HOME_STYLE+"</head>",1).encode("utf-8")

def patch_sitemap(original,old_urls):
    src=original.decode("utf-8")
    if SITEMAP_MARK in src:fail("Guide sitemap already registered")
    if src.count(PREVIOUS_MAP)!=1:fail("Sitemap registration anchor differs")
    urls=["/mpw-editorial/field-guides/original-ten/","/mpw-editorial/site-directory/"]
    urls += [destination(slug) for slug in SLUGS]
    urls += old_urls
    if len(urls)!=64 or len(set(urls))!=64:fail("Expected 12 new plus 52 legacy indexable URLs")
    insert='\n'+SITEMAP_MARK+'\n$paths = array_merge($paths, ['+','.join("'"+u+"'" for u in urls)+']);'
    newer=src.replace(PREVIOUS_MAP,PREVIOUS_MAP+insert,1)
    if newer.count(SITEMAP_MARK)!=1:fail("New sitemap marker not unique")
    return newer.encode("utf-8"),urls

def old_collection_urls():
    release=json.loads((OLD/"release.json").read_text("utf-8"))
    files=release.get("files_sha256",{})
    keys=sorted(key for key in files if re.fullmatch(r"guides/[a-z0-9-]+/index\.html",key))
    if release.get("guide_count")!=50 or len(keys)!=50:
        fail("Existing 50-guide collection manifest differs")
    for relative in keys+["index.html","prism-relay/index.html"]:
        target=OLD/relative
        if not target.is_file() or target.is_symlink():fail("Old guide missing: "+relative)
        if sha(target.read_bytes())!=files[relative]:fail("Old field-guide original hash changed: "+relative)
    return ["/mpw-editorial/field-guides/20261023/"+p for p in ["index.html","prism-relay/index.html"]+keys]

def paths_for_new_files():
    expected={GUIDES/"index.html",GUIDES/".htaccess",STYLESHEET,DIRECTORY/"index.html",DIRECTORY/".htaccess",OLD_CONFIG}
    expected.update(GUIDES/slug/"index.html" for slug in SLUGS)
    return expected

def verify_root():
    if ROOT.is_symlink() or ROOT.resolve()!=ROOT or ROOT.name!="mojplaywin.com":fail("Wrong site root")
    for path in (ROOT,BASE,OLD,HOME.parent,SITEMAP.parent,NAV_CSS.parent):
        if not path.is_dir() or path.is_symlink():fail("Unsafe main site directory "+str(path))
    for path in (HOME,SITEMAP,NAV_CSS,ROOT/".htaccess"):
        if not path.is_file() or path.is_symlink():fail("Missing main site source "+str(path))
    if not (120000<len(HOME.read_bytes())<850000):fail("Homepage size drift")
    if OLD_CONFIG.exists() or OLD_CONFIG.is_symlink():fail("Old guide collection has existing local routing; will not overwrite")
    for p in (OLD/"index.html",OLD/"release.json"):
        if not p.is_file() or p.is_symlink():fail("Original 50-guide collection unavailable")
    if ".mpw-unified-shell" not in NAV_CSS.read_text("utf-8","replace"):
        fail("Unified navigation stylesheet is unavailable")
    for path in (GUIDES,DIRECTORY):
        if path.exists() or path.is_symlink():fail("New content path already occupied "+str(path))

def backup_dir(run):
    if not re.fullmatch(r"[0-9]{8,20}",run):fail("Invalid GitHub run ID")
    return ACCOUNT/(".mpw-unbury-legacy-"+run)

def atomic(path,data,mode):
    fd,temp=tempfile.mkstemp(prefix=".mpw-unbury-",dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def php_lint(blob):
    fd,name=tempfile.mkstemp(prefix=".mpw-site-map-unbury-",suffix=".php",dir=SITEMAP.parent)
    try:
        with os.fdopen(fd,"wb") as stream:stream.write(blob)
        p=subprocess.run(["php","-l",name],capture_output=True,text=True,timeout=20)
        if p.returncode:fail("Sitemap PHP syntax failed")
    finally:
        if os.path.exists(name):os.unlink(name)

def planned(home_bytes,map_bytes,old_urls):
    home=home_bytes.decode("utf-8")
    s0,e0,s1,e1,cards,directory_section=parse_home(home)
    head=header_from_home(home)
    output={}
    output[GUIDES/"index.html"]=render_guide_hub(cards,head)
    output[DIRECTORY/"index.html"]=render_site_directory(directory_section,head)
    output[GUIDES/".htaccess"]=b"DirectoryIndex index.html\n"
    output[DIRECTORY/".htaccess"]=b"DirectoryIndex index.html\n"
    output[OLD_CONFIG]=b"DirectoryIndex index.html\n"
    output[STYLESHEET]=STYLE.encode("utf-8")
    for identity,inner in cards:
        slug=identity.removeprefix("home-guide-")
        output[GUIDES/slug/"index.html"]=render_article(slug,inner,head)
    if set(output)!=paths_for_new_files():fail("Unexpected new file inventory")
    newhome=patch_home(home,cards,(s0,e0,s1,e1))
    newmap,urls=patch_sitemap(map_bytes,old_urls)
    if len(urls)!=64:fail("Expected 64 new-and-existing indexable URLs")
    for p in (GUIDES/"index.html",DIRECTORY/"index.html",*(GUIDES/s/"index.html" for s in SLUGS)):
        doc=output[p].decode("utf-8")
        if (doc.count("<h1")!=1 or doc.count('rel="canonical"')!=1
            or doc.count('data-mpw-extracted-guides="20261026"')!=1
            or doc.count("<main")!=1 or doc.count("</main>")!=1):
            fail("Standalone page HTML structure failed: "+str(p))
    return output,newhome,newmap,urls

def cleanup_created(created,dirs,output):
    for path in reversed(created):
        if path.is_file() and not path.is_symlink() and sha(path.read_bytes())==sha(output[path]):
            path.unlink()
    for folder in sorted(dirs,key=lambda x:len(x.parts),reverse=True):
        if folder.is_dir() and not folder.is_symlink():
            try:folder.rmdir()
            except OSError:pass

def publish(run):
    verify_root()
    before_home=HOME.read_bytes();before_map=SITEMAP.read_bytes()
    old_urls=old_collection_urls()
    output,after_home,after_map,urls=planned(before_home,before_map,old_urls)
    php_lint(after_map)
    backup=backup_dir(run)
    if backup.exists() or backup.is_symlink():fail("Existing backup run")
    backup.mkdir(mode=0o700)
    meta={"run":run,"before":{"home":sha(before_home),"sitemap":sha(before_map)},
          "after":{"home":sha(after_home),"sitemap":sha(after_map)},
          "created":{str(p.relative_to(ROOT)):sha(content) for p,content in output.items()},
          "urls":urls,
          "mode":{"home":stat.S_IMODE(HOME.stat().st_mode),
                  "sitemap":stat.S_IMODE(SITEMAP.stat().st_mode)}}
    for name,content in (("home",before_home),("sitemap",before_map)):
        with (backup/(name+".before")).open("xb") as f:
            os.fchmod(f.fileno(),0o600);f.write(content)
    with (backup/"manifest.json").open("x",encoding="utf-8") as f:
        os.fchmod(f.fileno(),0o600);json.dump(meta,f,sort_keys=True)
    dirs=[GUIDES,DIRECTORY,GUIDES/"assets"]+[GUIDES/s for s in SLUGS]
    created=[];made_dirs=[];edited=[]
    try:
        for folder in dirs:
            folder.mkdir(mode=0o755)
            made_dirs.append(folder)
        for p,content in output.items():
            if p.exists() or p.is_symlink():fail("Concurrent new file "+str(p))
            with p.open("xb") as f:
                os.fchmod(f.fileno(),0o644);f.write(content);f.flush();os.fsync(f.fileno())
            created.append(p)
            if sha(p.read_bytes())!=sha(content):fail("Created page SHA mismatch "+str(p))
        for path,original,new,key in (
                (HOME,before_home,after_home,"home"),
                (SITEMAP,before_map,after_map,"sitemap")):
            if path.is_symlink() or sha(path.read_bytes())!=sha(original):
                fail("Concurrent change to "+key)
            atomic(path,new,meta["mode"][key]);edited.append((path,original,new,key))
            if sha(path.read_bytes())!=sha(new):fail("Modified page SHA mismatch "+key)
    except BaseException:
        for path,original,new,key in reversed(edited):
            if not path.is_symlink() and path.is_file() and sha(path.read_bytes())==sha(new):
                atomic(path,original,meta["mode"][key])
        cleanup_created(created,made_dirs,output)
        raise
    print("MPW_TEN_STANDALONE_GUIDES_AND_SITE_DIRECTORY_PUBLISHED=PASS")
    print("MPW_NEW_INDEXABLE_URLS="+json.dumps(urls))

def rollback(run):
    backup=backup_dir(run)
    path=backup/"manifest.json"
    if not backup.is_dir() or backup.is_symlink() or not path.is_file():fail("No verified release backup")
    meta=json.loads(path.read_text("utf-8"))
    if meta.get("run")!=run or set(meta.get("created",{}))!={str(p.relative_to(ROOT)) for p in paths_for_new_files()}:
        fail("Backup inventory mismatch")
    for p,key in ((HOME,"home"),(SITEMAP,"sitemap")):
        if not p.is_file() or p.is_symlink() or sha(p.read_bytes())!=meta["after"][key]:
            fail("A shared live file changed since publication")
    for rel,digest in meta["created"].items():
        p=ROOT/rel
        if not p.is_file() or p.is_symlink() or sha(p.read_bytes())!=digest:
            fail("One new page has been edited since publication "+rel)
    previous={}
    for key in ("home","sitemap"):
        blob=(backup/(key+".before")).read_bytes()
        if sha(blob)!=meta["before"][key]:fail("Backup SHA mismatch "+key)
        previous[key]=blob
    atomic(HOME,previous["home"],meta["mode"]["home"])
    atomic(SITEMAP,previous["sitemap"],meta["mode"]["sitemap"])
    for rel in sorted(meta["created"],key=lambda x:len(x.split("/")),reverse=True):
        (ROOT/rel).unlink()
    dirs=[GUIDES/"assets"]+[GUIDES/s for s in SLUGS]+[GUIDES,DIRECTORY]
    for folder in sorted(dirs,key=lambda x:len(x.parts),reverse=True):
        folder.rmdir()
    print("MPW_LEGACY_GUIDES_EXACT_ROLLBACK=PASS")

def selftest():
    assert len(SLUGS)==10 and len(set(SLUGS))==10
    f='<details class="mpw-content-fold" data-mpw-fold="sample"><details>abc</details></details>'
    assert span_balanced_details(f,"sample")[:2]==(0,len(f))
    assert len(paths_for_new_files())==16
    assert b"DirectoryIndex index.html" in b"DirectoryIndex index.html\n"
    print("MPW_GUIDE_EXTRACTION_SELFTEST_OK")

if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1]=="selftest":selftest()
    elif len(sys.argv)==3 and sys.argv[1]=="publish":publish(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=="rollback":rollback(sys.argv[2])
    else:raise SystemExit("Usage: selftest | publish RUN | rollback RUN")
