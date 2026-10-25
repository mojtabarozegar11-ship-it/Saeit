#!/usr/bin/env python3
"""One-time fail-closed recovery of missing MojPlayWin 12 pages and functional tools. Preserves all unrelated sites, orders and protected files."""
import hashlib, io, json, os, re, shutil, stat, sys, tarfile
from pathlib import Path

ROOT=Path("/home/zomorod2/mojplaywin.com/mpw-editorial")
HOME=Path("/home/zomorod2")
SLUGS=['website-doctor','landing-page-studio','ai-automation','business-spreadsheets','website-templates','social-media-kits','resume-builder','logo-studio','browser-games','marketing-ai','business-calculators','website-care']
EXPECTED={"earn/index.html","earn/catalog.json","earn/sitemap.xml","earn/assets/style.css"}
EXPECTED.update("earn/"+slug+"/index.html" for slug in SLUGS)
EXPECTED.update({"toolkit.js","toolkit.css"})
def fail(message): raise RuntimeError(message)
def guard():
    if ROOT.is_symlink() or not ROOT.is_dir() or ROOT.resolve()!=ROOT or ROOT.name!="mpw-editorial" or not (ROOT/"index.html").is_file() or not (ROOT.parent/".htaccess").is_file():fail("Unexpected editorial static root")
    if (ROOT/"revenue").is_symlink():fail("Symlinked revenue path")
def paths(run):
    if not re.fullmatch(r"[0-9]{8,20}",run):fail("Invalid release ID")
    return ROOT/"revenue", ROOT/(".revenue-stage-"+run), HOME/(".mpw-revenue-backup-"+run)
def sha(b):return hashlib.sha256(b).hexdigest()
def safe_tree(path):
    if path.is_symlink():fail("Symlinked directory")
    if path.exists():
        for d, dirs, files in os.walk(path,followlinks=False):
            for name in dirs+files:
                if (Path(d)/name).is_symlink():fail("Unexpected symlink in managed earn tree")
def publish(run):
    guard()
    target,stage,backup=paths(run)
    if stage.exists() or stage.is_symlink() or backup.exists() or backup.is_symlink():fail("Release collision")
    if target.exists():
        safe_tree(target)
        if not target.is_dir():
            fail("Revenue target is not a directory")
        entries=list(target.iterdir())
        placeholder=target/"assets"
        empty_placeholder=(len(entries)==1 and entries[0]==placeholder and
                           placeholder.is_dir() and not placeholder.is_symlink() and not any(placeholder.iterdir()))
        if not ((target/".mpw-revenue-release.json").is_file() or not entries or empty_placeholder):
            fail("Revenue directory holds unknown or unmanaged files; never overwrite")
    data=sys.stdin.buffer.read(1500000)
    if len(data)==1500000 or not data:fail("Release archive too large or empty")
    try:
        tf=tarfile.open(fileobj=io.BytesIO(data),mode="r:gz")
        members=tf.getmembers()
        names={m.name.removeprefix("./") for m in members if m.isfile()}
        if names!=EXPECTED:fail("Manifest whitelist mismatch")
        if any(m.issym() or m.islnk() or not (m.isfile() or m.isdir()) for m in members):fail("Unsafe archive entry")
        docs={}
        for m in members:
            if not m.isfile():continue
            name=m.name.removeprefix("./")
            if m.size>220000:fail("Oversized document")
            payload=tf.extractfile(m).read()
            if len(payload)!=m.size:fail("Archive short read")
            if name in ("toolkit.js","toolkit.css"):
                docs[name]=payload
                continue
            payload=payload.replace(b"/earn/",b"/mpw-editorial/revenue/")
            routes=[b"/mpw-editorial/revenue/"]+[b"/mpw-editorial/revenue/"+slug.encode("ascii")+b"/" for slug in SLUGS]
            for route in sorted(routes,key=len,reverse=True):
                for tail in (b'"',b"'",b"</loc>"):
                    payload=payload.replace(route+tail,route+b"index.html"+tail)
            if name.startswith("earn/") and name.endswith("/index.html") and name != "earn/index.html":
                slug=name.split("/")[1]
                if slug not in SLUGS:fail("Invalid revenue slug")
                if payload.count(b"</head>")!=1 or payload.count(b"</main>")!=1 or b'id="mpw-functional-tool"' in payload:
                    fail("Unexpected page skeleton for "+slug)
                stylesheet=b'<link rel="stylesheet" href="/mpw-editorial/revenue/assets/tools-v1.css">'
                section=(
                    '<section aria-label="Free browser tool and bespoke service">'
                    '<div id="mpw-functional-tool" data-tool="'+slug+'"></div>'
                    '<script defer src="/mpw-editorial/revenue/assets/tools-v1.js"></script>'
                    '<noscript><p>Enable JavaScript to use the free tool. You can still request a service quotation.</p></noscript>'
                    '<p><a href="mailto:support@mojplaywin.com?subject=MojPlayWin%20'+slug+'%20service%20enquiry">Request a tailored quote by email</a>. State your website or project objective, deliverables and deadline; never email credentials.</p>'
                    '</section>'
                ).encode("utf-8")
                payload=payload.replace(b"</head>",stylesheet+b"</head>",1).replace(b"</main>",section+b"</main>",1)
                if payload.count(b'id="mpw-functional-tool"')!=1:fail("Tool injection failed")
            if name=="earn/index.html":
                if payload.count(b'<section id="offers">')!=1:fail("Hub structure changed")
                note=b'<section aria-label="Tool availability"><h2>12 working free browser utilities</h2><p>Free tools create draft outputs in your own browser. Bespoke commercial services require a written scope and quotation; no payment is collected on these pages.</p><p><a href="mailto:support@mojplaywin.com?subject=MojPlayWin%20business%20quote">Request a business quotation</a></p></section>'
                payload=payload.replace(b'<section id="offers">',note+b'<section id="offers">',1)
            docs[name]=payload
    except (tarfile.TarError, OSError, UnicodeError) as exc:fail("Invalid archive: "+type(exc).__name__)
    if b"https://mojplaywin.com/mpw-editorial/revenue/index.html" not in docs["earn/index.html"]:fail("Missing canonical main hub")
    if b'const defs=' not in docs['toolkit.js'] or b'.mpw-functional-wrap' not in docs['toolkit.css']:fail("Invalid browser toolkit files")
    if any(b'id="mpw-functional-tool"' not in docs["earn/"+slug+"/index.html"] for slug in SLUGS):fail("Missing real interactive tool")
    if docs["earn/index.html"].count(b'/mpw-editorial/revenue/')<12:fail("Insufficient catalog links")
    if b"<urlset" not in docs["earn/sitemap.xml"]:fail("Invalid sitemap")
    stage.mkdir(mode=0o755)
    stage.chmod(0o755)
    try:
        checks={}
        for path,body in docs.items():
            rel=Path(path).relative_to("earn") if path.startswith("earn/") else Path("assets")/("tools-v1.js" if path=="toolkit.js" else "tools-v1.css")
            p=stage/rel
            p.parent.mkdir(parents=True,exist_ok=True)
            p.parent.chmod(0o755)
            p.write_bytes(body)
            p.chmod(0o644)
            checks[str(rel)]=sha(body)
        (stage/".mpw-revenue-release.json").write_text(json.dumps({"run":run,"sha256":checks},sort_keys=True)+"\n")
        (stage/".mpw-revenue-release.json").chmod(0o644)
        for rel,digest in checks.items():
            if sha((stage/rel).read_bytes())!=digest:fail("Stage file integrity mismatch")
        had_old=target.exists()
        if had_old:os.replace(target,backup)
        try:os.replace(stage,target)
        except BaseException:
            if had_old and backup.exists():os.replace(backup,target)
            raise
        print("MPW_REVENUE_HUB_PUBLISHED="+json.dumps({"run":run,"files":len(checks),"only_static_earn":True,"payment_flags_modified":False,"old_earn_backed_up":had_old}))
    finally:
        if stage.exists():shutil.rmtree(stage)
def rollback(run):
    guard()
    target,stage,backup=paths(run)
    if not target.is_dir() or target.is_symlink():fail("Missing release target")
    meta=target/".mpw-revenue-release.json"
    if not meta.is_file() or meta.is_symlink():fail("Release ownership marker missing")
    doc=json.loads(meta.read_text())
    if doc.get("run")!=run:fail("Refuse rollback over newer release")
    safe_tree(target)
    for rel,digest in doc["sha256"].items():
        if sha((target/rel).read_bytes())!=digest:fail("Modified target; refuse destructive rollback")
    shutil.rmtree(target)
    if backup.exists():
        if backup.is_symlink():fail("Unsafe backup")
        os.replace(backup,target)
    print("MPW_REVENUE_HUB_ROLLBACK=VERIFIED")
if __name__=="__main__":
    if len(sys.argv)!=3 or sys.argv[1] not in ("publish","rollback"):raise SystemExit("publish|rollback RUN_ID")
    (publish if sys.argv[1]=="publish" else rollback)(sys.argv[2])
