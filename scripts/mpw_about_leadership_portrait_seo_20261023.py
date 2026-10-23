#!/usr/bin/env python3
"""Guarded, one-file MojPlayWin /about/ leadership portrait and identity SEO release.

The exact static file is routed to /about/ by the existing .htaccess rules.
No other page, template, redirect, or deployment target is changed.
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
ABOUT = ROOT / "design-preview-20261017/mpw-ten-editorials-20261018/pages/about.html"
ROUTES = ROOT / ".htaccess"
MARK = "MPW_ABOUT_LEADERSHIP_PORTRAIT_SEO_20261023_V1"
PORTRAIT = "/mojtaba.roozegar/assets/personal_site/official_profile_20261016/portrait.2935ce8cb70d.webp"
PERSON_ID = "https://mojplaywin.com/mojtaba.roozegar/#person"
ALIASES = [
    "مجتبی روزگار", "روزگار", "Roozegar", "Mojtaba Roozegar",
    "Mojtaba Rozegar", "Rozegar", "دکتر مجتبی روزگار",
    "Dr. Mojtaba Roozegar", "Dr. Mojtaba Rozegar", "Dr.mojtaba.rozegar",
]

FIGURE = '''<figure id="mpw-leadership-official-photo-20261023" class="mpw-leadership-official-photo">
      <img src="'''+PORTRAIT+'''" width="865" height="744" loading="lazy" decoding="async" alt="Mojtaba Roozegar (مجتبی روزگار), founder and CEO of MojPlayWin — official portrait">
      <figcaption>Mojtaba Roozegar · Founder &amp; Chief Executive Officer</figcaption>
    </figure>'''
STYLE = '''<style id="mpw-leadership-photo-style-20261023">
#leadership .mpw-leadership-official-photo{width:min(100%,480px);margin:1.2rem auto 1.7rem;text-align:center;box-sizing:border-box}
#leadership .mpw-leadership-official-photo img{display:block;width:100%;height:auto;max-height:520px;object-fit:contain;box-sizing:border-box;border:1px solid #c5a465;border-radius:18px;background:#141414;box-shadow:0 12px 36px rgba(0,0,0,.35)}
#leadership .mpw-leadership-official-photo figcaption{color:#f0d39c;font-size:.9rem;line-height:1.5;margin:.65rem auto 0}
@media(max-width:640px){#leadership .mpw-leadership-official-photo{width:100%;max-width:360px;margin:1rem auto 1.35rem}#leadership .mpw-leadership-official-photo img{max-height:440px}}
</style>'''


def fail(message: str) -> None:
    raise RuntimeError(message)


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def leadership_span(document: str) -> tuple[int, int]:
    match = re.search(r'<section\b[^>]*\bid="leadership"[^>]*>', document)
    if not match or document.count('id="leadership"') != 1:
        fail("Cannot uniquely identify the pictured leadership section")
    end = document.find("</section>", match.end())
    if end == -1:
        fail("Leadership section has no closing tag")
    return match.start(), end + len("</section>")


def update_schema(document: str) -> str:
    pattern = re.compile(r'(<script\b[^>]*type="application/ld\+json"[^>]*>)([\s\S]*?)(</script>)', re.I)
    scripts = list(pattern.finditer(document))
    about = []
    for match in scripts:
        try:
            data = json.loads(match.group(2))
        except json.JSONDecodeError:
            fail("Existing JSON-LD is malformed")
        if data.get("@type") == "AboutPage":
            about.append((match, data))
    if len(about) != 1:
        fail("Expected exactly one existing AboutPage schema")
    match, data = about[0]
    if data.get("url") != "https://mojplaywin.com/about/":
        fail("AboutPage schema URL unexpectedly changed")
    org = data.get("mainEntity")
    if not isinstance(org, dict) or org.get("name") != "MojPlayWin":
        fail("AboutPage organization unexpectedly changed")
    person = org.get("founder")
    if not isinstance(person, dict) or person.get("name") != "Mojtaba Roozegar":
        fail("Founder identity unexpectedly changed")
    data["@id"] = "https://mojplaywin.com/about/#webpage"
    org["@id"] = "https://mojplaywin.com/#organization"
    person.update({
        "@id": PERSON_ID,
        "alternateName": ALIASES,
        "honorificPrefix": "Dr.",
        "jobTitle": "Founder and Chief Executive Officer",
        "image": "https://mojplaywin.com" + PORTRAIT,
        "sameAs": ["https://zomorodmelal.ir/authors/mojtaba-rozegar/"],
    })
    content = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return document[:match.start(2)] + content + document[match.end(2):]


def compose(document: str) -> str:
    if MARK in document or "mpw-leadership-official-photo-20261023" in document:
        fail("Portrait patch already installed")
    if document.count('rel="canonical" href="https://mojplaywin.com/about/"') != 1:
        fail("Self-canonical changed")
    if document.count("MPW_ABOUT_COMPANY_SEMANTIC_20261019_V2") != 1:
        fail("Existing approved About edition missing")
    if document.count(PORTRAIT) != 1 or document.count('id="mpw-founder-spotlight-20261019"') != 1:
        fail("Original official portrait is not present in the founder introduction")
    start, end = leadership_span(document)
    section = document[start:end]
    anchor = '<h2 id="leadership-title">Mojtaba Roozegar</h2>'
    if section.count(anchor) != 1 or '07 / FOUNDER &amp; LEADERSHIP' not in section:
        fail("The user-identified section 07 changed")
    section = section.replace(anchor, FIGURE + "\n    " + anchor, 1)
    document = document[:start] + section + document[end:]
    if document.count("</head>") != 1 or document.count("</body>") != 1:
        fail("Invalid HTML document")
    document = update_schema(document)
    document = document.replace("</head>", STYLE + "\n</head>", 1)
    document = document.replace("</body>", "<!-- " + MARK + " -->\n</body>", 1)
    verify(document)
    return document


def verify(document: str) -> None:
    start, end = leadership_span(document)
    section = document[start:end]
    if not (section.index('id="mpw-leadership-official-photo-20261023"')
            < section.index('id="leadership-title"')):
        fail("Official portrait is not before the exact leadership text")
    if document.count(MARK) != 1 or document.count(PORTRAIT) != 3:
        # Original founder image, new visible image, existing schema Person image.
        fail("Portrait/schema output count mismatch")
    if document.count('class="mpw-profile-indicator"') != 30 or document.count('class="mpw-seven-item"') != 6:
        fail("Unrelated profile/gallery sections changed")
    if '"alternateName"' not in document or 'Dr.mojtaba.rozegar' not in document:
        fail("Identity aliases are missing")


def backup_paths(run: str) -> tuple[Path, Path]:
    if not re.fullmatch(r"[0-9]{9,20}", run):
        fail("Invalid GitHub Actions run id")
    return (ROOT.parent / (".mpw-about-leadership-" + run + ".bak"),
            ROOT.parent / (".mpw-about-leadership-" + run + ".json"))


def guard() -> None:
    if ROOT.is_symlink() or ROOT.resolve() != ROOT or not ROOT.is_dir():
        fail("Unexpected MojPlayWin root")
    if not ABOUT.is_file() or ABOUT.is_symlink() or not ROUTES.is_file():
        fail("Exact static About page or routing file unavailable")
    rules = ROUTES.read_text("utf-8", errors="replace")
    if "mpw-ten-editorials-20261018/pages/about.html" not in rules:
        fail("Public About route no longer maps to the pinned file")


def atomic(path: Path, data: bytes, mode: int) -> None:
    descriptor, tmp = tempfile.mkstemp(prefix=".mpw-leadership-", dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.lexists(tmp):
            os.unlink(tmp)


def install(run: str) -> None:
    guard()
    backup, manifest = backup_paths(run)
    if backup.exists() or manifest.exists():
        fail("Backup run already exists")
    old = ABOUT.read_bytes()
    new = compose(old.decode("utf-8")).encode("utf-8")
    mode = stat.S_IMODE(ABOUT.stat().st_mode)
    record = {"run": run, "old": digest(old), "new": digest(new)}
    with backup.open("xb") as file:
        os.fchmod(file.fileno(), 0o600)
        file.write(old)
        file.flush()
        os.fsync(file.fileno())
    with manifest.open("x") as file:
        os.fchmod(file.fileno(), 0o600)
        json.dump(record, file)
        file.flush()
        os.fsync(file.fileno())
    if digest(ABOUT.read_bytes()) != record["old"]:
        fail("Concurrent change before install")
    atomic(ABOUT, new, mode)
    if digest(ABOUT.read_bytes()) != record["new"]:
        fail("Post-write hash verification failed")
    print("MPW_ABOUT_LEADERSHIP_PUBLISHED=" + json.dumps(record))


def rollback(run: str) -> None:
    guard()
    backup, manifest = backup_paths(run)
    record = json.loads(manifest.read_text("utf-8"))
    old = backup.read_bytes()
    if record["run"] != run or digest(old) != record["old"]:
        fail("Rollback backup mismatch")
    if digest(ABOUT.read_bytes()) != record["new"]:
        fail("Site changed after publication; refusing destructive rollback")
    atomic(ABOUT, old, stat.S_IMODE(ABOUT.stat().st_mode))
    if digest(ABOUT.read_bytes()) != record["old"]:
        fail("Rollback verification failed")
    print("MPW_ABOUT_LEADERSHIP_ROLLBACK=VERIFIED")


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("install", "rollback"):
        fail("Usage: install|rollback GITHUB_RUN_ID")
    {"install": install, "rollback": rollback}[sys.argv[1]](sys.argv[2])
