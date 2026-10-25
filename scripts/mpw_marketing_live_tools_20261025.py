#!/usr/bin/env python3
"""Publish eight reviewed, browser-only tools to isolated public locations.

No account, order, payment, social destination, database or existing site file
is changed. The installer refuses overwrites and rollback checks file hashes.
"""
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import sys

RELEASE = "free-tools-20261025-v1"
HOME = Path("/home/zomorod2")
STAGE_PREFIX = ".mpw-marketing-live-stage-"
ROOTS = {
    "mpw": HOME / "mojplaywin.com" / "mpw-free-tools" / "20261025",
    "zm": HOME / "public_html" / "agriculture" / "free-tools" / "20261025",
}
TOOLS = [
    ("mpw", "chess-calendar", "chess-84-day-calendar-builder-20261025.html",
     "Chess 84-day calendar", "Create a structured, editable training calendar and export CSV.",
     "https://mojplaywin.com/store/product/72/"),
    ("mpw", "taniya-storytime", "taniya-storytime-studio-20261025.html",
     "Family storytime studio", "Original read-aloud prompts and printable family activities.",
     "https://mojplaywin.com/store/product/225/"),
    ("mpw", "atelier-seo", "atelier-seo-meta-generator-20261025.html",
     "SEO metadata generator", "Create title, description, canonical and social preview tags.",
     "https://mojplaywin.com/store/product/879/"),
    ("mpw", "atelier-contrast", "atelier-wcag-contrast-checker-20261025.html",
     "WCAG contrast checker", "Calculate text contrast and review accessibility thresholds.",
     "https://mojplaywin.com/store/product/879/"),
    ("mpw", "browser-game-qa", "browser-game-qa-evidence-20261025.html",
     "Browser game quality worksheet", "Document release readiness without invented test passes.",
     "https://mojplaywin.com/games/"),
    ("mpw", "research-evidence", "mojtaba-research-evidence-appraisal-20261025.html",
     "Research evidence appraisal", "Record methods, limitations and source quality transparently.",
     "https://mojplaywin.com/mojtaba.roozegar/resume/"),
    ("zm", "farm-break-even", "fa-farm-break-even-calculator-20261025.html",
     "محاسبه‌گر نقطه سربه‌سر مزرعه", "برآورد اقتصادی هزینه، عملکرد و نقطه سربه‌سر مزرعه.",
     "https://zomorodmelal.ir/contact/"),
    ("zm", "import-landed-cost", "fa-import-landed-cost-scenario-20261025.html",
     "محاسبه‌گر هزینه واردات", "مقایسه سناریوهای هزینه واردات با مفروضات شفاف.",
     "https://zomorodmelal.ir/contact/"),
]

def digest(data):
    return hashlib.sha256(data).hexdigest()

def check_path(path):
    if path.is_symlink():
        raise RuntimeError("SYMLINK_PATH_REFUSED:" + str(path))

def build(out):
    if out.exists():
        raise RuntimeError("BUILD_DESTINATION_ALREADY_EXISTS")
    out.mkdir(parents=True)
    manifest = {"release": RELEASE, "files": {"mpw": {}, "zm": {}}}
    for site, slug, source, title, description, destination in TOOLS:
        src = Path("docs/marketing/tools") / source
        body = src.read_text(encoding="utf-8")
        if not body.lstrip().lower().startswith("<!doctype html>"):
            raise RuntimeError("INVALID_HTML_DOCTYPE:" + source)
        if body.count('<meta name="robots" content="noindex">') != 1:
            raise RuntimeError("MISSING_EXPECTED_ROBOTS_MARKER:" + source)
        if "<script>" not in body or "</script>" not in body:
            raise RuntimeError("NOT_A_STANDALONE_INTERACTIVE_TOOL:" + source)
        if re.search(r"<script[^>]+src=|<iframe|<form[^>]+action=|fetch\s*\(|XMLHttpRequest|document\.cookie", body, re.I):
            raise RuntimeError("NETWORK_OR_EMBEDDED_DEPENDENCY_REFUSED:" + source)
        if "dr.mojtaba.rozegar" in body or "7317306" in body:
            raise RuntimeError("FORBIDDEN_SOCIAL_DESTINATION_REFUSED")
        base = ("https://mojplaywin.com/mpw-free-tools/20261025/" if site == "mpw"
                else "https://zomorodmelal.ir/agriculture/free-tools/20261025/")
        canonical = base + slug + "/"
        safe_title = html.escape(title, quote=True)
        safe_description = html.escape(description, quote=True)
        metadata = ('<meta name="robots" content="index,follow,max-image-preview:large">'
                    '<link rel="canonical" href="' + canonical + '">'
                    '<meta name="description" content="' + safe_description + '">'
                    '<meta property="og:type" content="website">'
                    '<meta property="og:title" content="' + safe_title + '">'
                    '<meta property="og:description" content="' + safe_description + '">'
                    '<meta property="og:url" content="' + canonical + '">')
        body = body.replace('<meta name="robots" content="noindex">', metadata, 1)
        body = body.replace("utm_source=github", "utm_source=onsite_free_tool")
        separator = "&" if "?" in destination else "?"
        campaign = destination + separator + ("utm_source=onsite_free_tool&amp;utm_medium=organic&amp;utm_campaign=free_tools_20261025&amp;utm_content=" + slug)
        cta = ('<aside style="max-width:800px;margin:2rem auto;padding:1.2rem;border:2px solid #b59b58;'
               'border-radius:12px;font:16px/1.7 system-ui,sans-serif">'
               '<p><strong>' + safe_title + '</strong> · Free browser-based tool. '
               'Results are illustrative; check inputs before professional use.</p>'
               '<a rel="noopener" href="' + campaign + '">Explore the related official resource →</a></aside>')
        if site == "zm":
            cta = cta.replace("Free browser-based tool. Results are illustrative; check inputs before professional use.",
                              "ابزار رایگان مرورگری؛ محاسبات آموزشی هستند و جایگزین بررسی تخصصی نیستند.")
            cta = cta.replace("Explore the related official resource →", "ارتباط با شرکت زمرد ملل ←")
        body = body.replace("</body>", cta + "</body>", 1)
        if canonical not in body or body.count("index,follow") != 1:
            raise RuntimeError("CANONICAL_OR_ROBOTS_BUILD_FAILED:" + source)
        target = out / site / slug / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        manifest["files"][site][slug + "/index.html"] = digest(target.read_bytes())
    for site in ("mpw", "zm"):
        group = [x for x in TOOLS if x[0] == site]
        if site == "mpw":
            heading, intro, lang = "Free interactive tools | MojPlayWin", "Eight free tools across the two official websites. The six below run locally in your browser and link to official resources.", "en"
        else:
            heading, intro, lang = "ابزارهای رایگان | زمرد ملل", "دو محاسبه‌گر آموزشی رایگان برای اقتصاد مزرعه و سناریوهای واردات؛ بدون دریافت اطلاعات شخصی.", "fa"
        items = "\n".join(
            '<li><a href="./' + slug + '/">' + html.escape(title) + '</a> — ' + html.escape(desc) + '</li>'
            for _, slug, _, title, desc, _ in group)
        origin = ("https://mojplaywin.com/mpw-free-tools/20261025/" if site == "mpw"
                  else "https://zomorodmelal.ir/agriculture/free-tools/20261025/")
        official = ("https://mojplaywin.com/store/" if site == "mpw" else "https://zomorodmelal.ir/contact/")
        direction = "rtl" if lang == "fa" else "ltr"
        index = ('<!doctype html><html lang="' + lang + '" dir="' + direction + '"><head>'
                 '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                 '<meta name="robots" content="index,follow"><link rel="canonical" href="' + origin + '">'
                 '<meta name="description" content="' + html.escape(intro, quote=True) + '">'
                 '<title>' + html.escape(heading) + '</title>'
                 '<style>body{font:17px/1.8 system-ui,sans-serif;max-width:920px;margin:3rem auto;padding:0 1rem;color:#152d3c;background:#f4f8fa}'
                 'main{background:white;padding:clamp(1rem,4vw,3rem);border:1px solid #c8d8e1;border-radius:18px}'
                 'a{color:#075b87}li{margin:1rem 0}a:focus-visible{outline:3px solid orange}</style></head><body>'
                 '<main><h1>' + html.escape(heading) + '</h1><p>' + html.escape(intro) + '</p><ul>' + items + '</ul>'
                 '<p><a href="' + official + '?utm_source=onsite_free_tool&amp;utm_medium=organic&amp;utm_campaign=free_tools_20261025">'
                 + ("Visit the official store" if site == "mpw" else "تماس و همکاری با زمرد ملل")
                 + '</a></p><p>All calculations and worksheets run in the browser; no account is required.</p></main></body></html>')
        dest = out / site / "index.html"
        dest.write_text(index, encoding="utf-8")
        manifest["files"][site]["index.html"] = digest(dest.read_bytes())
    (out / "release.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    assert sum(map(len, manifest["files"].values())) == 10
    print("MARKETING_PUBLIC_TOOL_BUNDLE_BUILT_10_FILES")

def stage_path(run_id):
    if not re.fullmatch(r"[0-9]{6,20}", run_id):
        raise RuntimeError("INVALID_RUN_ID")
    return HOME / (STAGE_PREFIX + run_id)

def check_install_roots():
    mpw = HOME / "mojplaywin.com"
    zm = HOME / "public_html"
    for p in (HOME, mpw, zm, zm / "agriculture"):
        check_path(p)
        if not p.is_dir():
            raise RuntimeError("EXPECTED_SITE_DIRECTORY_MISSING:" + str(p))
    wsgi = mpw / "passenger_wsgi.py"
    check_path(wsgi)
    if not wsgi.is_file() or "APP='/home/zomorod2/Saeit-staging'" not in wsgi.read_text("utf-8", "replace"):
        raise RuntimeError("ACTIVE_MPW_PASSENGER_IDENTITY_MISMATCH")

def verify_tree(root, hashes):
    check_path(root)
    if not root.is_dir():
        raise RuntimeError("RELEASE_DIRECTORY_MISSING:" + str(root))
    actual = {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
    if actual != set(hashes):
        raise RuntimeError("RELEASE_FILE_SET_MISMATCH:" + str(root))
    for relative, expected in hashes.items():
        f = root / relative
        check_path(f)
        if digest(f.read_bytes()) != expected:
            raise RuntimeError("RELEASE_HASH_MISMATCH:" + str(f))

def install(action, run_id):
    check_install_roots()
    stage = stage_path(run_id)
    check_path(stage)
    manifest_path = stage / "release.json"
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise RuntimeError("RELEASE_MANIFEST_MISSING")
    manifest = json.loads(manifest_path.read_text("utf-8"))
    if manifest.get("release") != RELEASE or set(manifest["files"]) != set(ROOTS):
        raise RuntimeError("UNEXPECTED_RELEASE_MANIFEST")
    if sum(map(len, manifest["files"].values())) != 10:
        raise RuntimeError("INVALID_RELEASE_FILE_COUNT")
    if action == "apply":
        for site, destination in ROOTS.items():
            verify_tree(stage / site, manifest["files"][site])
            check_path(destination)
            if destination.exists():
                raise RuntimeError("PUBLIC_RELEASE_EXISTS_NO_OVERWRITE:" + str(destination))
            for parent in (destination.parent, destination.parent.parent):
                check_path(parent)
        for site, destination in ROOTS.items():
            destination.parent.mkdir(parents=True, exist_ok=True)
            check_path(destination.parent)
            os.rename(stage / site, destination)
            verify_tree(destination, manifest["files"][site])
            print("PUBLIC_MARKETING_RELEASE_INSTALLED=" + str(destination))
    elif action == "rollback":
        for site, destination in ROOTS.items():
            if destination.exists() or destination.is_symlink():
                verify_tree(destination, manifest["files"][site])
                shutil.rmtree(destination)
                print("OWNED_RELEASE_ONLY_ROLLED_BACK=" + str(destination))
    else:
        raise RuntimeError("UNKNOWN_ACTION")

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "build":
        build(Path(sys.argv[2]))
    elif len(sys.argv) == 3 and sys.argv[1] in ("apply", "rollback"):
        install(sys.argv[1], sys.argv[2])
    else:
        raise SystemExit("usage: script.py build OUT | apply|rollback RUN_ID")
