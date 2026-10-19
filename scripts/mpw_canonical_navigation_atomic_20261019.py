#!/usr/bin/env python3
"""Fail-closed MojPlayWin root main-domain canonical navigation and null-JS repair.

Source of truth: actual byte-matched public root homepage header, not a copy
invented here. The 19 exact main static section files and 19 GET-only routes
(using ONE PHP shell) are harmonized. All nonnavigation content is preserved.
No homepage, child-site, payment, database or .htaccess changes.
"""
from pathlib import Path
import hashlib,json,os,pwd,re,stat,sys,tempfile

ROOT=Path("/home/zomorod2/mojplaywin.com")
HOME=ROOT.parent
PAGES=ROOT/"design-preview-20261017/mpw-ten-editorials-20261018/pages"
HOMEPAGE=ROOT/"design-preview-20261017/production-home-20261017.html"
PHP=ROOT/"design-preview-20261017/_mpw_dynamic_main_shell_20261019.php"
HT=ROOT/".htaccess"
STATIC=(
  "about-mojtaba-rozegar","about","agents","company","economy","industry",
  "knowledge","market","research","services","studio","ventures-agriculture",
  "ventures-cafe-restaurant","ventures-carpets","ventures-currency-crypto",
  "ventures-ecommerce","ventures-fuel-station","ventures-hospitality","ventures-jewelry-gold")
MARK="data-mpw-nav-harmonized-20261019"
HEADER_RE=re.compile(r'<header\b(?=[^>]*\bclass=["\'](?:mw-site-nav|mpw-header)["\'])[^>]*>[\s\S]*?</header\s*>',re.I)
OLD_DECL="const b=document.querySelector('.menu-toggle'),n=document.querySelector('.nav');"
OLD1="if(b){b.addEventListener('click',()=>{n.classList.toggle('open');b.setAttribute('aria-expanded',n.classList.contains('open'));});}"
OLD2="n.querySelectorAll('a').forEach(a=>a.addEventListener('click',()=>{n.classList.remove('open');b.setAttribute('aria-expanded','false');}));"
OLD3="window.addEventListener('keydown',e=>{if(e.key==='Escape'){n.classList.remove('open');b.setAttribute('aria-expanded','false');}});"
NEW1=OLD1.replace("if(b){","if(b&&n){",1)
NEW2="if(b&&n){"+OLD2+"}"
NEW3="if(b&&n){"+OLD3+"}"
PHP_BRANCH="    } elseif ($heads['mpw-header']===1) {"
PHP_APPEND="        $body=takeOne($body,'~<header\\b[^>]*class=[\"\\']mw-site-nav[\"\\'][^>]*>[\\s\\S]*?</header\\s*>~i',$newHeader,'canonical homepage navigation',true);\n"
PHP_TAIL="    return $body;\n}\n\nfunction layoutParts(): array {"

def sha(data):return hashlib.sha256(data).hexdigest()
def fail(msg):raise RuntimeError(msg)
def all_targets():return [PAGES/(name+".html") for name in STATIC]+[PHP]
def backup_dir(run):
    if not re.fullmatch(r"[0-9]{9,20}",run):fail("Invalid deployment run ID")
    return HOME/(".mpw-nav-canonical-"+run)
def guard():
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":fail("Wrong authorized hosting account")
    for p in (ROOT,PAGES,HOMEPAGE.parent):
        if not p.is_dir() or p.is_symlink():fail("Unexpected site directory")
    if ROOT.resolve()!=ROOT or not HOMEPAGE.is_file() or HOMEPAGE.is_symlink():
        fail("Homepage reference is not safe")
    if not HT.is_file() or HT.is_symlink():fail("Unexpected routing file")
    rewrite=HT.read_text("utf-8",errors="replace")
    if "/design-preview-20261017/production-home-20261017.html" not in rewrite:
        fail("Published homepage source changed")
    for name in STATIC:
        path="/design-preview-20261017/mpw-ten-editorials-20261018/pages/"+name+".html"
        if path not in rewrite:fail("Exact section route changed "+name)
    if "_mpw_dynamic_main_shell_20261019.php" not in rewrite:fail("Root-only PHP dispatcher changed")
    for target in all_targets():
        if not target.is_file() or target.is_symlink() or target.parent.is_symlink():
            fail("Expected root site target unavailable "+str(target))
    if len(all_targets())!=20:fail("Target list length changed")

def canonical(doc):
    matches=list(HEADER_RE.finditer(doc))
    if len(matches)!=1:fail("Homepage reference does not have exactly one nav header")
    header=matches[0].group(0)
    if (not header.startswith('<header class="mw-site-nav"') or
        'data-design="atelier-v4"' not in header or
        '<nav aria-label="Primary MojPlayWin navigation"' not in header or
        'id="mw-all-pages-menu"' not in header or
        '<details' not in header or
        header.count('href=')<10):
        fail("Canonical homepage navigation structure changed")
    if MARK in header:fail("Homepage must be read-only")
    return header.replace('<header ', '<header '+MARK+'="true" ',1)

def js_guard(document):
    if OLD_DECL not in document:return document
    count=document.count(OLD_DECL)
    if count!=1:fail("Legacy navigation script occurs unexpected number of times")
    seen=[OLD1 in document,OLD2 in document,OLD3 in document]
    guarded=[NEW1 in document,NEW2 in document,NEW3 in document]
    if all(seen) and not any(guarded):
        for a,b in ((OLD1,NEW1),(OLD2,NEW2),(OLD3,NEW3)):
            if document.count(a)!=1:fail("Legacy navigation JS drifted")
            document=document.replace(a,b,1)
    elif all(guarded) and not any(seen[:1]):
        # Company-page already guards this now-obsolete standalone nav script.
        pass
    else:fail("Mixed or modified legacy navigation JS; no source rewrite")
    return document

def static_patch(doc,header):
    if MARK in doc:fail("Already harmonized")
    original=list(HEADER_RE.finditer(doc))
    if len(original)!=1:fail("Expected one root navigation header")
    if "mpw-design-unified-v1" not in doc or "mpw-legal-one-line" not in doc:
        fail("Approved previous design/footer release is missing")
    old=original[0]
    next_=doc[:old.start()]+header+doc[old.end():]
    next_=js_guard(next_)
    if next_.count(MARK)!=1 or next_.count('id="mw-all-pages-menu"')!=1:
        fail("Canonical menu duplicate")
    for signature in ('<main','<footer','mpw-legal-one-line'):
        if next_.count(signature)!=doc.count(signature):fail("Protected structural signature changed "+signature)
    return next_

def php_patch(document):
    if "canonical homepage navigation" in document:fail("PHP already upgraded")
    if document.count(PHP_BRANCH)!=1 or document.count(PHP_TAIL)!=1:
        fail("Dynamic shell did not match expected approved version")
    if "standard footer replacement" not in document or "MojPlayWin design alignment stylesheet" not in document:
        fail("Newer PHP shell or previous verified footer release missing")
    document=document.replace(PHP_BRANCH,PHP_APPEND+PHP_BRANCH,1)
    # All routed GET pages have legacy source HTML; only update exact known
    # obsolete selectors if present, so active interaction handlers are retained.
    prelude=r"""
    $legacyNav=[
      'if(b){b.addEventListener(\'click\',()=>{n.classList.toggle(\'open\');b.setAttribute(\'aria-expanded\',n.classList.contains(\'open\'));});}'
       => 'if(b&&n){b.addEventListener(\'click\',()=>{n.classList.toggle(\'open\');b.setAttribute(\'aria-expanded\',n.classList.contains(\'open\'));});}',
      'n.querySelectorAll(\'a\').forEach(a=>a.addEventListener(\'click\',()=>{n.classList.remove(\'open\');b.setAttribute(\'aria-expanded\',\'false\');}));'
       => 'if(b&&n){n.querySelectorAll(\'a\').forEach(a=>a.addEventListener(\'click\',()=>{n.classList.remove(\'open\');b.setAttribute(\'aria-expanded\',\'false\');}));}',
      'window.addEventListener(\'keydown\',e=>{if(e.key===\'Escape\'){n.classList.remove(\'open\');b.setAttribute(\'aria-expanded\',\'false\');}});'
       => 'if(b&&n){window.addEventListener(\'keydown\',e=>{if(e.key===\'Escape\'){n.classList.remove(\'open\');b.setAttribute(\'aria-expanded\',\'false\');}});}',
    ];
    if (str_contains($body,'const b=document.querySelector(\'.menu-toggle\'),n=document.querySelector(\'.nav\');')) {
        foreach ($legacyNav as $originalJs=>$guardedJs) {
            if (str_contains($body,$originalJs) && !str_contains($body,$guardedJs)) {
                $body=str_replace($originalJs,$guardedJs,$body);
            }
        }
    }
"""
    document=document.replace(PHP_TAIL,prelude+PHP_TAIL,1)
    if document.count("canonical homepage navigation")!=1 or document.count("$legacyNav=[")!=1:
        fail("New PHP code not installed uniquely")
    return document

def atomic(p,data,mode):
    if not p.is_file() or p.is_symlink():fail("Atomic destination changed")
    fd,temp=tempfile.mkstemp(dir=p.parent,prefix=".mpw-nav-header-")
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.replace(temp,p)
    finally:
        if os.path.lexists(temp):os.unlink(temp)

def plan():
    import subprocess
    guard()
    before=HOMEPAGE.read_bytes()
    header=canonical(before.decode("utf-8"))
    changes=[]
    for p in all_targets():
        raw=p.read_bytes()
        patched=(php_patch(raw.decode("utf-8")) if p==PHP
                 else static_patch(raw.decode("utf-8"),header)).encode("utf-8")
        if p==PHP:
            fd,tmp=tempfile.mkstemp(suffix=".php",dir=HOME,prefix=".mpw-nav-lint-")
            try:
                with os.fdopen(fd,"wb") as f:f.write(patched)
                result=subprocess.run(["php","-l",tmp],capture_output=True,text=True,timeout=25)
                if result.returncode!=0:fail("Generated PHP lint failed "+result.stderr[-500:])
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
        changes.append((p,raw,patched,stat.S_IMODE(p.stat().st_mode)))
    return changes,sha(before)

def install(run):
    changes,homehash=plan()
    recovery=backup_dir(run)
    if recovery.exists() or recovery.is_symlink():fail("Deployment ID already exists")
    recovery.mkdir(mode=0o700)
    manifest={"run":run,"home_sha":homehash,"pages":[]}
    for idx,(p,old,new,mode) in enumerate(changes):
        name=f"{idx:02d}.backup"
        with (recovery/name).open("xb") as f:
            os.fchmod(f.fileno(),0o600);f.write(old);f.flush();os.fsync(f.fileno())
        manifest["pages"].append({"path":str(p),"backup":name,"old":sha(old),"new":sha(new),"mode":mode})
    with (recovery/"manifest.json").open("x") as f:
        os.fchmod(f.fileno(),0o600);json.dump(manifest,f);f.flush();os.fsync(f.fileno())
    changed=[]
    try:
        if sha(HOMEPAGE.read_bytes())!=homehash:fail("Home reference changed during preflight")
        for p,old,new,mode in changes:
            if sha(p.read_bytes())!=sha(old):fail("Concurrent modification "+str(p))
            atomic(p,new,mode);changed.append((p,old,new,mode))
            if sha(p.read_bytes())!=sha(new):fail("Postwrite checksum mismatch")
    except BaseException:
        for p,old,new,mode in reversed(changed):
            if sha(p.read_bytes())==sha(new):atomic(p,old,mode)
        raise
    print("MPW_CANONICAL_NAV_INSTALLED=20; REFERENCE_HOME_UNCHANGED=true",flush=True)
def rollback(run):
    directory=backup_dir(run)
    if not directory.is_dir() or directory.is_symlink():fail("Recovery directory not safe")
    doc=json.loads((directory/"manifest.json").read_text("utf-8"))
    if doc["run"]!=run or len(doc["pages"])!=20 or sha(HOMEPAGE.read_bytes())!=doc["home_sha"]:
        fail("Unknown version or changed homepage")
    if {x["path"] for x in doc["pages"]}!={str(p) for p in all_targets()}:
        fail("Unknown rollback file set")
    for item in doc["pages"]:
        p=Path(item["path"])
        if sha(p.read_bytes())!=item["new"] or sha((directory/item["backup"]).read_bytes())!=item["old"]:
            fail("Concurrent file edit; unsafe rollback refused")
    for item in reversed(doc["pages"]):
        atomic(Path(item["path"]),(directory/item["backup"]).read_bytes(),item["mode"])
    print("MPW_CANONICAL_NAV_ROLLBACK=VERIFIED_20",flush=True)
def selftest():
    home='<header class="mw-site-nav" data-design="atelier-v4"><a href="/">Home</a><nav aria-label="Primary MojPlayWin navigation"><a href="/">Home</a>'+''.join('<a href="/games/">Games</a>' for i in range(10))+'<details id="mw-all-pages-menu"><summary>Explore all</summary></details></nav></header>'
    h=canonical(home)
    src='<html><body class="mpw-design-unified-v1"><header class="mpw-header"><a href="/">old</a></header><main><h1>About</h1></main><footer><span class="mpw-legal-one-line">Legal</span></footer></body></html>'
    next_=static_patch(src,h)
    assert "mpw-header" not in next_ and next_.count('data-mpw-nav-harmonized-20261019')==1
    assert '<main><h1>About</h1></main>' in next_
    sample='<script>\n'+OLD_DECL+'\n'+OLD1+'\n'+OLD2+'\n'+OLD3+'\n</script>'
    fixed=js_guard(sample)
    assert fixed.count("if(b&&n){")==3
    assert js_guard(fixed)==fixed
    try:static_patch(next_,h);raise AssertionError("Duplicate site navigation patch permitted")
    except RuntimeError:pass
    print("MPW_CANONICAL_NAV_SELFTEST=PASS")
if __name__=="__main__":
    if len(sys.argv)==2 and sys.argv[1]=="selftest":selftest()
    elif len(sys.argv)==2 and sys.argv[1]=="audit":
        changes,home=plan()
        print("MPW_CANONICAL_NAV_PREFLIGHT="+str(len(changes))+" HOME_SHA256="+home,flush=True)
    elif len(sys.argv)==3 and sys.argv[1]=="install":install(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=="rollback":rollback(sys.argv[2])
    else:fail("selftest|audit|install RUN|rollback RUN")
