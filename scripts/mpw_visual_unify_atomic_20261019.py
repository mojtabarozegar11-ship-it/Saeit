#!/usr/bin/env python3
"""MojPlayWin only: unify visual shell for 19 static + 19 routed PHP pages.

Preserve content, products, interactivity, game canvas, Django, route mappings
and five unrelated standalone child sites. This is an additive CSS enhancement.
The exact live homepage remains the visual reference and is not modified.
"""
from __future__ import annotations
import hashlib,json,os,pwd,re,stat,sys,tempfile
from pathlib import Path

HOME=Path("/home/zomorod2")
ROOT=HOME/"mojplaywin.com"
PAGES=ROOT/"design-preview-20261017/mpw-ten-editorials-20261018/pages"
PHP=ROOT/"design-preview-20261017/_mpw_dynamic_main_shell_20261019.php"
HT=ROOT/".htaccess"
ASSET=ROOT/"design-preview-20261017/static/site/mpw-main-visual-unify-20261019.css"
HOMEPAGE=ROOT/"design-preview-20261017/production-home-20261017.html"
URL="/design-preview-20261017/static/site/mpw-main-visual-unify-20261019.css"
MARK="mpw-design-unified-v1"
MAIN_MARK="mpw-visual-main-routes-v1"
STATIC=(
 "about-mojtaba-rozegar","about","agents","company","economy","industry",
 "knowledge","market","research","services","studio","ventures-agriculture",
 "ventures-cafe-restaurant","ventures-carpets","ventures-currency-crypto",
 "ventures-ecommerce","ventures-fuel-station","ventures-hospitality","ventures-jewelry-gold")
THEME="#08090b"
CSS=r"""
/* MojPlayWin main-domain design alignment, 2026-10-19. */
body.mpw-design-unified-v1{--mpw-base:#08090b;--mpw-gold:#dcb877;--mpw-edge:rgba(229,180,102,.48);background:#08090b!important;color:#f1e9da!important;color-scheme:dark}
body.mpw-design-unified-v1 .mw-site-nav,body.mpw-design-unified-v1 .mpw-header{
position:relative;z-index:45;box-sizing:border-box;width:100%;max-width:100%;display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:12px 20px;padding:15px clamp(16px,3.4vw,44px)!important;
background:linear-gradient(115deg,rgba(8,10,13,.97),rgba(25,24,20,.97))!important;border:0!important;border-bottom:1px solid rgba(224,181,98,.67)!important;box-shadow:0 15px 34px #0007!important;color:#f4eddf!important;backdrop-filter:blur(18px)}
body.mpw-design-unified-v1 .mw-site-nav .mw-brand,body.mpw-design-unified-v1 .mpw-header .mpw-brand{display:inline-flex;align-items:center;gap:11px;flex-shrink:0;color:#f9d899!important;text-decoration:none!important}
body.mpw-design-unified-v1 .mpw-header .mpw-mark{display:inline-block;width:54px!important;height:54px!important;min-width:54px;border:1px solid #e5bf78;border-radius:50%;background:#0b0e12 url('/design-preview-20261017/static/site/mojplaywin-atelier/official-coin-80.3ea52711f49d.webp') center/contain no-repeat!important;box-shadow:0 0 0 4px #bd853222,0 12px 28px #0009}
body.mpw-design-unified-v1 .mpw-header .mpw-mark>*{opacity:0!important}
body.mpw-design-unified-v1 .mw-site-nav .mw-brand img{width:54px!important;height:54px!important;object-fit:contain}
body.mpw-design-unified-v1 .mw-site-nav .mw-brand-copy strong,body.mpw-design-unified-v1 .mpw-header .mpw-brand>span:last-child{color:#f5d18c!important;font-size:clamp(1.02rem,1.5vw,1.25rem);font-weight:800}
body.mpw-design-unified-v1 .mw-site-nav .mw-brand-copy small,body.mpw-design-unified-v1 .mpw-header .mpw-brand small{color:#cec0ac!important;font-size:.71rem;letter-spacing:.055em}
body.mpw-design-unified-v1 .mw-site-nav nav,body.mpw-design-unified-v1 .mpw-header .mpw-nav{display:flex;flex:1 1 auto;min-width:0;align-items:center;gap:8px 15px;flex-wrap:wrap}
body.mpw-design-unified-v1 .mw-site-nav nav>a,body.mpw-design-unified-v1 .mpw-header .mpw-nav>a{color:#f3e7ce!important;text-decoration:none!important;font-size:.89rem;line-height:1.5}
body.mpw-design-unified-v1 .mw-site-nav nav>a:hover,body.mpw-design-unified-v1 .mpw-header .mpw-nav>a:hover{color:#ffe1a5!important}
body.mpw-design-unified-v1 .mw-site-nav a:focus-visible,body.mpw-design-unified-v1 .mpw-header a:focus-visible,body.mpw-design-unified-v1 .mpw-header button:focus-visible{outline:3px solid #f9dda0!important;outline-offset:3px}
body.mpw-design-unified-v1 .mw-nav-menu summary,body.mpw-design-unified-v1 .mpw-header .mpw-menu,body.mpw-design-unified-v1 .mpw-header .mpw-cta{border:1px solid #e5bd74aa!important;border-radius:12px!important;background:linear-gradient(120deg,#4c392d99,#0c1515e8)!important;color:#ffe0aa!important;box-shadow:inset 0 1px 1px #fff2,0 8px 22px #0005}
body.mpw-design-unified-v1 .mw-nav-panel{background:#111619!important;color:#f0e6d1!important;border:1px solid #a98a50!important;border-radius:16px!important;box-shadow:0 24px 55px #000b!important}
body.mpw-design-unified-v1 .mw-page-hero,body.mpw-design-unified-v1 .mpw-page-hero,body.mpw-design-unified-v1 .mw-hero,body.mpw-design-unified-v1 .mpw-hero{background:linear-gradient(120deg,#231e19ef,#0c1115f3)!important;border:1px solid var(--mpw-edge)!important;border-radius:clamp(18px,2.1vw,30px)!important;color:#f3e9da!important;box-shadow:0 24px 60px #0008,inset 0 1px 1px #fff2}
body.mpw-design-unified-v1 .mw-page-hero h1,body.mpw-design-unified-v1 .mpw-page-hero h1,body.mpw-design-unified-v1 .mw-hero h1{color:#ffe0a2!important}
body.mpw-design-unified-v1 :is(.mw-section,.mpw-section,.mw-card,.mpw-card,.mpw-page-card,.mpw-ten-card,.mpw-seven-item){border-color:#e5b76b66!important;background:linear-gradient(140deg,#24211fe2,#0c1116e6)!important;color:#f5ecdc!important;box-shadow:0 15px 38px #0006,inset 0 1px 0 #fff2;backdrop-filter:blur(12px)}
body.mpw-design-unified-v1 :is(.mw-section,.mpw-section,.mw-card,.mpw-card,.mpw-page-card,.mpw-ten-card,.mpw-seven-item) :is(h2,h3,h4,strong){color:#f6d699}
body.mpw-design-unified-v1 :is(.mw-section,.mpw-section,.mw-card,.mpw-card,.mpw-page-card,.mpw-ten-card,.mpw-seven-item) :is(p,li,small){color:#e8dfcf}
body.mpw-design-unified-v1 .mw-site-footer,body.mpw-design-unified-v1 .mpw-footer{background:linear-gradient(125deg,#111619,#090a0d)!important;color:#f3eade!important;border-top:1px solid #e5b76b88!important}
body.mpw-design-unified-v1 .mw-site-footer a,body.mpw-design-unified-v1 .mpw-footer a{color:#f1d194!important}
body.mpw-design-unified-v1 .mpw-legal-one-line{color:#f3d184!important;white-space:nowrap!important}
@media(max-width:760px){body.mpw-design-unified-v1 .mw-site-nav,body.mpw-design-unified-v1 .mpw-header{gap:10px;padding:13px 15px!important}body.mpw-design-unified-v1 .mw-site-nav nav,body.mpw-design-unified-v1 .mpw-header .mpw-nav{flex-basis:100%;gap:10px}}
@media(prefers-reduced-motion:reduce){body.mpw-design-unified-v1 *{scroll-behavior:auto!important}}
""".strip()+"\n"

LINK='<link rel="stylesheet" href="'+URL+'" data-design="mojplaywin-atelier-v4-alignment">'
def fail(v):raise RuntimeError(v)
def sha(b):return hashlib.sha256(b).hexdigest()
def paths():return [PAGES/(n+".html") for n in STATIC]+[PHP]
def backup_root(run):
    if not re.fullmatch(r"[0-9]{9,20}",run):fail("Unsafe run ID")
    return HOME/(".mpw-theme-unify-"+run)
def validate_paths():
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":fail("Wrong cPanel user")
    if ROOT.resolve()!=ROOT or ROOT.is_symlink() or not ROOT.is_dir():fail("Wrong document root")
    for p in [PAGES,ASSET.parent,HT.parent]:
        if not p.is_dir() or p.is_symlink():fail("Symlinked directory "+str(p))
    if not HT.is_file() or HT.is_symlink():fail("No trusted route map")
    routes=HT.read_text("utf-8",errors="replace")
    if "/design-preview-20261017/production-home-20261017.html" not in routes:fail("Homepage route unexpectedly changed")
    for n in STATIC:
        if "/design-preview-20261017/mpw-ten-editorials-20261018/pages/"+n+".html" not in routes:
            fail("Expected static route missing "+n)
    if "_mpw_dynamic_main_shell_20261019.php" not in routes:fail("Main-only dynamic route changed")
    if not HOMEPAGE.is_file() or MARK in HOMEPAGE.read_text("utf-8",errors="replace"):
        fail("Reference homepage missing or already changed")
    if ASSET.exists() or ASSET.is_symlink():fail("Shared new CSS filename is occupied")
    for p in paths():
        if not p.is_file() or p.is_symlink() or p.parent.is_symlink():
            fail("Unsafe static/PHP target "+str(p))
def add_body_class(tag):
    m=re.search(r'\bclass=(["\'])(.*?)\1',tag,re.I|re.S)
    if m:return tag[:m.start(2)]+m.group(2)+" "+MARK+tag[m.end(2):]
    return tag[:-1]+' class="'+MARK+'">'
def theme_meta(doc):
    match=list(re.finditer(r'<meta\b(?=[^>]*\bname=["\']theme-color["\'])[^>]*>',doc,re.I))
    if len(match)!=1:fail("Expected exactly one theme-color")
    m=match[0];tag=m.group(0)
    new,n=re.subn(r'(\bcontent\s*=\s*)(["\'])([^"\']*)\2',lambda q:q.group(1)+q.group(2)+THEME+q.group(2),tag,count=1,flags=re.I)
    if n!=1:fail("Original theme-color content is absent")
    return doc[:m.start()]+new+doc[m.end():]
def static_patch(doc):
    if MARK in doc or URL in doc:fail("Source already unified")
    if doc.count("</head>")!=1 or doc.count("</body>")!=1:fail("Unusual static HTML")
    body=list(re.finditer(r'<body\b[^>]*>',doc,re.I))
    if len(body)!=1:fail("Expected one static body")
    if not re.search(r'<footer\b[^>]*>[\s\S]*?mpw-legal-one-line',doc,re.I):
        fail("Previously approved rights footer missing")
    if not re.search(r'<header\b[^>]*class=["\'](?:mpw-header|mw-site-nav)["\']',doc,re.I):
        fail("Unrecognized header, manual review required")
    doc=theme_meta(doc).replace("</head>",LINK+"\n</head>",1)
    doc=re.sub(r'<body\b[^>]*>',lambda m:add_body_class(m.group(0)),doc,count=1,flags=re.I)
    if doc.count(URL)!=1 or doc.count(MARK)!=1:fail("CSS or body marker incorrectly installed")
    return doc
PHP_ANCHOR="    return $body;\n}\n\nfunction layoutParts(): array {"
PHP_ADD=r"""
    // Main-domain routed pages only. Keep all existing product interactions intact.
    $body=takeOne($body,'~</head\s*>~i',
      '<link rel="stylesheet" href="/design-preview-20261017/static/site/mpw-main-visual-unify-20261019.css" data-design="mojplaywin-atelier-v4-alignment">'."\n</head>",
      'MojPlayWin design alignment stylesheet',true);
    $body=preg_replace_callback('~<body\b[^>]*>~i',static function(array $m): string {
        $tag=$m[0];
        if (preg_match('~\bclass=(["\'])(.*?)\1~si',$tag,$c,PREG_OFFSET_CAPTURE)) {
            $v=$c[2][0];$at=$c[2][1];
            return substr($tag,0,$at).$v.' mpw-design-unified-v1'.substr($tag,$at+strlen($v));
        }
        return substr($tag,0,-1).' class="mpw-design-unified-v1">';
    },$body,1,$bodyChanges);
    if ($bodyChanges!==1)throw new RuntimeException('MojPlayWin body marker not uniquely installed');
    $body=preg_replace_callback('~<meta\b(?=[^>]*\bname=["\']theme-color["\'])[^>]*>~i',
      static function(array $m): string {
        return preg_replace('~(\bcontent\s*=\s*)(["\'])[^"\']*\2~i','$1$2#08090b$2',$m[0],1);
      },$body,1,$themeChanges);
    if ($themeChanges!==1)throw new RuntimeException('MojPlayWin brand theme meta not found');
    if (substr_count($body,'mpw-design-unified-v1')!==1)throw new RuntimeException('Duplicate visual marker');
"""
def php_patch(doc):
    if MARK in doc or URL in doc:fail("Main-only PHP already patched")
    if doc.count(PHP_ANCHOR)!=1:fail("Dynamic shell position changed")
    if "standard footer replacement" not in doc or "mpw-contact-safe-business-20261019" not in doc:
        fail("Previously verified dynamic PHP features missing")
    result=doc.replace(PHP_ANCHOR,PHP_ADD+PHP_ANCHOR,1)
    if result.count(MARK)!=3:fail("Unexpected PHP marker count")
    return result
def planned():
    validate_paths()
    out=[]
    for p in paths():
        before=p.read_bytes()
        new=(php_patch if p==PHP else static_patch)(before.decode("utf-8")).encode("utf-8")
        out.append((p,before,new,stat.S_IMODE(p.stat().st_mode)))
    if len(out)!=20:fail("Expected exactly twenty main-domain source files")
    return out
def atomic(p,raw,mode,allow_new=False):
    if p.is_symlink() or (not allow_new and not p.is_file()):fail("Unexpected atomic target")
    fd,tmp=tempfile.mkstemp(prefix=".mpw-visual-atomic-",dir=p.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(tmp,p)
    finally:
        if os.path.lexists(tmp):os.unlink(tmp)
def install(run):
    batch=planned()
    backup=backup_root(run)
    if backup.exists() or backup.is_symlink():fail("Existing deployment ID")
    backup.mkdir(mode=0o700)
    manifest=[]
    for i,(p,raw,new,mode) in enumerate(batch):
        name=f"{i:02d}.bak"
        with (backup/name).open("xb") as f:os.fchmod(f.fileno(),0o600);f.write(raw);f.flush();os.fsync(f.fileno())
        manifest.append({"path":str(p),"backup":name,"before":sha(raw),"after":sha(new),"mode":mode})
    css=CSS.encode("utf-8")
    record={"run":run,"rows":manifest,"asset":sha(css),"asset_path":str(ASSET)}
    with (backup/"manifest.json").open("x") as f:
        os.fchmod(f.fileno(),0o600);json.dump(record,f);f.flush();os.fsync(f.fileno())
    installed=[]
    try:
        atomic(ASSET,css,0o644,allow_new=True)
        for p,raw,new,mode in batch:
            if sha(p.read_bytes())!=sha(raw):fail("Concurrent modification "+str(p))
            atomic(p,new,mode);installed.append((p,raw,new,mode))
            if sha(p.read_bytes())!=sha(new):fail("Written file changed")
    except BaseException:
        for p,raw,new,mode in reversed(installed):
            if sha(p.read_bytes())==sha(new):atomic(p,raw,mode)
        if ASSET.is_file() and sha(ASSET.read_bytes())==sha(css):ASSET.unlink()
        raise
    print("MPW_VISUAL_UNIFICATION_INSTALLED=20; CSS=1; HOMEPAGE_UNCHANGED=true",flush=True)
def rollback(run):
    backup=backup_root(run)
    if not backup.is_dir() or backup.is_symlink():fail("Recovery directory unavailable")
    data=json.loads((backup/"manifest.json").read_text("utf-8"))
    if data["run"]!=run or data["asset_path"]!=str(ASSET) or len(data["rows"])!=20:fail("Recovery manifest mismatch")
    for row in data["rows"]:
        p=Path(row["path"])
        if p not in paths() or sha(p.read_bytes())!=row["after"] or sha((backup/row["backup"]).read_bytes())!=row["before"]:
            fail("Cannot roll back concurrent site modification")
    if not ASSET.is_file() or ASSET.is_symlink() or sha(ASSET.read_bytes())!=data["asset"]:
        fail("Cannot remove unknown CSS asset")
    for row in reversed(data["rows"]):
        atomic(Path(row["path"]),(backup/row["backup"]).read_bytes(),row["mode"])
    ASSET.unlink()
    print("MPW_VISUAL_UNIFICATION_ROLLBACK=20; CSS_REMOVED=true",flush=True)
def selftest():
    a='<!doctype html><html><head><meta name="theme-color" content="#103b2d"></head><body class="old mw-shell"><header class="mw-site-nav"></header><main><h1>Store</h1></main><footer class="mw-site-footer"><div class="mpx-bottom-bar"><span class="mpw-legal-one-line">☆ All Rights Reserved. ☆ 2022. ☆ Mojtaba roozegar ☆</span></div></footer></body></html>'
    q=static_patch(a)
    assert q.count(URL)==1 and 'class="old mw-shell mpw-design-unified-v1"' in q
    assert '<h1>Store</h1>' in q and 'content="#08090b"' in q
    b=a.replace('<body class="old mw-shell">','<body>').replace('class="mw-site-nav"','class="mpw-header"')
    q2=static_patch(b)
    assert 'class="mpw-design-unified-v1"' in q2
    try:static_patch(q);raise AssertionError("Duplicate edit allowed")
    except RuntimeError:pass
    assert 'mpw-design-unified-v1' in CSS and 'mw-site-nav' in CSS and 'mpw-header' in CSS
    print("MPW_VISUAL_UNIFICATION_SELFTEST=PASS")
if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1]=="selftest":selftest()
    elif len(sys.argv)==2 and sys.argv[1]=="audit":
        print("MPW_VISUAL_UNIFICATION_PREFLIGHT="+str(len(planned())))
    elif len(sys.argv)==3 and sys.argv[1]=="install":install(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=="rollback":rollback(sys.argv[2])
    else:fail("selftest|audit|install RUN_ID|rollback RUN_ID")
