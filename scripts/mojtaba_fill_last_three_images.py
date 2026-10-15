#!/usr/bin/env python3
"""Add original, unmodified owner photos to the three already-published V17 personal pages.

Non-destructive. Changes only these three existing HTML templates. Requires all 10
owner originals previously deployed. Backups and rollback. No new media generated.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import os
from pathlib import Path
import re
import shutil
import sys

APP = Path("/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17")
TEMPLATES = APP / "templates/personal_site/core"
STATIC = APP / "static/personal_site/owner_gallery_20261015"
MARKER = 'id="mpw-three-photo-strip-20261015"'
ORIGINAL_SECTION = 'id="mpw-inner-content-20261015"'

# Filenames and captions map exclusively to the ten unmodified owner originals.
PAGES = {
    "resume": [
        (2, "Agribusiness executive work", "Branded editorial photograph provided by the founder"),
        (3, "Presentation and project leadership", "Branded editorial photograph provided by the founder"),
        (8, "MojPlayWin founder portrait", "Branded editorial photograph provided by the founder"),
    ],
    "memories": [
        (9, "A personal portrait", "Owner-provided editorial portrait, not a documentary image of a location or event"),
        (7, "Professional roots and experience", "Owner-provided branded editorial portrait, not a photograph of Persepolis"),
    ],
    "stories": [
        (1, "Meet the founder", "Owner-provided editorial portrait; not an illustration of a fictional scene"),
        (8, "Writer and entrepreneur", "Owner-provided editorial portrait; fictional characters are not depicted"),
    ],
}

CSS = """<style>
.mpw-photo-panel {margin:32px 0 35px;padding:22px 20px;background:#172c40;border:1px solid #a98e62;border-radius:10px;color:#ede5d9}
.mpw-photo-panel * {box-sizing:border-box}
.mpw-photo-panel .mpw-photo-title {font:400 clamp(22px,3vw,31px)/1.2 Georgia,'Times New Roman',serif;color:#f4ead8;margin:0 0 9px}
.mpw-photo-panel .mpw-photo-intro {font-size:14px;line-height:1.65;color:#d2d9df;margin:0 0 16px}
.mpw-photo-panel .mpw-photo-grid {display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
.mpw-photo-panel.mpw-photo-two .mpw-photo-grid {grid-template-columns:repeat(2,minmax(0,1fr))}
.mpw-photo-panel figure {margin:0;background:#101e2f;border:1px solid rgba(213,176,108,.3);border-radius:8px;overflow:hidden}
.mpw-photo-panel a {display:block}
.mpw-photo-panel a:focus-visible {outline:3px solid #e6c178;outline-offset:-3px}
.mpw-photo-panel img {display:block;width:100%;height:295px;object-fit:contain;background:#101e2f}
.mpw-photo-panel figcaption {color:#ebe1cf;padding:12px 13px 15px;font-size:14px;line-height:1.5}
.mpw-photo-panel figcaption strong {display:block;color:#f5efe2;margin-bottom:4px;font-size:15px}
@media (max-width:650px) {
 .mpw-photo-panel {padding:15px;margin:24px 0}
 .mpw-photo-panel .mpw-photo-grid,.mpw-photo-panel.mpw-photo-two .mpw-photo-grid {grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}
 .mpw-photo-panel img {height:200px}
 .mpw-photo-panel figcaption {font-size:12px;padding:9px}
 .mpw-photo-panel figcaption strong {font-size:13px}
}
</style>"""

def static_expression(number: int) -> str:
    if number not in range(1, 11):
        raise ValueError("Photo outside original ten")
    return (
        "{% static 'personal_site/owner_gallery_20261015/photo-"
        + f"{number:02d}" + ".jpg' %}"
    )

def block_for(page: str) -> str:
    if page not in PAGES:
        raise ValueError("Unsupported page")
    photos = PAGES[page]
    cards = []
    for number, title, note in photos:
        src = static_expression(number)
        cards.append(
            '<figure><a href="' + src + '" target="_blank" rel="noopener noreferrer"'
            ' aria-label="Open original photograph ' + str(number) + '">'
            '<img src="' + src + '" alt="' + html.escape(title, quote=True)
            + '" width="480" height="600" loading="lazy" decoding="async"></a>'
            '<figcaption><strong>' + html.escape(title)
            + '</strong>' + html.escape(note) + '</figcaption></figure>'
        )
    intro = (
        "Every image below is one of the ten original photographs supplied by the founder. "
        "The photographs remain unaltered, and no scene is used as documentary proof of an event."
    )
    return (
        '<div id="mpw-three-photo-strip-20261015" class="mpw-photo-panel'
        + (' mpw-photo-two' if len(photos) == 2 else "") + '">'
        + CSS + '<h3 class="mpw-photo-title">A visual perspective</h3>'
        + '<p class="mpw-photo-intro">' + intro + '</p>'
        + '<div class="mpw-photo-grid">' + "".join(cards) + '</div></div>'
    )

def patch(page: str, original: str) -> str:
    if page not in PAGES:
        raise ValueError("Non-allowlisted page")
    if original.count(ORIGINAL_SECTION) != 1 or original.count("{% load static %}") != 1:
        raise ValueError("Unexpected existing published V17 template")
    if MARKER in original:
        raise ValueError("Photo strip is already installed")
    anchor = '<p class="mpw-intro">'
    pos = original.find(anchor)
    if pos < 0 or original.find(anchor, pos + len(anchor)) >= 0:
        raise ValueError("Intro anchor missing or ambiguous")
    end = original.find("</p>", pos)
    if end < 0 or end-pos > 2000:
        raise ValueError("Intro ending not found")
    end += 4
    changed = original[:end] + "\n" + block_for(page) + "\n" + original[end:]
    if changed.count(MARKER) != 1:
        raise ValueError("Marker count invalid")
    for number, _, _ in PAGES[page]:
        if changed.count("photo-" + f"{number:02d}" + ".jpg") != 2:
            raise ValueError("Photo source must appear once as image and once as link")
    return changed

def originals_exist() -> None:
    if not STATIC.is_dir() or STATIC.is_symlink():
        raise ValueError("Original static source folder absent")
    for i in range(1, 11):
        f = STATIC / f"photo-{i:02d}.jpg"
        if not f.is_file() or f.is_symlink():
            raise ValueError("Original photo missing " + f.name)

def current_templates() -> dict[str, str]:
    files = {}
    for name in PAGES:
        f = TEMPLATES / (name + ".html")
        if not f.is_file() or f.is_symlink() or f.resolve() != f:
            raise ValueError("Unsafe template file " + name)
        files[name] = f.read_text(encoding="utf-8")
    return files

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("check", "install", "rollback"))
    parser.add_argument("--backup-dir", type=Path, required=True)
    args = parser.parse_args()
    if APP.is_symlink() or not (APP / "manage.py").is_file():
        raise SystemExit("Personal V17 path not verified")
    backup = args.backup_dir
    if args.mode == "rollback":
        if not backup.is_dir() or backup.is_symlink():
            raise SystemExit("No safe backup")
        for page in PAGES:
            file = backup / (page + ".html")
            if not file.is_file() or file.is_symlink():
                raise SystemExit("Missing backup " + page)
        for page in PAGES:
            file = TEMPLATES / (page + ".html")
            tmp = file.with_name(file.name + ".photos-restore")
            shutil.copy2(backup / (page + ".html"), tmp)
            os.replace(tmp, file)
        if (APP / "tmp").is_dir():
            (APP / "tmp/restart.txt").touch()
        print("RESTORED_THREE_ORIGINAL_TEMPLATES=yes")
        return

    originals_exist()
    current = current_templates()
    result = {page: patch(page, data) for page, data in current.items()}
    print("ORIGINAL_PHOTOS_AVAILABLE=10")
    print("PERSONAL_PHOTO_PAGES_PREPARED=3")
    if args.mode == "check":
        return
    if backup.exists():
        raise SystemExit("Refusing to overwrite existing backup directory")
    backup.mkdir(parents=True, mode=0o700)
    for page, data in current.items():
        file = backup / (page + ".html")
        file.write_text(data, encoding="utf-8")
        file.chmod(0o600)
        print("BACKED_UP=" + page + " sha256=" + hashlib.sha256(data.encode()).hexdigest())
    updated = []
    try:
        for page, rendered in result.items():
            file = TEMPLATES / (page + ".html")
            tmp = file.with_name(file.name + ".photos-install")
            if tmp.exists(): raise RuntimeError("Temporary path already exists")
            tmp.write_text(rendered, encoding="utf-8")
            os.chmod(tmp, file.stat().st_mode & 0o777)
            os.replace(tmp, file)
            updated.append(page)
    except BaseException:
        for page in updated:
            shutil.copy2(backup / (page + ".html"), TEMPLATES / (page + ".html"))
        raise
    if (APP / "tmp").is_dir():
        (APP / "tmp/restart.txt").touch()
    print("THREE_PHOTO_PAGES_INSTALLED=yes")
    print("BACKUP_DIRECTORY=" + str(backup))

if __name__ == "__main__":
    main()
