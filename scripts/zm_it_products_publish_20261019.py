#!/usr/bin/env python3
"""Safe, additive deployment for all 21 existing ZM-R25 topic cards.
The separate Farm Dominion card at /farm-wars/ remains untouched.
Operations: prepare, install, verify, rollback, cleanup. Fail closed.
"""
from __future__ import annotations
import hashlib, html, json, os, re, shutil, stat, sys
from pathlib import Path

ROOT=Path("/home/zomorod2/public_html")
PREFIX="ZM-IT-PRODUCT-20261019"
EXPECTED={
"website-design","software-development","mobile-app-development","ux-design",
"applied-ai","business-automation","data-analytics","cloud-infrastructure",
"cybersecurity","ecommerce","digital-products","game-development",
"digital-animation","professional-content","seo","tech-project-management",
"api-engineering","backup-recovery","digital-training","software-qa",
"live-878f27b75f2daa"}
PATTERN=re.compile(r"^/topics/zm-r25/([a-z0-9-]+)/$")
HOME_MANIFEST=re.compile(rb"window\.ZOMOROD_ORBIT_DATA=(\{.*?\});</script>",re.S)

def die(message):
    raise RuntimeError(message)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def strict_file(path):
    if path.is_symlink() or not path.is_file():
        die("missing or symlink file: "+str(path))
    return path.read_bytes()

def stage_for(run_id):
    if not re.fullmatch(r"[0-9]{4,20}",run_id):
        die("invalid GitHub run ID")
    p=Path("/home/zomorod2")/(".zm-it-products-"+run_id)
    if p.is_symlink() or not p.is_dir():
        die("private stage absent")
    return p

def manifest_and_home():
    m=json.loads(strict_file(ROOT/"topics/topic-manifest.json"))
    cards=[card for card in m["topics"] if card["row"]=="ZM-R25"]
    paths={}
    for c in cards:
        hit=PATTERN.fullmatch(c["path"])
        if not hit: die("unexpected destination "+c["path"])
        slug=hit.group(1)
        if slug in paths: die("duplicate topic slug "+slug)
        paths[slug]=ROOT/("topics/zm-r25/"+slug+"/index.html")
    if set(paths)!=EXPECTED: die("topic manifest differs from approved 21 cards: "+str(set(paths)^EXPECTED))
    home=strict_file(ROOT/"index.html")
    found=HOME_MANIFEST.search(home)
    if not found:die("root carousel manifest absent; site may have changed")
    orbit=json.loads(found.group(1))
    rows=[row for row in orbit["rows"] if row["id"]=="ZM-R25"]
    if len(rows)!=1:die("IT row count changed")
    urls=[card.get("canonicalUrl") for card in rows[0]["cards"]]
    permitted=set(c["path"] for c in cards)|{"/farm-wars/"}
    unexpected=set(urls)-permitted
    if unexpected:die("new IT card without its own approved product: "+str(unexpected))
    if len(urls)!=22 or len(set(urls))!=22 or set(urls)!=permitted:
        die("expected 21 specialist cards plus standalone Farm Dominion card")
    return paths,home

def payload(stage):
    src=strict_file(stage/"index.html")
    if b"__PRODUCT_DATA__" in src or b"ZOMOROD DIGITAL LAB" not in src:die("invalid product source")
    j=re.search(rb'<script id="catalog" type="application/json">(.*?)</script>',src,re.S)
    if not j:die("product catalog not found")
    cats=json.loads(j.group(1))
    actual={c["slug"] for c in cats}
    if actual!=EXPECTED or len(cats)!=21:die("product catalog mismatch")
    return src

def insert(old,slug,title):
    if b"</main>" not in old.lower():die("page has no main element: "+slug)
    if PREFIX.encode() in old:die("already modified: "+slug)
    url="/digital-lab/?tool="+slug
    block=("""
<!-- %s:%s:BEGIN -->
<section class="zm-product-in-page" id="zm-product-%s" aria-label="محصول کاربردی %s"
 style="margin:34px auto;padding:clamp(14px,2vw,28px);border-radius:23px;border:1px solid rgba(239,210,131,.56);
 background:linear-gradient(145deg,rgba(16,48,37,.96),rgba(10,33,27,.97));box-shadow:0 14px 32px #0005;color:#eff6e8;direction:rtl">
<h2 style="color:#efd393;font-size:clamp(20px,3vw,29px)">محصول دیجیتال کاربردی: %s</h2>
<p style="line-height:1.9">ابزار تعاملی این حوزه در همین صفحه قابل استفاده است؛ محاسبه، برنامه‌ریزی و دریافت گزارش بدون ارسال داده به سرور.</p>
<iframe title="محصول تعاملی %s" src="%s" loading="lazy" referrerpolicy="strict-origin-when-cross-origin"
 sandbox="allow-scripts allow-downloads" style="display:block;width:100%%;min-height:740px;height:min(94svh,1020px);
 border:1px solid #c9d9b766;border-radius:17px;background:#102d25" ></iframe>
<p><a href="%s" target="_blank" rel="noopener" style="color:#ffdf97">بازکردن محصول در صفحه مستقل ↗</a></p>
</section>
<!-- %s:%s:END -->
""" % (PREFIX,slug,slug,html.escape(title,quote=True),html.escape(title),html.escape(title),url,url,PREFIX,slug)).encode("utf-8")
    lower=old.lower()
    pos=lower.find(b"</main>")
    return old[:pos]+block+old[pos:]

def atomic_write(path,data):
    if path.is_symlink():die("unsafe symlink at "+str(path))
    temp=path.with_name(path.name+".zm-products-temp")
    if temp.exists() or temp.is_symlink():die("temporary destination already exists")
    perm=stat.S_IMODE(path.stat().st_mode)
    with temp.open("xb") as f:
        f.write(data);f.flush();os.fsync(f.fileno())
    os.chmod(temp,perm)
    os.replace(temp,path)

def paths_from_saved(state):
    return {slug:ROOT/("topics/zm-r25/"+slug+"/index.html") for slug in state["slugs"]}

def prepare(stage):
    paths,home=manifest_and_home()
    src=payload(stage)
    target=ROOT/"digital-lab"
    if target.exists() or target.is_symlink():die("digital-lab route already exists; refuse to overwrite")
    immutable=[ROOT/"index.html",ROOT/".htaccess",ROOT/"farm-wars/index.html",
               ROOT/"topics/zm-r25/game-development/index.html"]
    for p in immutable:strict_file(p)
    backup=stage/"backup"
    if backup.exists():die("backup stage already initialized")
    backup.mkdir(mode=0o700)
    pages={}
    titles={c["path"].split("/")[-2]:c["title"] for c in json.loads(strict_file(ROOT/"topics/topic-manifest.json"))["topics"] if c["row"]=="ZM-R25"}
    for slug,p in sorted(paths.items()):
        old=strict_file(p)
        if PREFIX.encode() in old:die("marker already present in "+slug)
        new=insert(old,slug,titles[slug])
        (backup/(slug+".html")).write_bytes(old)
        pages[slug]={"original_sha":digest(old),"new_sha":digest(new),"title":titles[slug]}
    state={"slugs":sorted(paths),"pages":pages,
           "immutable":{str(p):digest(strict_file(p)) for p in immutable},
           "app_sha":digest(src),"version":PREFIX}
    (stage/"state.json").write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding="utf-8")
    print("IT_PRODUCTS_PREPARE=PASS count="+str(len(paths)),flush=True)

def load_state(stage):
    s=json.loads(strict_file(stage/"state.json"))
    if s["version"]!=PREFIX or set(s["slugs"])!=EXPECTED:die("unexpected state")
    return s

def rollback(stage):
    state=load_state(stage)
    total=0
    for slug,p in paths_from_saved(state).items():
        before=strict_file(stage/"backup"/(slug+".html"))
        current=strict_file(p)
        old_hash=state["pages"][slug]["original_sha"]
        new_hash=state["pages"][slug]["new_sha"]
        if digest(before)!=old_hash:die("backup digest changed "+slug)
        if digest(current)==new_hash:
            atomic_write(p,before)
            total+=1
        elif digest(current)!=old_hash:
            die("external concurrent edit; refusing destructive rollback on "+slug)
    route=ROOT/"digital-lab"
    if route.exists() or route.is_symlink():
        if route.is_symlink() or not route.is_dir():die("unsafe new product route")
        if set(p.name for p in route.iterdir())!={"index.html",".htaccess"}:die("non-owned product directory")
        if digest(strict_file(route/"index.html"))!=state["app_sha"]:die("app changed concurrently")
        (route/"index.html").unlink();(route/".htaccess").unlink();route.rmdir()
    print("IT_PRODUCTS_ROLLBACK=PASS restored="+str(total),flush=True)

def install(stage):
    state=load_state(stage)
    for p,sha in state["immutable"].items():
        if digest(strict_file(Path(p)))!=sha:die("protected file changed before install "+p)
    payload_bytes=payload(stage)
    folder=stage/"digital-lab-staged"
    folder.mkdir(mode=0o755)
    (folder/"index.html").write_bytes(payload_bytes)
    (folder/".htaccess").write_text("PassengerEnabled off\nDirectoryIndex index.html\nOptions -Indexes\n",encoding="ascii")
    (folder/"index.html").chmod(0o644)
    (folder/".htaccess").chmod(0o644)
    try:
        folder.rename(ROOT/"digital-lab")
        for slug,p in paths_from_saved(state).items():
            old=strict_file(p)
            if digest(old)!=state["pages"][slug]["original_sha"]:
                die("concurrent page modification "+slug)
            new=insert(old,slug,state["pages"][slug]["title"])
            if digest(new)!=state["pages"][slug]["new_sha"]:die("unexpected insertion delta")
            atomic_write(p,new)
    except BaseException:
        rollback(stage)
        raise
    print("IT_PRODUCTS_INSTALLED=PASS count=21 + retained game",flush=True)

def verify(stage):
    state=load_state(stage)
    assert digest(strict_file(ROOT/"digital-lab/index.html"))==state["app_sha"]
    for slug,p in paths_from_saved(state).items():
        if digest(strict_file(p))!=state["pages"][slug]["new_sha"]:die("page live hash mismatch "+slug)
        data=strict_file(p)
        if data.count((PREFIX+":"+slug+":BEGIN").encode())!=1 or ("/digital-lab/?tool="+slug).encode() not in data:
            die("product embed invalid "+slug)
    for p,sha in state["immutable"].items():
        # The original game-development page is intentionally modified by this operation.
        if p.endswith("/topics/zm-r25/game-development/index.html"):continue
        if digest(strict_file(Path(p)))!=sha:die("protected document changed "+p)
    print("IT_PRODUCTS_VERIFIED=PASS 21 unique + existing farm game",flush=True)

def cleanup(stage):
    state=load_state(stage)
    verify(stage)
    shutil.rmtree(stage/"backup")
    (stage/"state.json").unlink()
    (stage/"index.html").unlink()
    (stage/"installer.py").unlink()
    stage.rmdir()
    print("IT_PRODUCTS_STAGE_REMOVED=PASS",flush=True)

def main():
    if len(sys.argv)!=3:die("usage: installer.py COMMAND RUN_ID")
    command,run_id=sys.argv[1:]
    if command not in {"prepare","install","verify","rollback","cleanup"}:die("unknown command")
    stage=stage_for(run_id)
    globals()[command](stage)

if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("IT_PRODUCTS_ERROR="+repr(exc),file=sys.stderr,flush=True)
        raise
