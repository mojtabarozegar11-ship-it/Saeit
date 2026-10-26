#!/usr/bin/env python3
"""Owned-file, backup-first, fail-closed MojPlayWin 12-offer release; unrelated sites and payments remain untouched."""
import hashlib, io, json, os, re, shutil, sys, tarfile
from pathlib import Path

ROOT=Path("/home/zomorod2/mojplaywin.com/mpw-editorial")
HOME=Path("/home/zomorod2")
SLUGS=("website-doctor","landing-page-studio","ai-automation","business-spreadsheets","website-templates","social-media-kits","resume-builder","logo-studio","browser-games","marketing-ai","business-calculators","website-care")
HTML=("index.html",)+tuple(slug+"/index.html" for slug in SLUGS)
OLD=set(HTML)|{"catalog.json","sitemap.xml","assets/style.css","assets/tools-v1.js","assets/tools-v1.css"}
NEW=OLD|{"inquiry.php","metrics.php"}
SOURCES={"earn/"+p:p for p in HTML+("catalog.json","sitemap.xml","assets/style.css","inquiry.php","metrics.php")}
SOURCES.update({"toolkit.js":"assets/tools-v1.js","toolkit.css":"assets/tools-v1.css"})
def fail(message): raise RuntimeError(message)
def digest(blob):return hashlib.sha256(blob).hexdigest()
def guard():
    if ROOT.is_symlink() or not ROOT.is_dir() or ROOT.resolve()!=ROOT or ROOT.name!="mpw-editorial" or not (ROOT/"index.html").is_file() or not (ROOT.parent/".htaccess").is_file():fail("Unexpected editorial root")
    target=ROOT/"revenue"
    if not target.is_dir() or target.is_symlink() or target.resolve()!=target:fail("Unexpected revenue target")
    return target
def paths(run):
    if not re.fullmatch("[0-9]{8,20}",run):fail("Invalid release ID")
    return ROOT/(".revenue-upgrade-stage-"+run),HOME/(".mpw-revenue-commercial-backup-"+run)
def read_marker(path):
    if not path.is_file() or path.is_symlink():fail("Owned-release marker absent")
    marker=json.loads(path.read_text("utf-8"))
    if not isinstance(marker,dict) or not isinstance(marker.get("sha256"),dict):fail("Invalid ownership manifest")
    checks=marker["sha256"]
    if set(checks)!=OLD:fail("Pre-upgrade ownership mismatch")
    if any(not isinstance(h,str) or not re.fullmatch("[0-9a-f]{64}",h) for h in checks.values()):fail("Invalid digest")
    return marker
def verify_owned(target,checks):
    for rel,hashval in checks.items():
        p=target/rel
        if not p.is_file() or p.is_symlink() or digest(p.read_bytes())!=hashval:fail("Unowned/concurrently changed path: "+rel)
    if any((target/rel).is_symlink() for rel in NEW):fail("Symlink on managed path")
def archive_docs():
    blob=sys.stdin.buffer.read(1800000)
    if not blob or len(blob)>=1800000:fail("Release archive empty or oversized")
    docs={}
    with tarfile.open(fileobj=io.BytesIO(blob),mode="r:gz") as tar:
        members=tar.getmembers()
        if any(not (m.isfile() or m.isdir()) or m.issym() or m.islnk() for m in members):fail("Unexpected archive entry")
        names={m.name.removeprefix("./") for m in members if m.isfile()}
        if names!=set(SOURCES):fail("Release whitelist mismatch")
        for member in members:
            if not member.isfile():continue
            key=member.name.removeprefix("./")
            if member.size>230000:fail("Oversized release file")
            data=tar.extractfile(member).read()
            if len(data)!=member.size:fail("Archive truncated")
            if key.startswith("earn/"):
                data=data.replace(b"/earn/",b"/mpw-editorial/revenue/")
                routes=[b"/mpw-editorial/revenue/"]+[b"/mpw-editorial/revenue/"+slug.encode()+b"/" for slug in SLUGS]
                for route in sorted(routes,key=len,reverse=True):
                    for tail in (b'"',b"'",b"</loc>"):
                        data=data.replace(route+tail,route+b"index.html"+tail)
            if key.startswith("earn/") and key.endswith("/index.html") and key!="earn/index.html":
                slug=key.split("/")[1]
                if slug not in SLUGS or data.count(b"</head>")!=1 or data.count(b"</main>")!=1 or b'id="mpw-functional-tool"' in data:fail("Unsafe page skeleton")
                stylesheet=b'<link rel="stylesheet" href="/mpw-editorial/revenue/assets/tools-v1.css">'
                section=(
                    '<section class="mpw-tool-section" aria-label="Free browser tool and bespoke service">'
                    '<div id="mpw-functional-tool" data-tool="'+slug+'"></div>'
                    '<script defer src="/mpw-editorial/revenue/assets/tools-v1.js"></script>'
                    '<noscript><p>Enable JavaScript for the browser tool. Secure inquiries remain available without JavaScript.</p></noscript>'
                    '<p><a href="/mpw-editorial/revenue/inquiry.php?service='+slug+'">Send a scoped service request</a> · '
                    '<a href="mailto:support@mojplaywin.com?subject=MojPlayWin%20'+slug+'%20service%20enquiry">Email fallback</a>. Never send credentials.</p>'
                    '</section>'
                ).encode()
                data=data.replace(b"</head>",stylesheet+b"</head>",1).replace(b"</main>",section+b"</main>",1)
                if data.count(b'id="mpw-functional-tool"')!=1:fail("Tool insertion failed")
            if key=="earn/index.html":
                if data.count(b'<section id="offers">')!=1:fail("Hub structure changed")
                note=b'<section aria-label="Tool availability"><h2>12 working free browser utilities</h2><p>Free tools create draft outputs locally in your browser. Bespoke services require a written quotation; no payment is collected on these pages.</p><p><a href="/mpw-editorial/revenue/inquiry.php?service=website-doctor">Request a business quotation</a></p></section>'
                data=data.replace(b'<section id="offers">',note+b'<section id="offers">',1)
            docs[SOURCES[key]]=data
    if set(docs)!=NEW or b'const defs=' not in docs["assets/tools-v1.js"] or b'.mpw-functional-wrap' not in docs["assets/tools-v1.css"]:fail("Incomplete tool bundle")
    if b"<urlset" not in docs["sitemap.xml"]:fail("Sitemap missing")
    if docs["index.html"].count(b"/mpw-editorial/revenue/")<12:fail("Catalog links missing")
    if any(b'data-tool="'+slug.encode()+b'"' not in docs[slug+"/index.html"] for slug in SLUGS):fail("Tool wiring missing")
    if b"store_inquiry" not in docs["inquiry.php"] or b"$events" not in docs["metrics.php"]:fail("Lead endpoint missing")
    return docs
def publish(run):
    target=guard();stage,backup=paths(run)
    if stage.exists() or stage.is_symlink() or backup.exists() or backup.is_symlink():fail("Release ID collision")
    meta=target/".mpw-revenue-release.json"
    old=read_marker(meta)
    verify_owned(target,old["sha256"])
    for rel in NEW-OLD:
        p=target/rel
        if p.exists() or p.is_symlink():fail("Unexpected existing inquiry endpoint")
    docs=archive_docs()
    backup.mkdir(mode=0o700)
    stage.mkdir(mode=0o700)
    new_checks={rel:digest(data) for rel,data in docs.items()}
    done=[]
    try:
        for rel in sorted(OLD):
            src=target/rel; dst=backup/rel
            dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(src,dst)
            if digest(dst.read_bytes())!=old["sha256"][rel]:fail("Backup verification failed")
        shutil.copy2(meta,backup/".mpw-revenue-release.json")
        (backup/".prior-manifest.json").write_text(json.dumps(old,sort_keys=True),encoding="utf-8")
        for rel,data in docs.items():
            p=stage/rel
            p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(data);p.chmod(0o644)
            if digest(p.read_bytes())!=new_checks[rel]:fail("Stage digest mismatch")
        for rel in sorted(NEW):
            dst=target/rel
            if dst.is_symlink() or (rel in OLD and digest(dst.read_bytes())!=old["sha256"][rel]) or (rel not in OLD and dst.exists()):fail("Concurrent release modification")
            os.replace(stage/rel,dst);done.append(rel)
            if digest(dst.read_bytes())!=new_checks[rel]:fail("Post-copy verification failure")
        new_marker={"run":run,"sha256":new_checks,"upgraded_from":old.get("run"),"backup":str(backup)}
        marker_temp=target/(".mpw-revenue-marker-"+run)
        marker_temp.write_text(json.dumps(new_marker,sort_keys=True)+"\n",encoding="utf-8")
        os.replace(marker_temp,meta)
        print("MPW_COMMERCIAL_INTEGRATED_RELEASE="+json.dumps({"run":run,"managed":len(NEW),"prior_backup_preserved":True,"unrelated_site_files_modified":False,"orders_modified":False,"payments_modified":False}))
    except BaseException:
        # Restore only files that are demonstrably from this upgrade; do not erase concurrent customer edits.
        for rel in reversed(done):
            dst=target/rel
            if not dst.is_file() or dst.is_symlink() or digest(dst.read_bytes())!=new_checks[rel]:continue
            if rel in OLD:os.replace(backup/rel,dst)
            else:dst.unlink()
        raise
    finally:
        if stage.exists():shutil.rmtree(stage)
def rollback(run):
    target=guard();stage,backup=paths(run)
    meta=target/".mpw-revenue-release.json"
    if not meta.is_file() or meta.is_symlink():fail("Manifest absent")
    current=json.loads(meta.read_text("utf-8"))
    if current.get("run")!=run or set(current.get("sha256",{}))!=NEW:fail("Refuse rollback over another release")
    if not backup.is_dir() or backup.is_symlink():fail("Original backup missing")
    verify_owned(target,current["sha256"])
    original=read_marker(backup/".mpw-revenue-release.json")
    for rel in sorted(OLD):
        back=backup/rel
        if not back.is_file() or back.is_symlink() or digest(back.read_bytes())!=original["sha256"][rel]:fail("Original backup damaged")
    for rel in sorted(OLD):
        os.replace(backup/rel,target/rel)
    for rel in NEW-OLD:(target/rel).unlink()
    os.replace(backup/".mpw-revenue-release.json",meta)
    print("MPW_COMMERCIAL_ROLLBACK=VERIFIED;ORIGINAL_18_FILES_RESTORED;OTHER_SITES_UNCHANGED")
if __name__=="__main__":
    if len(sys.argv)!=3 or sys.argv[1] not in ("publish","rollback"):raise SystemExit("publish|rollback RUN_ID")
    (publish if sys.argv[1]=="publish" else rollback)(sys.argv[2])
