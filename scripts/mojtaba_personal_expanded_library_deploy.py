#!/usr/bin/env python3
"""Safely append rich original educational and professional content to five personal V17 pages.

The original academic biography, 50 editorial items, original photo collections,
and unrelated Django apps/routes are protected with allowlists and backups.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import shutil

APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
PAGES = {
    "home": "home.html",
    "about": "about.html",
    "resume": "resume.html",
    "activities": "activities.html",
    "posts": "posts.html",
}
MARKER = 'id="mpw-personal-expanded-20261016"'
OLD_ACADEMIC = 'id="mpw-academic-profile-20261016"'
OLD_EDITORIAL = 'id="mpw-fifty-editorials-20261015"'
OLD_PHOTOS = 'id="mpw-new-originals-20261015-b"'
ROUTES = {
    "home": "",
    "about": "about/",
    "resume": "resume/",
    "activities": "works-activities/",
    "posts": "blog/",
}
CSS = """
<style>
.mpw-expanded{box-sizing:border-box;clear:both;margin:36px auto;max-width:1180px;width:100%;padding:clamp(18px,3vw,40px);border:4px solid #c99c48;border-radius:18px;background:#131313;color:#f5eee1;box-shadow:0 18px 45px rgba(0,0,0,.28)}
.mpw-expanded *{box-sizing:border-box}
.mpw-expanded .mx-kicker{font:700 12px/1.6 system-ui,sans-serif;letter-spacing:.13em;text-transform:uppercase;color:#e1bd77}
.mpw-expanded h2{font:600 clamp(27px,4vw,43px)/1.21 Georgia,serif;color:#f4d499;margin:10px 0 16px}
.mpw-expanded .mx-intro{font:400 clamp(16px,2vw,20px)/1.7 system-ui,sans-serif;color:#e9e0d2;max-width:980px}
.mpw-expanded .mx-sections{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;margin:28px 0}
.mpw-expanded .mx-section{min-width:0;padding:22px;border:2px solid #806435;border-radius:12px;background:#1d1c1a}
.mpw-expanded .mx-section h3{font:600 clamp(19px,2.3vw,25px)/1.3 Georgia,serif;margin:0 0 13px;color:#f4d499}
.mpw-expanded .mx-section p{font:400 15px/1.85 system-ui,sans-serif;color:#e0dacd;margin:0 0 12px;overflow-wrap:anywhere}
.mpw-expanded .mx-section p:last-child{margin-bottom:0}
.mpw-expanded .mx-nav{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0}
.mpw-expanded .mx-nav a{display:inline-block;padding:9px 13px;background:#26221d;color:#f4d499;border:1px solid #b48b44;border-radius:7px;font:600 13px/1.4 system-ui,sans-serif;text-decoration:none}
.mpw-expanded .mx-nav a:hover,.mpw-expanded .mx-nav a:focus{background:#43341e;text-decoration:underline}
.mpw-expanded .mx-note{font:400 12px/1.8 system-ui,sans-serif;color:#cbbfa9;margin:18px 0 0}
@media(max-width:760px){.mpw-expanded{padding:17px 13px;border-width:3px}.mpw-expanded .mx-sections{grid-template-columns:1fr;gap:13px}.mpw-expanded .mx-section{padding:17px}}
</style>"""

def read_content(path: Path) -> dict:
    if not path.is_file() or path.is_symlink():
        raise ValueError("Missing or unsafe content source")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (data.get("version"), data.get("marker"), data.get("language")) != (
        1, "mpw-personal-expanded-20261016", "en"
    ):
        raise ValueError("Unexpected content metadata")
    if set(data.get("pages", {})) != set(PAGES):
        raise ValueError("Pages must exactly match approved five-page allowlist")
    titles = set()
    for page, record in data["pages"].items():
        if set(record) != {"kicker", "title", "intro", "sections", "note"}:
            raise ValueError("Unexpected page schema")
        if not (5 <= len(record["sections"]) <= 10):
            raise ValueError("Insufficient substantive sections: " + page)
        for field in ("kicker", "title", "intro", "note"):
            if not isinstance(record[field], str) or len(record[field]) < 20:
                raise ValueError("Missing page introduction or disclosure: " + page)
        for section in record["sections"]:
            if set(section) != {"title", "paragraphs"}:
                raise ValueError("Unexpected section schema")
            title = section["title"]
            if not isinstance(title, str) or len(title) < 16 or title in titles:
                raise ValueError("Invalid or duplicated section title")
            titles.add(title)
            if not isinstance(section["paragraphs"], list) or len(section["paragraphs"]) != 2:
                raise ValueError("Each section needs exactly two substantial paragraphs")
            if any(not isinstance(p, str) or len(p) < 190 for p in section["paragraphs"]):
                raise ValueError("Insufficient original educational prose: " + title)
    return data

def render_section(page: str, data: dict) -> str:
    if page not in PAGES:
        raise ValueError("Not allowed")
    part = data["pages"][page]
    esc = lambda value: html.escape(value, quote=True)
    out = [
        '<section id="mpw-personal-expanded-20261016" class="mpw-expanded" aria-label="Expanded professional and educational content">',
        CSS,
        '<span class="mx-kicker">' + esc(part["kicker"]) + '</span>',
        "<h2>" + esc(part["title"]) + "</h2>",
        '<p class="mx-intro">' + esc(part["intro"]) + "</p>",
        '<div class="mx-sections">',
    ]
    for section in part["sections"]:
        out.append('<article class="mx-section">')
        out.append("<h3>" + esc(section["title"]) + "</h3>")
        for paragraph in section["paragraphs"]:
            out.append("<p>" + esc(paragraph) + "</p>")
        out.append("</article>")
    out.append("</div>")
    out.append('<nav class="mx-nav" aria-label="Personal site sections">')
    for key, label in [
        ("home", "Home"), ("about", "About"), ("resume", "Resume"),
        ("activities", "Work & Activities"), ("posts", "Journal")
    ]:
        out.append(
            '<a href="/mojtaba.roozegar/' + ROUTES[key] + '">' + esc(label) + "</a>"
        )
    out.append("</nav>")
    out.append('<p class="mx-note">' + esc(part["note"]) + "</p>")
    out.append("</section>")
    return "\n".join(out)

def patch(page: str, old: str, data: dict) -> str:
    if page not in PAGES:
        raise ValueError("Cannot touch unapproved page")
    if MARKER in old:
        raise ValueError("Expansion already present; not installing twice")
    for marker in (OLD_ACADEMIC, OLD_EDITORIAL, OLD_PHOTOS):
        if old.count(marker) != 1:
            raise ValueError("Protected prior content missing or duplicated: " + marker)
    start = "{% block content %}"
    if old.count(start) != 1:
        raise ValueError("Ambiguous Django content insertion point")
    begin = old.index(start) + len(start)
    end = old.find("{% endblock %}", begin)
    if end < 0:
        raise ValueError("Missing endblock")
    result = old[:end] + "\n" + render_section(page, data) + "\n" + old[end:]
    for marker in (MARKER, OLD_ACADEMIC, OLD_EDITORIAL, OLD_PHOTOS):
        if result.count(marker) != 1:
            raise ValueError("Non-additive change refused")
    return result

def get_templates(app: Path) -> dict[str, str]:
    if app.is_symlink() or not (app / "manage.py").is_file():
        raise ValueError("Personal V17 application unavailable")
    base = app / "templates/personal_site/core"
    result = {}
    for page, filename in PAGES.items():
        path = base / filename
        if not path.is_file() or path.is_symlink() or path.resolve() != path:
            raise ValueError("Unsafe or missing template")
        result[page] = path.read_text(encoding="utf-8")
    return result

def rollback(app: Path, backup: Path) -> None:
    if not backup.is_dir() or backup.is_symlink():
        raise ValueError("Backup directory missing")
    get_templates(app)
    for name in PAGES.values():
        source = backup / name
        if not source.is_file() or source.is_symlink():
            raise ValueError("Incomplete backup")
    for name in PAGES.values():
        dest = app / "templates/personal_site/core" / name
        tmp = dest.with_name(dest.name + ".rich-rollback")
        shutil.copy2(backup / name, tmp)
        os.replace(tmp, dest)
    if (app / "tmp").is_dir():
        (app / "tmp/restart.txt").touch()
    print("RICH_LIBRARY_ROLLBACK_FIVE_PAGES_OK=yes", flush=True)

def main(args) -> None:
    if args.mode == "rollback":
        rollback(args.app, args.backup)
        return
    data = read_content(args.content)
    old = get_templates(args.app)
    new = {page: patch(page, before, data) for page, before in old.items()}
    print("RICH_LIBRARY_PROTECTED_TEMPLATE_CHECK=yes", flush=True)
    if args.mode == "check":
        return
    if args.backup is None or args.backup.exists() or args.backup.is_symlink():
        raise ValueError("A fresh backup destination is required")
    args.backup.mkdir(parents=True, mode=0o700)
    for page, filename in PAGES.items():
        target = args.backup / filename
        target.write_text(old[page], encoding="utf-8")
        target.chmod(0o600)
        print("BACKUP=" + filename + " SHA256=" + hashlib.sha256(old[page].encode()).hexdigest(), flush=True)
    if len(list(args.backup.glob("*.html"))) != 5:
        raise ValueError("Incomplete backups")
    changed = []
    try:
        for page, filename in PAGES.items():
            dest = args.app / "templates/personal_site/core" / filename
            tmp = dest.with_name(filename + ".rich-new")
            if tmp.exists() or tmp.is_symlink():
                raise ValueError("Unclean temporary path")
            tmp.write_text(new[page], encoding="utf-8")
            os.chmod(tmp, dest.stat().st_mode & 0o777)
            os.replace(tmp, dest)
            changed.append(page)
    except BaseException:
        for page in changed:
            shutil.copy2(args.backup / PAGES[page], args.app / "templates/personal_site/core" / PAGES[page])
        raise
    if (args.app / "tmp").is_dir():
        (args.app / "tmp/restart.txt").touch()
    print("RICH_LIBRARY_FIVE_PAGES_INSTALLED=yes", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["check", "install", "rollback"])
    parser.add_argument("--app", type=Path, default=APP)
    parser.add_argument("--content", type=Path)
    parser.add_argument("--backup", type=Path)
    options = parser.parse_args()
    if options.mode == "rollback" and options.backup is None:
        parser.error("--backup required for rollback")
    if options.mode != "rollback" and options.content is None:
        parser.error("--content required")
    main(options)
