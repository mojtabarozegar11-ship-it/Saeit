#!/usr/bin/env python3
"""Guarded visual-shell unification for 18 standalone MojPlayWin free pages.

Never modifies embedded exercises, JavaScript tools, URLs, store, personal
website or protected sibling apps. Shares the already published main-site
navigation stylesheet and copies current canonical navigation on release.
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
SHELL_CSS = ROOT / "mpw-editorial/revenue/assets/mpw-one-shell-20261026.css"
TOOLS = (
    "chess-calendar", "taniya-storytime", "atelier-seo", "atelier-contrast",
    "browser-game-qa", "research-evidence",
)
LEARNING_A = (
    "chess-baseline", "family-storytime", "website-client-brief", "research-methods",
)
LEARNING_B = (
    "chess-error-review", "taniya-creative-retelling",
    "atelier-accessibility-acceptance", "browser-game-retention-diagnostics",
    "digital-product-license-check", "research-data-audit-trail",
)
MARK = 'data-mpw-content-shell="20261026"'
CSS_LINK = '<link rel="stylesheet" href="/mpw-editorial/revenue/assets/mpw-one-shell-20261026.css">'
RESET = """<style id="mpw-content-layout-20261026">
body.mpw-content-unified{margin:0!important;max-width:none!important;padding:0!important}
body.mpw-content-unified>main{box-sizing:border-box;max-width:960px;
width:calc(100% - 28px);margin:clamp(16px,3vw,34px) auto 42px}
body.mpw-content-unified>header.mpw-unified-shell{font-family:system-ui,Arial,sans-serif;
font-size:16px;line-height:1.35;color:#f1ebde}
body.mpw-content-unified>.mpw-content-footer{box-sizing:border-box;max-width:960px;
margin:0 auto 30px;padding:18px 14px;border-top:1px solid #86959b;
display:flex;flex-wrap:wrap;gap:14px;font:700 15px/1.6 system-ui,sans-serif}
body.mpw-content-unified>.mpw-content-footer a{color:#075b87}
body.mpw-content-unified>.mpw-content-footer a:focus-visible{outline:3px solid #c68a21}
@media(max-width:600px){body.mpw-content-unified>main{width:calc(100% - 16px)}}
</style>"""
HEADER_RE = re.compile(r'<header\b[^>]*class="mw-site-nav"[^>]*>[\s\S]*?</header>', re.I)
BODY_RE = re.compile(r"<body>", re.I)


def err(message: str) -> None:
    raise RuntimeError(message)


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def paths() -> list[Path]:
    root_tools = ROOT / "mpw-free-tools/20261025"
    root_learn = ROOT / "mpw-learning/20261025"
    root_learn_b = ROOT / "mpw-learning/20261025b"
    return (
        [root_tools / "index.html"]
        + [root_tools / item / "index.html" for item in TOOLS]
        + [root_learn / "index.html"]
        + [root_learn / item / "index.html" for item in LEARNING_A]
        + [root_learn_b / item / "index.html" for item in LEARNING_B]
    )


def official_header(home_html: str) -> str:
    blocks = list(HEADER_RE.finditer(home_html))
    if len(blocks) != 1:
        err("Official main homepage nav is not unique")
    header = blocks[0].group(0)
    for required in (
        'aria-label="Primary MojPlayWin navigation"',
        'href="/services/"',
        'href="/mpw-editorial/revenue/index.html"',
        'data-mpw-earning-directory="v1"',
    ):
        if required not in header:
            err("Official main-site navigation drifted: " + required)
    return header.replace(
        '<header class="mw-site-nav"',
        '<header class="mw-site-nav mpw-unified-shell" ' + MARK,
        1,
    )


def patch(content: bytes, header: str) -> bytes:
    html = content.decode("utf-8")
    if MARK in html or 'id="mpw-content-layout-20261026"' in html:
        err("Content page has already been integrated")
    if (len(BODY_RE.findall(html)) != 1 or html.count("</body>") != 1 or
            html.count("</head>") != 1 or html.count("<main") != 1 or
            html.count("</main>") != 1 or "<!doctype html>" not in html.lower()):
        err("Unexpected independent learning/tool HTML shape")
    if "<header" in html.lower():
        err("Unexpected pre-existing header: cannot safely add shell")
    old_scripts = html.lower().count("<script")
    old_canonicals = re.findall(r'<link\s+rel="canonical"\s+href="[^"]+"', html, re.I)
    out = html.replace("</head>", CSS_LINK + RESET + "</head>", 1)
    out = BODY_RE.sub('<body class="mpw-content-unified">' + header, out, count=1)
    foot = ('<footer class="mpw-content-footer" aria-label="MojPlayWin navigation">'
            '<a href="/">MojPlayWin home</a><a href="/services/">Services</a>'
            '<a href="/knowledge/">Knowledge</a><a href="/research/">Research</a>'
            '<a href="/mpw-free-tools/20261025/">Free tools</a>'
            '<a href="/mpw-learning/20261025/">Free guides</a>'
            '<a href="/contact/">Contact</a></footer>')
    out = out.replace("</body>", foot + "</body>", 1)
    if (out.count(MARK) != 1 or out.count("<header") != 1 or
            out.count("</main>") != 1 or out.lower().count("<script") != old_scripts or
            re.findall(r'<link\s+rel="canonical"\s+href="[^"]+"', out, re.I) != old_canonicals):
        err("Content publication changed more than its external navigation shell")
    return out.encode("utf-8")


def verify_root() -> None:
    if ROOT.resolve() != ROOT or ROOT.is_symlink() or ROOT.name != "mojplaywin.com":
        err("Unexpected document root")
    ht = ROOT / ".htaccess"
    if not ht.is_file() or ht.is_symlink():
        err("Production routing missing")
    ht_text = ht.read_text("utf-8", "replace")
    if "production-home-20261017.html" not in ht_text:
        err("Main site route identity changed")
    if not HOME.is_file() or HOME.is_symlink():
        err("Verified main homepage unavailable")
    if not SHELL_CSS.is_file() or SHELL_CSS.is_symlink():
        err("Main unified navigation stylesheet not published")
    if ".mpw-unified-shell" not in SHELL_CSS.read_text("utf-8", "replace"):
        err("Unexpected unified navigation stylesheet")
    for path in paths():
        if not path.is_file() or path.is_symlink():
            err("Missing or unsafe free resource path: " + str(path))
        ancestor = path.parent
        while ancestor != ROOT:
            if ancestor.is_symlink() or not ancestor.is_dir():
                err("Unsafe ancestor " + str(ancestor))
            ancestor = ancestor.parent


def backup_dir(run: str) -> Path:
    if not re.fullmatch(r"[0-9]{8,20}", run):
        err("Invalid run identifier")
    return ROOT.parent / (".mpw-learning-shell-" + run)


def atomic(path: Path, data: bytes, mode: int) -> None:
    fd, temp = tempfile.mkstemp(prefix=".mpw-learn-shell-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def publish(run: str) -> None:
    verify_root()
    header = official_header(HOME.read_text("utf-8"))
    current = {str(p.relative_to(ROOT)): p.read_bytes() for p in paths()}
    newer = {key: patch(blob, header) for key, blob in current.items()}
    if len(newer) != 18:
        err("Expected exactly 18 resource documents")
    backup = backup_dir(run)
    if backup.exists() or backup.is_symlink():
        err("Backup collision")
    backup.mkdir(mode=0o700)
    manifest = {}
    for idx, (relative, original) in enumerate(current.items()):
        saved = backup / (str(idx) + ".original")
        with saved.open("xb") as output:
            os.fchmod(output.fileno(), 0o600)
            output.write(original)
        manifest[relative] = {
            "saved": saved.name, "before": digest(original), "after": digest(newer[relative]),
            "mode": stat.S_IMODE((ROOT / relative).stat().st_mode),
        }
    with (backup / "manifest.json").open("x", encoding="utf-8") as output:
        os.fchmod(output.fileno(), 0o600)
        json.dump({"run": run, "files": manifest}, output, sort_keys=True)
    changed = []
    try:
        for relative, original in current.items():
            target = ROOT / relative
            if target.is_symlink() or digest(target.read_bytes()) != manifest[relative]["before"]:
                err("Concurrent independent edit of " + relative)
            atomic(target, newer[relative], manifest[relative]["mode"])
            changed.append(relative)
            if digest(target.read_bytes()) != manifest[relative]["after"]:
                err("Target SHA mismatch " + relative)
    except BaseException:
        for relative in reversed(changed):
            target = ROOT / relative
            if (not target.is_symlink() and target.is_file() and
                    digest(target.read_bytes()) == manifest[relative]["after"]):
                atomic(target, current[relative], manifest[relative]["mode"])
        raise
    print("MPW_18_FREE_TOOLS_AND_LEARNING_PAGES_UNIFIED=PASS")


def rollback(run: str) -> None:
    backup = backup_dir(run)
    meta = backup / "manifest.json"
    if not backup.is_dir() or backup.is_symlink() or not meta.is_file():
        err("No verified run backup")
    manifest = json.loads(meta.read_text("utf-8"))
    allowed = {str(p.relative_to(ROOT)) for p in paths()}
    if manifest["run"] != run or set(manifest["files"]) != allowed:
        err("Unexpected rollback inventory")
    validated = {}
    for relative, item in manifest["files"].items():
        target = ROOT / relative
        saved = backup / item["saved"]
        if (not target.is_file() or target.is_symlink() or
                digest(target.read_bytes()) != item["after"] or
                not saved.is_file() or saved.is_symlink()):
            err("Concurrent edit or missing backup " + relative)
        previous = saved.read_bytes()
        if digest(previous) != item["before"]:
            err("Original backup checksum changed")
        validated[relative] = previous
    for relative, previous in validated.items():
        atomic(ROOT / relative, previous, manifest["files"][relative]["mode"])
    print("MPW_18_FREE_PAGES_ROLLBACK=PASS")


def selftest() -> None:
    nav = ('<header class="mw-site-nav"><nav aria-label="Primary MojPlayWin navigation">'
           '<a href="/services/">Services</a><a href="/mpw-editorial/revenue/index.html">Offers</a>'
           '<section data-mpw-earning-directory="v1">Links</section></nav></header>')
    header = official_header(nav)
    sample = (b'<!doctype html><html><head><link rel="canonical" href="https://mojplaywin.com/one/">'
              b'</head><body><main><h1>Preserve lesson</h1>'
              b'<script>const a=1;</script></main></body></html>')
    fixed = patch(sample, header)
    assert fixed.count(b'Preserve lesson') == 1 and fixed.count(b'<script') == 1
    assert fixed.count(b'data-mpw-content-shell="20261026"') == 1
    assert fixed.count(b'<main') == 1 and fixed.count(b'</main>') == 1
    assert len(paths()) == 18 and len(set(paths())) == 18
    print("MPW_LEARNING_TOOLS_SHELL_SELFTEST_OK")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "selftest":
        selftest()
    elif len(sys.argv) == 3 and sys.argv[1] == "publish":
        publish(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "rollback":
        rollback(sys.argv[2])
    else:
        raise SystemExit("Usage: selftest | publish RUN | rollback RUN")
