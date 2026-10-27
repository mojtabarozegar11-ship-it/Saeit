#!/usr/bin/env python3
"""Scoped MojPlayWin main-page architecture correction. No child sites or commerce."""
import hashlib
import html
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile

ROOT = Path("/home/zomorod2/mojplaywin.com")
SOURCE_DIR = ROOT / "design-preview-20261017/mpw-ten-editorials-20261018/pages"
DEST_DIR = ROOT / "mpw-editorial/collections"
BACKUP_DIR = Path("/home/zomorod2/.mpw-architecture-backups")
MARKER = 'data-mpw-content-architecture="20261027"'
# 2026-10-27 read-only SSH audit, SHA-256 prefix guard.
BASELINES = {
    "about": "86a860a79e0ad626",
    "ventures-hospitality": "dd75c5d91959843e",
    "agents": "e76dcb264700eb6d",
    "ventures-agriculture": "b5704c3d24e850b6",
    "ventures-jewelry-gold": "1a25550681e48d60",
    "industry": "10ae93328bb4850f",
    "ventures-ecommerce": "1e55501d06a16dcb",
    "services": "c247de125b5aba19",
    "research": "9e4edaecde92009c",
    "ventures-currency-crypto": "ddca9ba861f17cfd",
    "ventures-carpets": "914fcc4d85e56b9f",
    "company": "74a60efe2c70d8d2",
    "studio": "0cca041727839664",
    "ventures-cafe-restaurant": "11bbb35bf48b93a2",
    "knowledge": "afb2d4abab0c365c",
    "ventures-fuel-station": "14fbe8432e7721fc",
    "economy": "1295ce1fe9ecc304",
    "market": "255c90db399cd3eb",
}
# Deliberately excludes about-mojtaba-rozegar.html and all personal microsites.

def checksum(data):
    return hashlib.sha256(data).hexdigest()

def source_path(slug):
    return SOURCE_DIR / (slug + ".html")

def public_route(slug):
    return ("/ventures/" + slug[len("ventures-"):] + "/") if slug.startswith("ventures-") else "/" + slug + "/"

def archive_route(slug):
    return "/mpw-editorial/collections/" + slug + "/index.html"

def section_span(s, needle):
    pos = s.find(needle)
    if pos == -1 or s.find(needle, pos + len(needle)) != -1:
        raise ValueError("Missing or ambiguous section: " + needle)
    start = s.rfind("<section", 0, pos)
    if start < 0 or pos - start > 250:
        raise ValueError("Section anchor not in section opening: " + needle)
    depth = 0
    for m in re.finditer(r"</?section\b[^>]*>", s[start:], re.I):
        tag = m.group()
        depth += -1 if tag.lstrip().startswith("</") else 1
        if depth == 0:
            return (start, start + m.end())
        if depth < 0:
            raise ValueError("Malformed section nesting")
    raise ValueError("Unclosed " + needle)

def page_title(s, slug):
    m = re.search(r"<h1\b[^>]*>(.*?)</h1>", s, re.I | re.S)
    if m:
        val = html.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
        if val: return re.sub(r"\s+", " ", val)[:120]
    return slug.replace("-", " ").title()

def render_archive(original, slug, visual_html, research_html):
    title = page_title(original, slug)
    title_html = html.escape(title)
    styles = "\n".join(re.findall(r"<style\b[^>]*>.*?</style\s*>", original, re.I | re.S))
    # Reuse source CSS, but not source scripts, canonical, forms or mixed checkout.
    origin = public_route(slug)
    canonical = "https://mojplaywin.com" + archive_route(slug)
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Illustrated guides and research | {title_html} | MojPlayWin</title>
<meta name="description" content="Original illustrated field guides and research analyses for {title_html}; an organized MojPlayWin knowledge collection.">
<link rel="canonical" href="{canonical}">
{styles}
<style>
:root{{color-scheme:dark}}
body{{margin:0;background:#0b1014;color:#f1e8db;font-family:Inter,system-ui,-apple-system,Segoe UI,sans-serif;line-height:1.65}}
.mpw-archive-wrap{{max-width:1240px;margin:auto;padding:28px clamp(16px,4vw,54px) 90px}}
.mpw-archive-nav{{display:flex;flex-wrap:wrap;gap:13px;align-items:center;padding:14px 0 30px;border-bottom:1px solid #8e764b}}
.mpw-archive-nav a{{color:#e8bd6a;text-underline-offset:4px}}
.mpw-archive-title{{margin:38px 0;padding:28px;border:1px solid #645332;border-radius:20px;background:linear-gradient(115deg,#1b2229,#2a2119)}}
.mpw-archive-title h1{{color:#ffe0a2;font-size:clamp(1.7rem,4vw,3rem);margin:4px 0 15px;line-height:1.16}}
.mpw-archive-title p{{max-width:74ch}}
.mpw-archive-wrap section{{max-width:100%;box-sizing:border-box}}
.mpw-archive-foot{{padding:25px;border-top:1px solid #645332;text-align:center;color:#dfd1b7}}
.mpw-archive-foot a{{color:#e8bd6a}}
a:focus-visible{{outline:3px solid #f2cf7d;outline-offset:4px}}
</style>
</head>
<body {MARKER}>
<main id="main-content" class="mpw-archive-wrap">
<nav class="mpw-archive-nav" aria-label="Navigation"><strong>MojPlayWin</strong><a href="/">Home</a><a href="/knowledge/">Knowledge</a><a href="/research/">Research</a><a href="{origin}">Back to {title_html}</a></nav>
<header class="mpw-archive-title">
<p>MOJPLAYWIN / EDITORIAL COLLECTION</p><h1>Insights and illustrated guides: {title_html}</h1>
<p>This specialist collection preserves the complete illustrated notes and research briefs for this topic. The primary page presents services and navigation, while long-form reading is organized here.</p>
</header>
{visual_html}
{research_html}
</main>
<footer class="mpw-archive-foot">MojPlayWin · <a href="{origin}">Return to {title_html}</a> · <a href="/knowledge/">Knowledge library</a></footer>
</body></html>
""".encode("utf-8")

def render_summary(slug, title):
    title_html = html.escape(title)
    url = archive_route(slug)
    return f"""
<style {MARKER}>
.mpw-collection-linkout{{margin:clamp(25px,4vw,52px) auto;padding:clamp(18px,3vw,32px);border:1px solid #847049;border-radius:18px;background:linear-gradient(135deg,#1e262c,#241c16);color:#f5e8d2;max-width:1180px}}
.mpw-collection-linkout h2{{color:#f4cd83;font-size:clamp(1.25rem,2.3vw,1.8rem);margin:0 0 10px}}
.mpw-collection-linkout p{{max-width:76ch;margin-bottom:18px}}
.mpw-collection-linkout .mpw-collection-actions{{display:flex;gap:12px;flex-wrap:wrap}}
.mpw-collection-linkout a{{display:inline-block;padding:10px 15px;border:1px solid #b89a5b;border-radius:10px;color:#ffdb98;text-decoration:none;font-weight:700}}
.mpw-collection-linkout a:hover,.mpw-collection-linkout a:focus-visible{{background:#604b2d;color:white}}
</style>
<section class="mpw-collection-linkout" {MARKER} aria-label="Extended subject reading">
<h2>Specialist guides and research</h2>
<p>The complete illustrated field notes and research analyses for {title_html} have a dedicated reading library, keeping this overview focused and easy to navigate.</p>
<div class="mpw-collection-actions"><a href="{url}#mpw-ten-illustrated-20261018">Illustrated guides</a><a href="{url}">Research collection</a></div>
</section>
"""

def transform(original, slug):
    if MARKER in original:
        raise ValueError("Already patched source: " + slug)
    ten = section_span(original, 'id="mpw-ten-illustrated-20261018"')
    research = section_span(original, 'id="mpw-research-editorials-20261019-')
    if ten[1] > research[0]:
        raise ValueError("Unexpected section order: " + slug)
    visual = original[ten[0]:ten[1]]
    papers = original[research[0]:research[1]]
    if "mpw-ten-heading" not in visual or "mpw-r30" not in papers:
        raise ValueError("Missing archive sections: " + slug)
    archive = render_archive(original, slug, visual, papers)
    # Remove only identified complete sections; do not drop their content from archives.
    updated = original[:research[0]] + original[research[1]:]
    updated = updated[:ten[0]] + updated[ten[1]:]
    main_end = re.search(r"</main\s*>", updated, re.I)
    footer = re.search(r"<footer\b[^>]*>.*?</footer\s*>", updated, re.I | re.S)
    if not main_end or not footer:
        raise ValueError("Missing semantic landmark: " + slug)
    if footer.start() < main_end.start():
        block = footer.group()
        updated = updated[:footer.start()] + updated[footer.end():]
        close = re.search(r"</main\s*>", updated, re.I)
        updated = updated[:close.end()] + "\n" + block + updated[close.end():]
    # Short, scoped library signpost within main, before the closing main tag.
    close = re.search(r"</main\s*>", updated, re.I)
    updated = updated[:close.start()] + render_summary(slug, page_title(original, slug)) + updated[close.start():]
    main_end = re.search(r"</main\s*>", updated, re.I)
    footer = re.search(r"<footer\b[^>]*>.*?</footer\s*>", updated, re.I | re.S)
    if not main_end or not footer or main_end.end() > footer.start():
        raise ValueError("Footer still inside main: " + slug)
    if updated.count(MARKER) != 2:
        raise ValueError("Incorrect archive signpost count: " + slug)
    if ('id="mpw-ten-illustrated-20261018"' in updated or
        'id="mpw-research-editorials-20261019-' in updated):
        raise ValueError("Long-form sections still embedded: " + slug)
    if 'id="mpw-ten-illustrated-20261018"' not in archive.decode() or \
       'id="mpw-research-editorials-20261019-' not in archive.decode():
        raise ValueError("Archive lost sections: " + slug)
    return updated.encode("utf-8"), archive

def prepare():
    pairs = {}
    for slug, prefix in BASELINES.items():
        path = source_path(slug)
        if path.is_symlink() or not path.is_file():
            raise ValueError("Invalid exact source path " + str(path))
        data = path.read_bytes()
        digest = checksum(data)
        if not digest.startswith(prefix):
            raise ValueError(f"Changed source {slug}: {digest[:16]} expected {prefix}")
        dest = DEST_DIR / slug / "index.html"
        if dest.exists() or dest.is_symlink():
            raise ValueError("Archive path already exists: " + str(dest))
        updated, archive = transform(data.decode("utf-8"), slug)
        if len(archive) < 7000:
            raise ValueError("Archive suspiciously small: " + slug)
        pairs[slug] = {"path":path,"dest":dest,"before":data,"after":updated,"archive":archive}
    return pairs

def write_atomic(path, data, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".mpw-arch-", dir=path.parent)
    try:
        os.chmod(tmp, mode)
        with os.fdopen(fd, "wb") as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def safe_rollback(backup, manifest):
    for slug, rec in reversed(list(manifest.items())):
        source = source_path(slug)
        archive = DEST_DIR / slug / "index.html"
        old = backup / (slug + ".html")
        if source.is_file() and checksum(source.read_bytes()) == rec["after"] and old.is_file():
            write_atomic(source, old.read_bytes(),rec["mode"])
            print("ROLLBACK_SOURCE",slug)
        if archive.is_file() and checksum(archive.read_bytes()) == rec["archive"]:
            archive.unlink()
            print("ROLLBACK_ARCHIVE",slug)

def publish(run_id):
    pairs = prepare()
    backup = BACKUP_DIR / ("main-architecture-" + run_id)
    if backup.exists():
        raise RuntimeError("Backup collision")
    backup.mkdir(parents=True, mode=0o700)
    backup.chmod(0o700)
    manifest = {}
    try:
        for slug, p in pairs.items():
            source, archive = p["path"],p["dest"]
            mode = stat.S_IMODE(source.stat().st_mode)
            write_atomic(backup / (slug + ".html"),p["before"],0o600)
            manifest[slug] = {
                "before":checksum(p["before"]),
                "after":checksum(p["after"]),
                "archive":checksum(p["archive"]),
                "mode":mode}
        write_atomic(backup / "manifest.json",json.dumps(manifest,sort_keys=True,indent=2).encode(),0o600)
        # Recheck all input content before beginning the release.
        for slug,p in pairs.items():
            if checksum(p["path"].read_bytes()) != checksum(p["before"]):
                raise RuntimeError("Source changed during preflight: " + slug)
        for slug,p in pairs.items():
            write_atomic(p["dest"],p["archive"])
            write_atomic(p["path"],p["after"],manifest[slug]["mode"])
            print("PUBLISHED_ARCHITECTURE",slug,public_route(slug),archive_route(slug))
    except Exception:
        safe_rollback(backup,manifest)
        raise
    print("MPW_ARCHITECTURE_COMPLETE",len(pairs),"BACKUP",str(backup))

def rollback(run_id):
    backup = BACKUP_DIR / ("main-architecture-" + run_id)
    manifest_file = backup / "manifest.json"
    if not manifest_file.is_file():
        raise RuntimeError("No matching guarded manifest")
    manifest = json.loads(manifest_file.read_text())
    safe_rollback(backup,manifest)
    print("MPW_ARCHITECTURE_ROLLBACK_COMPLETE")

def main():
    mode = sys.argv[1] if len(sys.argv)>1 else "preflight"
    if mode=="selftest":
        for footer_inside in (True,False):
            head="<html><head><title>A</title><style>.mpw-ten-illustrated{color:red}</style></head><body><main><h1>Demo</h1>"
            a='<section id="mpw-ten-illustrated-20261018"><h2 id="mpw-ten-heading-demo">Guides</h2><article><section>nested</section></article></section>'
            b='<section id="mpw-research-editorials-20261019-demo"><p class="mpw-r30">Paper</p></section>'
            footer="<footer>Foot</footer>"
            s=head+(footer if footer_inside else "")+a+b+"</main>"+("" if footer_inside else footer)+"</body></html>"
            patched,archive=transform(s,"demo")
            assert patched.find(b"</main>") < patched.find(b"<footer")
            assert archive.count(b"<section")>=3
        print("ARCHITECTURE_SELFTEST_OK")
    elif mode=="preflight":
        pairs=prepare()
        print("ARCHITECTURE_PREFLIGHT_OK",len(pairs),"sources",sum(len(p["before"]) for p in pairs.values()),"archives",sum(len(p["archive"]) for p in pairs.values()))
    elif mode=="publish":
        publish(sys.argv[2])
    elif mode=="rollback":
        rollback(sys.argv[2])
    else:
        raise ValueError("Unknown mode")

if __name__=="__main__":main()
