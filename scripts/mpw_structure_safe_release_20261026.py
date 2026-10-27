#!/usr/bin/env python3
"""Scoped, reversible structure/SEO repair for the live MojPlayWin main site.

The active public homepage is a cPanel static source, not the legacy Django
template in this repository. No accounts, commerce, child sites or rewrites
are edited by this release.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile


ACCOUNT = Path("/home/zomorod2")
ROOT = ACCOUNT / "mojplaywin.com"
HOME = ROOT / "design-preview-20261017/production-home-20261017.html"
SITEMAP = ROOT / "design-preview-20261017/_mpw_sitemap_three_indexable_20261017.php"
SERVICES = ROOT / "design-preview-20261017/mpw-ten-editorials-20261018/pages/services.html"
GAMES = ROOT / "design-preview-20261017/mpw-ten-editorials-20261018/pages/games.html"
FOOTER_FIX_MARKER = "<!-- MPW_FOOTER_ORDER_FIXED_20261027 -->"
HOME_MARKER = 'data-mpw-structure-v1="20261026"'
MAP_MARKER = "// MPW_MAIN_NAV_SITEMAP_20261026: indexable navigational destinations"
PREVIOUS_MAP_MARKER = "// 2026-10-25: verified canonical MPW learning resources, isolated sitemap registration"
NAV_PATHS = (
    "/knowledge/",
    "/research/",
    "/company/",
    "/taniya/",
    "/ventures/agriculture/",
)

HOME_CSS = """
<style data-mpw-structure-v1="20261026">
/* Main homepage only: clear progressive sections and reliable mobile navigation. */
.mpw-content-fold{display:block;max-width:1240px;margin:clamp(22px,4vw,48px) auto;border:1px solid rgba(217,180,92,.36);border-radius:20px;background:#11110f;overflow:hidden}
.mpw-content-fold>summary{display:flex;align-items:center;justify-content:space-between;gap:12px;min-height:56px;padding:16px clamp(18px,3vw,30px);color:#f0cf82;font-size:clamp(1rem,1.55vw,1.15rem);font-weight:750;cursor:pointer;list-style:none}
.mpw-content-fold>summary::-webkit-details-marker{display:none}
.mpw-content-fold>summary::after{content:"+";font-size:1.55rem;line-height:1}
.mpw-content-fold[open]>summary::after{content:"−"}
.mpw-content-fold>summary:hover{background:rgba(217,180,92,.08)}
.mpw-content-fold>summary:focus-visible{outline:3px solid #f0cf82;outline-offset:-4px}
.mpw-content-fold>.mw-section{margin:0!important;border-top:1px solid rgba(217,180,92,.22);border-radius:0!important}
.mw-site-nav nav>a,.mw-nav-menu>summary,.mw-actions a{min-height:44px}
@media(max-width:760px){
  .mpw-top-utility-panel{flex-wrap:wrap;gap:12px}
  .mw-site-nav{flex-wrap:wrap;gap:12px;padding:12px!important}
  .mw-site-nav nav{width:100%;justify-content:flex-start;gap:6px}
  .mw-site-nav nav>a,.mw-nav-menu>summary{font-size:.9rem;padding:10px 12px}
  .mw-nav-panel{left:0;right:auto;width:min(92vw,520px);max-height:65dvh;grid-template-columns:repeat(2,minmax(0,1fr));overscroll-behavior:contain}
  .mpw-content-fold{margin:18px 12px}
}
@media(max-width:430px){.mw-nav-panel{grid-template-columns:1fr}.mw-brand-copy small{letter-spacing:.06em}}
@media(prefers-reduced-motion:reduce){.mpw-content-fold *, .mpw-content-fold *::before, .mpw-content-fold *::after{transition:none!important}}
</style>
""".strip()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def section_span(text, element_id):
    start_tag = re.compile(r"<section\b[^>]*\bid=[\"']" + re.escape(element_id) + r"[\"'][^>]*>", re.I | re.S)
    hits = list(start_tag.finditer(text))
    if len(hits) != 1:
        raise RuntimeError(f"SECTION_ANCHOR_DRIFT:{element_id}:{len(hits)}")
    start = hits[0].start()
    depth = 0
    for token in re.finditer(r"</?section\b[^>]*>", text[start:], re.I | re.S):
        if token.group().lower().startswith("</"):
            depth -= 1
        else:
            depth += 1
        if depth == 0:
            return start, start + token.end()
    raise RuntimeError(f"UNCLOSED_SECTION:{element_id}")


def fold(text, element_id, label):
    start, end = section_span(text, element_id)
    fragment = text[start:end]
    if "<script" in fragment.lower() or "<footer" in fragment.lower():
        raise RuntimeError(f"UNEXPECTED_SECTION_CONTENT:{element_id}")
    return (
        text[:start]
        + '<details class="mpw-content-fold" data-mpw-fold="' + element_id + '">'
        + '<summary>' + label + '</summary>'
        + fragment
        + '</details>'
        + text[end:]
    )


def patch_home(raw):
    text = raw.decode("utf-8")
    if HOME_MARKER in text:
        if text.count(HOME_MARKER) != 1:
            raise RuntimeError("HOME_MARKER_DUPLICATED")
        existing_folds = text.count('<details class="mpw-content-fold"')
        if existing_folds == 2:
            return raw
        if existing_folds != 0:
            raise RuntimeError("PARTIAL_HOME_FOLD_DRIFT")
        # A prior interrupted deployment installed CSS but not the two semantic
        # disclosure containers. Repair this partial state without duplicating CSS.
        text = fold(text, "mpw-home-ten-guides", "Read the ten original field guides")
        text = fold(text, "site-directory", "Browse the complete site directory")
        if text.count('<details class="mpw-content-fold"') != 2:
            raise RuntimeError("PARTIAL_HOME_FOLD_REPAIR_FAILED")
        return text.encode("utf-8")
    if not (100_000 < len(raw) < 850_000):
        raise RuntimeError("UNEXPECTED_HOME_SIZE")
    for marker in ('id="mpw-home-ten-guides"', 'id="site-directory"', 'id="mw-all-pages-menu"', 'class="mw-site-nav"'):
        if text.count(marker) != 1:
            raise RuntimeError("HOME_SOURCE_DRIFT:" + marker)
    if text.lower().count("</head>") != 1:
        raise RuntimeError("INVALID_HOME_HEAD")
    # Entire sections stay in the DOM and remain keyboard/screen-reader accessible.
    # Collapsing them changes presentation, not their contents, URLs or SEO copy.
    text = fold(text, "mpw-home-ten-guides", "Read the ten original field guides")
    text = fold(text, "site-directory", "Browse the complete site directory")
    text = re.sub(r"</head\s*>", HOME_CSS + "\n</head>", text, count=1, flags=re.I)
    if text.count(HOME_MARKER) != 1:
        raise RuntimeError("HOME_STRUCTURE_PATCH_FAILED")
    for original in ('id="mpw-home-ten-guides"', 'id="site-directory"', 'id="mw-all-pages-menu"'):
        if text.count(original) != 1:
            raise RuntimeError("HOME_CONTENT_LOST:" + original)
    return text.encode("utf-8")



def patch_home_footer_order(raw):
    """Move the revenue offer inside the one main landmark, before the footer."""
    text = raw.decode("utf-8")
    if FOOTER_FIX_MARKER in text:
        if text.count(FOOTER_FIX_MARKER) != 1:
            raise RuntimeError("FOOTER_FIX_MARKER_DUPLICATED")
        return raw
    if HOME_MARKER not in text or text.count("<main") != 1 or text.count("</main>") != 1:
        raise RuntimeError("UNEXPECTED_ACTIVE_HOME_LANDMARKS")
    footer_start = text.find('<footer class="mw-site-footer"')
    if footer_start < 0 or text.count("</footer>") != 1:
        raise RuntimeError("FOOTER_SOURCE_DRIFT")
    footer_end = text.find("</footer>", footer_start) + len("</footer>")
    match = re.search(r'<section id="mpw-revenue-offers-20261020"[^>]*>[\s\S]*?</section>', text)
    if not match or text.count('id="mpw-revenue-offers-20261020"') != 1:
        raise RuntimeError("REVENUE_SECTION_DRIFT")
    offer_start, offer_end = match.span()
    main_end = text.find("</main>", offer_end)
    if not (footer_start < footer_end < offer_start < offer_end <= main_end):
        raise RuntimeError("HOMEPAGE_FOOTER_SEQUENCE_CHANGED")
    gap = text[footer_end:offer_start]
    if re.sub(r'<script\b[^>]*></script>', "", gap, flags=re.I | re.S).strip():
        raise RuntimeError("UNEXPECTED_CONTENT_BETWEEN_FOOTER_AND_REVENUE")
    if text[offer_end:main_end].strip():
        raise RuntimeError("UNEXPECTED_CONTENT_AFTER_REVENUE")
    footer = text[footer_start:footer_end]
    offer = text[offer_start:offer_end]
    result = (
        text[:footer_start] + offer + "\n</main>\n" + footer
        + gap + "\n" + FOOTER_FIX_MARKER + "\n"
        + text[main_end + len("</main>"):]
    )
    if (result.count("<main") != 1 or result.count("</main>") != 1
            or result.count("<footer") != 1 or result.count("</footer>") != 1
            or result.count('id="mpw-revenue-offers-20261020"') != 1
            or result.index("</main>") > result.index("<footer")):
        raise RuntimeError("FOOTER_FIX_SEMANTIC_CHECK_FAILED")
    return result.encode("utf-8")


GUIDE_LINK_REPLACEMENTS = {
    'href="/#mpw-insight-title"': 'href="/mpw-editorial/field-guides/original-ten/"',
    'href="/#field-library-round2"': 'href="/mpw-editorial/field-guides/20261023/index.html"',
    'href="/#field-library-advanced"': 'href="/mpw-editorial/field-guides/20261023/index.html"',
}


def patch_editorial_guide_links(raw):
    """Consolidate legacy in-page links onto extant standalone guide libraries."""
    text = raw.decode("utf-8")
    matches = [text.count(old) for old in GUIDE_LINK_REPLACEMENTS]
    if all(count == 0 for count in matches):
        return raw
    if any(count == 0 for count in matches) or "<main" not in text:
        raise RuntimeError("EDITORIAL_LINK_SOURCE_DRIFT")
    result = text
    for old, new in GUIDE_LINK_REPLACEMENTS.items():
        result = result.replace(old, new)
    if any(old in result for old in GUIDE_LINK_REPLACEMENTS):
        raise RuntimeError("EDITORIAL_LINK_REPAIR_INCOMPLETE")
    return result.encode("utf-8")


def patch_sitemap(raw):
    text = raw.decode("utf-8")
    if MAP_MARKER in text:
        if text.count(MAP_MARKER) != 1:
            raise RuntimeError("SITEMAP_MARKER_DUPLICATED")
        return raw
    if text.count(PREVIOUS_MAP_MARKER) != 1:
        raise RuntimeError("SITEMAP_SOURCE_DRIFT")
    paths = ", ".join("'" + path + "'" for path in NAV_PATHS)
    insertion = "\n" + MAP_MARKER + "\n$paths = array_merge($paths, [" + paths + "]);"
    newer = text.replace(PREVIOUS_MAP_MARKER, PREVIOUS_MAP_MARKER + insertion, 1)
    if newer.count(MAP_MARKER) != 1:
        raise RuntimeError("SITEMAP_PATCH_FAILED")
    return newer.encode("utf-8")


def verify_live_targets():
    if ROOT.is_symlink() or ROOT.resolve() != ROOT or not ROOT.is_dir():
        raise RuntimeError("INVALID_SITE_ROOT")
    for marker in (ROOT / ".htaccess", ROOT / "passenger_wsgi.py"):
        if not marker.is_file() or marker.is_symlink():
            raise RuntimeError("SITE_IDENTITY_MISSING")
    for path in (HOME, SITEMAP, SERVICES):
        if path.is_symlink() or not path.is_file() or path.parent.is_symlink():
            raise RuntimeError("UNSAFE_RELEASE_TARGET:" + str(path))


def php_lint(data):
    fd, name = tempfile.mkstemp(prefix=".mpw-map-lint-", suffix=".php", dir=str(SITEMAP.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        p = subprocess.run(["php", "-l", name], capture_output=True, text=True, timeout=20)
        if p.returncode:
            raise RuntimeError("PHP_LINT_FAILED:" + p.stderr[-250:])
    finally:
        if os.path.exists(name):
            os.unlink(name)


def atomic(path, data):
    fd, name = tempfile.mkstemp(prefix=".mpw-structure-stage-", dir=str(path.parent))
    try:
        os.fchmod(fd, stat.S_IMODE(path.stat().st_mode))
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def backup_path(run_id):
    if not re.fullmatch(r"[0-9]{6,20}", run_id):
        raise RuntimeError("BAD_RUN_ID")
    return ACCOUNT / (".mpw-structure-20261026-" + run_id)


def publish(run_id):
    verify_live_targets()
    targets = {"home": HOME, "sitemap": SITEMAP, "services": SERVICES}
    before = {key: path.read_bytes() for key, path in targets.items()}
    after = {
        "home": patch_home_footer_order(patch_home(before["home"])),
        "sitemap": patch_sitemap(before["sitemap"]),
        "services": patch_editorial_guide_links(before["services"]),
    }
    changed = [key for key in targets if before[key] != after[key]]
    if not changed:
        print("MPW_STRUCTURE_ALREADY_APPLIED")
        return
    php_lint(after["sitemap"])
    state = backup_path(run_id)
    if state.exists() or state.is_symlink():
        raise RuntimeError("BACKUP_COLLISION")
    state.mkdir(mode=0o700)
    manifest = {"run": run_id, "files": {}}
    for key in changed:
        (state / (key + ".before")).write_bytes(before[key])
        manifest["files"][key] = {"before": digest(before[key]), "after": digest(after[key])}
    (state / "manifest.json").write_text(json.dumps(manifest, sort_keys=True))
    changed_now = []
    try:
        for key in changed:
            path = targets[key]
            if digest(path.read_bytes()) != digest(before[key]):
                raise RuntimeError("CONCURRENT_MODIFICATION:" + key)
            atomic(path, after[key])
            changed_now.append(key)
            if digest(path.read_bytes()) != digest(after[key]):
                raise RuntimeError("POSTWRITE_MISMATCH:" + key)
    except BaseException:
        for key in reversed(changed_now):
            if digest(targets[key].read_bytes()) == digest(after[key]):
                atomic(targets[key], before[key])
        raise
    print("MPW_STRUCTURE_RELEASE=" + json.dumps({"changed": changed, "home_bytes": len(after["home"]), "seo_urls": NAV_PATHS}))


def rollback(run_id):
    verify_live_targets()
    state = backup_path(run_id)
    if not state.is_dir() or state.is_symlink():
        print("NO_MATCHING_STRUCTURE_BACKUP")
        return
    manifest = json.loads((state / "manifest.json").read_text())
    if manifest.get("run") != run_id:
        raise RuntimeError("WRONG_BACKUP_RUN")
    targets = {"home": HOME, "sitemap": SITEMAP, "services": SERVICES}
    pending = {}
    for key, checks in manifest["files"].items():
        original = (state / (key + ".before")).read_bytes()
        if digest(original) != checks["before"]:
            raise RuntimeError("INVALID_BACKUP:" + key)
        if digest(targets[key].read_bytes()) != checks["after"]:
            raise RuntimeError("CONCURRENT_CHANGE_REFUSE_ROLLBACK:" + key)
        pending[key] = original
    for key, original in pending.items():
        atomic(targets[key], original)
    print("MPW_STRUCTURE_ROLLBACK_OK")


def selftest():
    sample = (
        '<!doctype html><head></head><body><div class="mw-site-nav" id="mw-all-pages-menu"></div>'
        '<section id="mpw-home-ten-guides"><h2>Ten guides</h2><div><section><p>Nested</p></section></div></section>'
        '<section id="site-directory"><h2>Directory</h2><a href="/store/">Store</a></section></body>'
    )
    # The production size gate deliberately blocks synthetic small pages.
    sample = sample.replace('</head>', '<meta name="fixture" content="yes"></head>')
    assert section_span(sample, "mpw-home-ten-guides")[1] <= section_span(sample, "site-directory")[0]
    updated = fold(fold(sample, "mpw-home-ten-guides", "Guides"), "site-directory", "Directory")
    assert updated.count('<details class="mpw-content-fold"') == 2
    assert updated.count('href="/store/"') == 1 and 'Nested' in updated
    padded = sample.replace('</body>', '<!-- harmless fixture -->' * 6000 + '</body>')
    home = patch_home(padded.encode())
    assert HOME_MARKER.encode() in home and home.count(b'mpw-content-fold') >= 2
    assert patch_home(home) == home
    half_applied = padded.replace("</head>", HOME_CSS + "\n</head>").encode()
    repaired = patch_home(half_applied)
    assert repaired.count(b'<details class="mpw-content-fold"') == 2
    assert repaired.count(HOME_MARKER.encode()) == 1
    assert patch_home(repaired) == repaired
    existing = ('<?php\n' + PREVIOUS_MAP_MARKER + '\n$paths=[];').encode()
    patched = patch_sitemap(existing)
    assert patched.count(MAP_MARKER.encode()) == 1 and all(path.encode() in patched for path in NAV_PATHS)
    assert patch_sitemap(patched) == patched
    footer_fixture = (
        '<main><p>Keep original main content</p><footer class="mw-site-footer">'
        '<p>Protected legal footer</p></footer>\n'
        '<script src="/assets/orbits.js" defer></script>\n'
        '<section id="mpw-revenue-offers-20261020"><p>Keep offer</p></section>'
        '</main><script>window.ready=true;</script>'
    )
    footer_fixture = footer_fixture.replace("<main>", '<main><!-- ' + HOME_MARKER + ' -->')
    fixed = patch_home_footer_order(footer_fixture.encode())
    assert fixed.count(b"<main") == 1 and fixed.count(b"</main>") == 1
    assert fixed.index(b"</main>") < fixed.index(b"<footer")
    assert b"Protected legal footer" in fixed and b"Keep offer" in fixed
    assert patch_home_footer_order(fixed) == fixed
    guide_fixture = ('<main><a href="/#mpw-insight-title">One</a>'
        '<a href="/#field-library-round2">Two</a>'
        '<a href="/#field-library-advanced">Three</a></main>').encode()
    resolved = patch_editorial_guide_links(guide_fixture)
    assert b'/#field-library-' not in resolved
    assert b'/mpw-editorial/field-guides/' in resolved
    assert patch_editorial_guide_links(resolved) == resolved
    print("MPW_STRUCTURE_SELFTEST=PASS")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "selftest":
        selftest()
    elif len(sys.argv) == 3 and sys.argv[1] in ("publish", "rollback"):
        (publish if sys.argv[1] == "publish" else rollback)(sys.argv[2])
    else:
        raise SystemExit("usage: selftest | publish RUN_ID | rollback RUN_ID")
