#!/usr/bin/env python3
"""Make the existing 21 live products visible directly below the linked-page H1.
Only moves the previously installed, tagged product section. Transactional and reversible.
Never touches the root homepage, topic manifest, other rows, or Farm Dominion.
"""
from __future__ import annotations
import hashlib, json, os, re, shutil, stat, sys
from pathlib import Path

ROOT = Path("/home/zomorod2/public_html")
MARKER = "ZM-IT-PRODUCT-20261019"
VISIBLE = "ZM-R25-VISIBLE-20261019"
SLUGS = {
 "website-design","software-development","mobile-app-development","ux-design",
 "applied-ai","business-automation","data-analytics","cloud-infrastructure",
 "cybersecurity","ecommerce","digital-products","game-development",
 "digital-animation","professional-content","seo","tech-project-management",
 "api-engineering","backup-recovery","digital-training","software-qa",
 "live-878f27b75f2daa",
}
def fail(s): raise RuntimeError(s)
def sha(b): return hashlib.sha256(b).hexdigest()
def read(p):
    if p.is_symlink() or not p.is_file(): fail("unsafe or absent file: "+str(p))
    return p.read_bytes()
def stage_dir(ident):
    if not re.fullmatch(r"[0-9]{4,20}",ident): fail("invalid run ID")
    path=Path("/home/zomorod2")/(".zm-r25-visibility-"+ident)
    if path.is_symlink() or not path.is_dir(): fail("stage missing or unsafe")
    return path
def catalog():
    obj=json.loads(read(ROOT/"topics/topic-manifest.json"))
    cards=[c for c in obj["topics"] if c.get("row")=="ZM-R25"]
    slugs={c["path"].split("/")[-2] for c in cards}
    if len(cards)!=21 or slugs!=SLUGS: fail("unexpected topic manifest or count")
    return {s:ROOT/"topics"/"zm-r25"/s/"index.html" for s in slugs}
def transform(data,slug):
    begin=("<!-- "+MARKER+":"+slug+":BEGIN -->").encode()
    end=("<!-- "+MARKER+":"+slug+":END -->").encode()
    if data.count(begin)!=1 or data.count(end)!=1:fail("tagged original product absent or duplicated: "+slug)
    if VISIBLE.encode() in data: fail("already surfaced: "+slug)
    a=data.index(begin);b=data.index(end,a)+len(end)
    block=data[a:b]
    expected=("/digital-lab/?tool="+slug).encode()
    if expected not in block or b"<iframe" not in block:fail("linked current product missing: "+slug)
    base=data[:a]+data[b:]
    main=re.search(rb"<main\b[^>]*>",base,re.I)
    if not main:fail("main tag missing: "+slug)
    h1=re.search(rb"<h1\b[^>]*>[\s\S]*?</h1\s*>",base[main.end():],re.I)
    if not h1:fail("h1 tag missing: "+slug)
    pos=main.end()+h1.end()
    if pos>a:fail("original product unexpectedly already above title: "+slug)
    # Make the product load immediately and ensure a highly visible, direct open link
    # even when a browser extension prevents iframes/scripts from displaying.
    block=block.replace(b'loading="lazy"',b'loading="eager"',1)
    launch=('''\n<!-- '''+VISIBLE+''':START -->
<div data-zm-r25-visible="'''+slug+'''" style="padding:10px 0 16px;direction:rtl">
<a href="/digital-lab/?tool='''+slug+'''" target="_self" style="display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:48px;padding:11px 24px;font-weight:800;text-decoration:none;color:#102820;background:linear-gradient(115deg,#ffe29e,#dcb670);border-radius:13px;border:1px solid #ffeac0;box-shadow:0 8px 20px #0005">▶ اجرای محصول دیجیتال و دریافت گزارش</a>
</div>
<!-- '''+VISIBLE+''':END -->
''').encode("utf-8")
    point=block.find(b"<iframe")
    if point<0:fail("iframe missing: "+slug)
    block=block[:point]+launch+block[point:]
    new=base[:pos]+b"\n"+block+b"\n"+base[pos:]
    if len(new)-len(data)!=len(launch)+2:fail("unexpected mutation size: "+slug)
    return new
def atomic(p,b):
    if p.is_symlink():fail("symlink destination")
    tmp=p.with_name(p.name+"."+VISIBLE+".tmp")
    if tmp.exists() or tmp.is_symlink():fail("temp file exists")
    mode=stat.S_IMODE(p.stat().st_mode)
    with tmp.open("xb") as fd: fd.write(b);fd.flush();os.fsync(fd.fileno())
    tmp.chmod(mode);os.replace(tmp,p)
def state(stage):
    obj=json.loads(read(stage/"state.json"))
    if set(obj["pages"])!=SLUGS or obj["version"]!=VISIBLE:fail("state invalid")
    return obj
def prepare(stage):
    pages=catalog()
    if (stage/"state.json").exists():fail("stage already prepared")
    backup=stage/"backups"
    backup.mkdir(mode=0o700)
    obj={"version":VISIBLE,"pages":{},"protected":{}}
    for name in ("index.html","topics/topic-manifest.json","farm-wars/index.html"):
        p=ROOT/name
        obj["protected"][name]=sha(read(p))
    for slug,p in sorted(pages.items()):
        old=read(p);new=transform(old,slug)
        (backup/(slug+".html")).write_bytes(old)
        obj["pages"][slug]={"old":sha(old),"new":sha(new)}
    (stage/"state.json").write_text(json.dumps(obj,indent=2,ensure_ascii=False))
    print("R25_VISIBLE_PREPARE=PASS count=21",flush=True)
def rollback(stage):
    obj=state(stage);pages=catalog();count=0
    for slug,p in sorted(pages.items()):
        original=read(stage/"backups"/(slug+".html"))
        current=read(p)
        a=obj["pages"][slug]
        if sha(original)!=a["old"]:fail("backup corruption: "+slug)
        if sha(current)==a["new"]:
            atomic(p,original);count+=1
        elif sha(current)!=a["old"]:fail("refusing to undo external edit: "+slug)
    print("R25_VISIBLE_ROLLBACK=PASS restored="+str(count),flush=True)
def install(stage):
    obj=state(stage);pages=catalog()
    try:
        for slug,p in sorted(pages.items()):
            old=read(p)
            if sha(old)!=obj["pages"][slug]["old"]:fail("concurrent change: "+slug)
            new=transform(old,slug)
            if sha(new)!=obj["pages"][slug]["new"]:fail("hash mismatch: "+slug)
            atomic(p,new)
    except BaseException:
        rollback(stage);raise
    print("R25_VISIBLE_INSTALL=PASS count=21",flush=True)
def verify(stage):
    obj=state(stage);pages=catalog()
    for slug,p in sorted(pages.items()):
        data=read(p)
        if sha(data)!=obj["pages"][slug]["new"]:fail("unexpected content: "+slug)
        marker=(VISIBLE+":START").encode()
        if data.count(marker)!=1:fail("missing visible CTA: "+slug)
        if data.index(marker)>data.index(b"</main>") or data.index(marker)>data.index(b"<h2"):
            fail("product not prominent: "+slug)
        if ("/digital-lab/?tool="+slug).encode() not in data:fail("product URL incorrect: "+slug)
    for name,h in obj["protected"].items():
        if sha(read(ROOT/name))!=h:fail("protected file changed: "+name)
    print("R25_VISIBLE_VERIFY=PASS 21 product panels near top; site and game preserved",flush=True)
def cleanup(stage):
    verify(stage)
    shutil.rmtree(stage)
    print("R25_VISIBLE_CLEANUP=PASS",flush=True)
if __name__=="__main__":
    try:
        if len(sys.argv)!=3 or sys.argv[1] not in ("prepare","install","verify","rollback","cleanup"):
            fail("usage: file.py prepare|install|verify|rollback|cleanup GITHUB_RUN_ID")
        method=sys.argv[1];stage=stage_dir(sys.argv[2])
        globals()[method](stage)
    except Exception as exc:
        print("R25_VISIBLE_ERROR="+repr(exc),file=sys.stderr,flush=True)
        raise
