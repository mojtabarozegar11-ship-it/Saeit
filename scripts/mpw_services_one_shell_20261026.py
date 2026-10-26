#!/usr/bin/env python3
"""Unify MojPlayWin services navigation without touching protected sibling apps.

Production targets are exactly one main services document, 13 static revenue
documents, and one new scoped stylesheet. All edits are SHA-guarded and
reversible. Existing service URLs, tools, forms, commerce and personal pages
are left in place.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path("/home/zomorod2/mojplaywin.com")
HOME = ROOT / "design-preview-20261017/production-home-20261017.html"
SERVICES = ROOT / "design-preview-20261017/mpw-ten-editorials-20261018/pages/services.html"
REVENUE = ROOT / "mpw-editorial/revenue"
STYLESHEET = REVENUE / "assets/mpw-one-shell-20261026.css"
SLUGS = (
    "website-doctor", "landing-page-studio", "ai-automation",
    "business-spreadsheets", "website-templates", "social-media-kits",
    "resume-builder", "logo-studio", "browser-games", "marketing-ai",
    "business-calculators", "website-care",
)
LABELS = (
    "Website Doctor", "Landing Page Studio", "AI Workflow Automation",
    "Business Spreadsheet Kits", "Website Templates", "Social Media Kits",
    "Resume Builder", "Logo and Brand Studio", "Browser Games",
    "Marketing AI Workspace", "Business Calculators", "Website Care",
)
MARK = 'data-mpw-one-shell="20261026"'
CSS_LINK = '<link rel="stylesheet" href="/mpw-editorial/revenue/assets/mpw-one-shell-20261026.css">'
MAIN_MARK = 'id="mpw-service-offers-20261026"'
HEADER = re.compile(r'<header\b[^>]*class="mw-site-nav"[^>]*>[\s\S]*?</header>', re.I)
REVENUE_HEADER = re.compile(r'<header><a class="brand" href="/">MojPlayWin</a><nav aria-label="Main navigation">[\s\S]*?</nav></header>')
SERVICES_ANCHOR = '<section class="mpw-page-cta" id="expert-guide"'

CSS = """/* Scoped shell shared by all 12 service detail pages and their catalog. */
.mpw-unified-shell{max-width:1240px;margin:0 auto;display:flex;align-items:center;
 justify-content:space-between;gap:16px;padding:12px 20px;
 background:linear-gradient(115deg,#141610,#090c12);border:1px solid #5c4d31;
 border-radius:0 0 19px 19px;position:relative;z-index:25;isolation:isolate}
.mpw-unified-shell *{box-sizing:border-box}
.mpw-unified-shell .mw-brand{display:flex;align-items:center;gap:11px;flex:0 0 auto;
 text-decoration:none;color:#f2d393;line-height:1.12}
.mpw-unified-shell .mw-brand img{width:48px;height:48px;object-fit:contain}
.mpw-unified-shell .mw-brand-copy{display:flex;flex-direction:column}
.mpw-unified-shell .mw-brand-copy strong{font-size:1.04rem}
.mpw-unified-shell .mw-brand-copy small{color:#cec3ac;font-size:.72rem}
.mpw-unified-shell nav.mw-navigation{display:flex;flex:1;justify-content:flex-end;
 align-items:center;gap:3px;flex-wrap:wrap}
.mpw-unified-shell .mw-navigation>a,.mpw-unified-shell .mw-nav-menu>summary{
 display:inline-flex;align-items:center;min-height:42px;padding:9px 10px;
 font-size:.86rem;font-weight:700;color:#f1ebde;text-decoration:none;
 border-radius:9px;list-style:none;line-height:1.2}
.mpw-unified-shell .mw-navigation>a:hover,.mpw-unified-shell .mw-nav-menu>summary:hover,
.mpw-unified-shell .mw-navigation>a:focus-visible,
.mpw-unified-shell .mw-nav-menu>summary:focus-visible{background:#5a4625;color:#fff;outline:2px solid #dbb975}
.mpw-unified-shell .mw-nav-menu>summary::-webkit-details-marker{display:none}
.mpw-unified-shell .mw-nav-menu>summary:after{content:" ▾";padding-left:4px;color:#e8bf71}
.mpw-unified-shell .mw-nav-panel{position:absolute;right:10px;top:calc(100% + 3px);
 display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;
 width:min(1030px,calc(100vw - 24px));max-height:min(78vh,730px);overflow:auto;
 padding:19px;background:#151921;border:1px solid #9a7b46;border-radius:16px;
 box-shadow:0 24px 70px #000a;z-index:99;text-align:left}
.mpw-unified-shell .mw-nav-panel section{min-width:0;display:flex;flex-direction:column;gap:3px}
.mpw-unified-shell .mw-nav-panel h3{font-size:.92rem;color:#efcb82;margin:0 0 7px}
.mpw-unified-shell .mw-nav-panel a{display:block;padding:5px 6px;color:#e8e1d4;
 text-decoration:none;font-size:.84rem;line-height:1.35;border-radius:6px}
.mpw-unified-shell .mw-nav-panel a:hover,.mpw-unified-shell .mw-nav-panel a:focus-visible{
 background:#3b3426;color:#fff;outline:2px solid #e5bb70}
.mpw-unified-footer-nav{display:flex;flex-wrap:wrap;gap:13px;margin:0 0 15px}
.mpw-unified-footer-nav a{color:#ead3a5;font-weight:700}
.mpw-service-parent-link{font-size:.91rem;margin:0 0 16px}
.mpw-service-parent-link a{font-weight:800}
@media(max-width:1050px){
 .mpw-unified-shell{align-items:flex-start;flex-direction:column}
 .mpw-unified-shell nav.mw-navigation{justify-content:flex-start}
}
@media(max-width:650px){
 .mpw-unified-shell{padding:12px}
 .mpw-unified-shell .mw-navigation>a,.mpw-unified-shell .mw-nav-menu>summary{
   min-height:42px;padding:9px 8px;font-size:.8rem}
 .mpw-unified-shell .mw-nav-panel{grid-template-columns:1fr;left:0;right:0;
  margin:0 auto;width:calc(100vw - 22px);max-height:72vh}
}
@media(prefers-reduced-motion:reduce){.mpw-unified-shell *{scroll-behavior:auto}}
"""

MAIN_STYLE = """<style id="mpw-service-hub-style-20261026">
#mpw-service-offers-20261026{box-sizing:border-box;max-width:1240px;margin:34px auto;
 padding:clamp(18px,3vw,32px);border:1px solid #8e7442;border-radius:22px;
 background:linear-gradient(135deg,#171a17,#10131a);color:#f7f0e4}
#mpw-service-offers-20261026 *{box-sizing:border-box}
#mpw-service-offers-20261026 h2{font-size:clamp(1.55rem,3vw,2.4rem);
 line-height:1.2;color:#efd6a4;margin:8px 0 12px}
#mpw-service-offers-20261026>p{max-width:80ch;color:#d8d1c6;line-height:1.7}
#mpw-service-offers-20261026 .mpw-offer-grid{display:grid;
 grid-template-columns:repeat(3,minmax(0,1fr));gap:13px;margin:20px 0}
#mpw-service-offers-20261026 article{padding:18px;border:1px solid #514634;
 background:#202126;border-radius:14px;min-width:0}
#mpw-service-offers-20261026 h3{font-size:1.05rem;margin:0 0 8px}
#mpw-service-offers-20261026 article a{color:#f4cd80;text-decoration:underline;
 text-underline-offset:3px;display:block;padding:9px 0;min-height:44px}
#mpw-service-offers-20261026 article p{color:#c5c5c4;font-size:.9rem;margin:0}
#mpw-service-offers-20261026 a:focus-visible{outline:3px solid #f6d58d;outline-offset:4px}
@media(max-width:900px){#mpw-service-offers-20261026 .mpw-offer-grid{
 grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:570px){#mpw-service-offers-20261026 .mpw-offer-grid{
 grid-template-columns:1fr}}
</style>"""


def fail(message: str) -> None:
    raise RuntimeError(message)


def sha(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def files() -> list[Path]:
    return [SERVICES, REVENUE / "index.html"] + [
        REVENUE / slug / "index.html" for slug in SLUGS
    ]


def make_header(home_doc: str) -> str:
    matches = list(HEADER.finditer(home_doc))
    if len(matches) != 1:
        fail("Main production homepage header not unambiguous")
    old = matches[0].group(0)
    if (old.count('aria-label="Primary MojPlayWin navigation"') != 1 or
            old.count('href="/services/"') < 1 or
            old.count('data-mpw-earning-directory="v1"') != 1 or
            any(f'/mpw-editorial/revenue/{slug}/index.html' not in old for slug in SLUGS)):
        fail("Official main-site navigation has drifted")
    return old.replace('<header class="mw-site-nav"', '<header class="mw-site-nav mpw-unified-shell" ' + MARK, 1)


def offer_hub() -> str:
    cards = []
    for slug, label in zip(SLUGS, LABELS):
        url = f"/mpw-editorial/revenue/{slug}/index.html"
        cards.append(
            '<article><h3><a href="' + url + '">' + label
            + '</a></h3><p>Standalone details, current availability and the correct enquiry route.</p></article>'
        )
    return (
        '<section ' + MAIN_MARK + ' aria-labelledby="mpw-services-offer-title">'
        '<span class="eyebrow">MOJPLAYWIN / PROFESSIONAL SERVICES</span>'
        '<h2 id="mpw-services-offer-title">Twelve services, each on its own page</h2>'
        '<p>Explore the scope and availability of each offering on its independent page. '
        'Custom engagements use written quotations; proposals and in-development tools are not live checkouts.</p>'
        '<div class="mpw-offer-grid">' + ''.join(cards) + '</div>'
        '<p>For a tailored project, <a href="/mpw-editorial/revenue/inquiry.php?service=general">'
        'request a written quotation</a>. For existing digital products, use the '
        '<a href="/store/">official digital store</a>.</p></section>'
    )


def patch_services(raw: bytes) -> bytes:
    doc = raw.decode("utf-8")
    if MAIN_MARK in doc or 'id="mpw-service-hub-style-20261026"' in doc:
        fail("Services already integrated")
    if doc.count(SERVICES_ANCHOR) != 1 or doc.count("</head>") != 1:
        fail("Active services document no longer matches expected layout")
    main_count = doc.count("<main")
    footer_count = doc.count("<footer")
    out = doc.replace("</head>", MAIN_STYLE + "</head>", 1)
    out = out.replace(SERVICES_ANCHOR, offer_hub() + SERVICES_ANCHOR, 1)
    if (out.count(MAIN_MARK) != 1 or
            any(out.count('/mpw-editorial/revenue/' + slug + '/index.html') < 1 for slug in SLUGS) or
            out.count("<main") != main_count or out.count("<footer") != footer_count):
        fail("Services hub generated an invalid structure")
    return out.encode("utf-8")


def patch_revenue(raw: bytes, header: str, *, slug: str | None) -> bytes:
    doc = raw.decode("utf-8")
    if MARK in doc or CSS_LINK in doc:
        fail("Revenue document already integrated")
    if doc.count("</head>") != 1 or doc.count("<main") != 1 or doc.count("<footer") != 1:
        fail("Revenue document HTML shell changed")
    blocks = list(REVENUE_HEADER.finditer(doc))
    if len(blocks) != 1:
        fail("Unexpected revenue legacy header, refuse replacement")
    before_count = doc.count("</header>")
    doc = doc[:blocks[0].start()] + header + doc[blocks[0].end():]
    doc = doc.replace("</head>", CSS_LINK + "</head>", 1)
    if slug is None:
        target = '<main id="content">'
        if doc.count(target) != 1:
            fail("Revenue hub main location changed")
        notice = ('<p class="mpw-service-parent-link">Official service directory: '
                  '<a href="/services/#mpw-service-offers-20261026">Browse all MojPlayWin services</a>.</p>')
        doc = doc.replace(target, target + notice, 1)
    else:
        target = '<main id="content"><p class="crumb">'
        if doc.count(target) != 1:
            fail("Revenue offer breadcrumb changed " + slug)
        prefix = ('<main id="content"><p class="mpw-service-parent-link">'
                  '<a href="/services/#mpw-service-offers-20261026">MojPlayWin Services</a>'
                  '</p><p class="crumb">')
        doc = doc.replace(target, prefix, 1)
    footer = '<footer>'
    if doc.count(footer) != 1:
        fail("Revenue footer structure changed")
    footer_nav = ('<nav class="mpw-unified-footer-nav" aria-label="MojPlayWin site footer">'
                  '<a href="/">Home</a><a href="/services/">Services</a>'
                  '<a href="/store/">Store</a><a href="/research/">Research</a>'
                  '<a href="/about/">About</a><a href="/contact/">Contact</a></nav>')
    doc = doc.replace(footer, footer + footer_nav, 1)
    if doc.count(MARK) != 1 or doc.count("</header>") != before_count:
        fail("Revenue shell transformation not bounded")
    return doc.encode("utf-8")


def verify_paths() -> None:
    if (ROOT.resolve() != ROOT or ROOT.is_symlink() or
            ROOT.name != "mojplaywin.com" or not ROOT.is_dir()):
        fail("Wrong MojPlayWin document root")
    htaccess = ROOT / ".htaccess"
    if not htaccess.is_file() or htaccess.is_symlink():
        fail("Production route guard missing")
    ht = htaccess.read_text("utf-8", "replace")
    if "production-home-20261017.html" not in ht or "_mpw_dynamic_main_shell_20261019.php" not in ht:
        fail("Production routing identity changed")
    if not HOME.is_file() or HOME.is_symlink():
        fail("Cannot read verified main homepage")
    for path in files():
        if (not path.is_file() or path.is_symlink() or
                path.parent.is_symlink() or path.parent.parent.is_symlink()):
            fail("Unsafe/missing scoped service file: " + str(path))
    if STYLESHEET.exists() or STYLESHEET.is_symlink():
        fail("New scoped stylesheet already exists; refuse overwrite")


def atomic(path: Path, contents: bytes, mode: int) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".mpw-one-shell-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def backup_dir(run: str) -> Path:
    if not re.fullmatch(r"[0-9]{8,20}", run):
        fail("Invalid GitHub run number")
    return ROOT.parent / (".mpw-one-shell-" + run)


def publish(run: str) -> None:
    verify_paths()
    saved = {str(p.relative_to(ROOT)): p.read_bytes() for p in files()}
    home = HOME.read_text("utf-8")
    header = make_header(home)
    patched: dict[str, bytes] = {}
    service_rel = str(SERVICES.relative_to(ROOT))
    patched[service_rel] = patch_services(saved[service_rel])
    for path in files()[1:]:
        relative = str(path.relative_to(ROOT))
        slug = None if path == REVENUE / "index.html" else path.parent.name
        patched[relative] = patch_revenue(saved[relative], header, slug=slug)
    css_rel = str(STYLESHEET.relative_to(ROOT))
    patched[css_rel] = CSS.encode("utf-8")
    if len(patched) != 15:
        fail("Unexpected number of scoped files")
    backup = backup_dir(run)
    if backup.exists() or backup.is_symlink():
        fail("Run-specific backup already exists")
    backup.mkdir(mode=0o700)
    manifest = {}
    for i, (relative, newer) in enumerate(patched.items()):
        original = saved.get(relative)
        previous = str(i) + ".original"
        if original is not None:
            destination = backup / previous
            with destination.open("xb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(original)
        manifest[relative] = {
            "original": previous if original is not None else None,
            "before": sha(original) if original is not None else None,
            "after": sha(newer),
            "mode": stat.S_IMODE((ROOT / relative).stat().st_mode) if original is not None else 0o644,
        }
    meta = backup / "manifest.json"
    with meta.open("x", encoding="utf-8") as stream:
        os.fchmod(stream.fileno(), 0o600)
        json.dump({"run": run, "files": manifest}, stream, sort_keys=True)
    changed = []
    try:
        for relative, newer in patched.items():
            target = ROOT / relative
            data = manifest[relative]
            if target.is_symlink():
                fail("Changed target to symlink")
            if data["before"] is None:
                if target.exists():
                    fail("New asset appeared concurrently")
            elif not target.is_file() or sha(target.read_bytes()) != data["before"]:
                fail("Concurrent modification to " + relative)
            atomic(target, newer, data["mode"])
            changed.append(relative)
            if sha(target.read_bytes()) != data["after"]:
                fail("Write verification failed for " + relative)
    except BaseException:
        for relative in reversed(changed):
            target = ROOT / relative
            data = manifest[relative]
            if target.is_symlink() or not target.is_file() or sha(target.read_bytes()) != data["after"]:
                continue  # Never overwrite an independent concurrent modification.
            if data["original"] is None:
                target.unlink()
            else:
                atomic(target, saved[relative], data["mode"])
        raise
    print("MPW_SERVICES_ONE_SHELL_PUBLISHED pages=14 asset=1 protected_sites_untouched=true")


def rollback(run: str) -> None:
    backup = backup_dir(run)
    meta = backup / "manifest.json"
    if not backup.is_dir() or backup.is_symlink() or not meta.is_file():
        fail("Scoped backup is unavailable")
    data = json.loads(meta.read_text("utf-8"))
    if data["run"] != run or len(data["files"]) != 15:
        fail("Unexpected scoped backup manifest")
    # Validate every target before rolling any of them back.
    restored = {}
    for relative, item in data["files"].items():
        target = ROOT / relative
        if target.is_symlink() or not target.is_file() or sha(target.read_bytes()) != item["after"]:
            fail("Concurrent edit: refuse destructive rollback of " + relative)
        if item["original"] is None:
            restored[relative] = None
        else:
            old_path = backup / item["original"]
            if not old_path.is_file() or old_path.is_symlink():
                fail("Backup missing for " + relative)
            old = old_path.read_bytes()
            if sha(old) != item["before"]:
                fail("Original content hash mismatch")
            restored[relative] = old
    for relative, original in restored.items():
        target = ROOT / relative
        if original is None:
            target.unlink()
        else:
            atomic(target, original, data["files"][relative]["mode"])
    print("MPW_SERVICES_ONE_SHELL_ROLLED_BACK")


def selftest() -> None:
    header = ('<header class="mw-site-nav"><a class="mw-brand" href="/">M</a>'
              '<nav aria-label="Primary MojPlayWin navigation"><a href="/services/">Services</a>'
              '<details><section data-mpw-earning-directory="v1">'
              + ''.join('<a href="/mpw-editorial/revenue/' + s + '/index.html">X</a>' for s in SLUGS)
              + '</section></details></nav></header>')
    real_header = make_header(header)
    sample = ('<html><head></head><body><header><a class="brand" href="/">MojPlayWin</a>'
              '<nav aria-label="Main navigation"><a href="/store/">Store</a></nav></header>'
              '<main id="content"><p class="crumb">Old</p><h1>Offer</h1></main><footer>Legal</footer></body></html>')
    fixed = patch_revenue(sample.encode(), real_header, slug="website-doctor").decode()
    assert fixed.count(MARK) == 1 and "<h1>Offer</h1>" in fixed
    assert fixed.count("</main>") == 1 and "Legal" in fixed
    service = ('<html><head></head><body><main><section class="mpw-page-cta" '
               'id="expert-guide" aria-label="Read">Guide</section></main></body></html>')
    merged = patch_services(service.encode()).decode()
    assert merged.count(MAIN_MARK) == 1 and merged.count("<main") == 1
    assert len(SLUGS) == 12 and len(set(SLUGS)) == 12
    print("MPW_SERVICES_ONE_SHELL_SELFTEST_OK")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "selftest":
        selftest()
    elif len(sys.argv) == 3 and sys.argv[1] == "publish":
        publish(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "rollback":
        rollback(sys.argv[2])
    else:
        raise SystemExit("Usage: ... selftest | publish RUN | rollback RUN")
