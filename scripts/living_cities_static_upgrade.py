#!/usr/bin/env python3
"""Atomic, rollback-capable upgrade of the OWNED Living Cities browser edition.

All writes restricted to the game's preexisting public folder and private
rollback/staging folders. Never writes the main Saeit app, user DBs, or site rules.
"""
import hashlib
import io
import os
from pathlib import Path
import re
import secrets
import shutil
import sys
import tarfile

HOME=Path("/home/zomorod2")
SOURCE="50a44804d1b90df1bd6098ca75da2c3af6632e18"
OLD="b3fe1b772368f3f0874481ab88ad82862bd24de2"
ROOT=HOME/".private/living-cities-app"
RELEASE=ROOT/"upgrades"/SOURCE
ARCHIVE=RELEASE/"source.tgz"
DOCROOT=HOME/"public_html"
PUBLIC=DOCROOT/"living-cities"
STAGE=DOCROOT/(".living-cities-upgrade-"+SOURCE[:10]+".stage")
BACKUP=ROOT/("original-browser-release-"+SOURCE[:10])
NEW_MARKER="LC-STATIC-BROWSER-PUBLIC-"+SOURCE
OLD_MARKER="LC-STATIC-BROWSER-PUBLIC-"+OLD
ALLOWED_EXTENSIONS={".mjs",".js",".css",".png",".webp",".svg",".jpg",".jpeg",".woff2",".json"}
NEW_FILES=["app.mjs","tycoon-panel.mjs","tycoon.mjs","progression.mjs","sim.mjs","render.mjs","tycoon.css","style.css","tycoon-idempotency.mjs"]

def require(ok,message):
    if not ok: raise RuntimeError(message)

def check_layout():
    require(os.geteuid()==HOME.stat().st_uid,"cpanel_wrong_owner")
    for path in (HOME,DOCROOT,ROOT,RELEASE,PUBLIC,STAGE,BACKUP):
        require(not path.is_symlink(),"symlink_in_scoped_path:"+path.name)
    require(DOCROOT.is_dir() and ROOT.is_dir(),"unexpected_root")
    require(ARCHIVE.is_file() and not ARCHIVE.is_symlink(),"new_source_archive_absent")
    require(ARCHIVE.stat().st_size < 4194304,"oversized_source")
    require(not (PUBLIC/"passenger_wsgi.py").exists(),"will_not_overwrite_django_app")

def marker(folder):
    p=folder/"LC-OWNER.txt"
    require(p.is_file() and not p.is_symlink(),"owner_marker_missing")
    return p.read_text().strip()

def extracted_bytes():
    raw=ARCHIVE.read_bytes()
    assert len(raw)>10_000
    files={}
    with tarfile.open(fileobj=io.BytesIO(raw),mode="r:gz") as tar:
        for entry in tar.getmembers():
            name=Path(entry.name)
            require(not name.is_absolute() and ".." not in name.parts and
                    (entry.isdir() or entry.isfile()),"invalid_archive_entry")
            if entry.isfile() and str(name).startswith("apps/living_cities/static/living_cities/"):
                rel=name.relative_to("apps/living_cities/static/living_cities")
                if rel.name=="index.html":
                    continue  # Standalone source sample; production serves only vetted Django-template HTML.
                require(len(rel.parts)==1 and rel.suffix in ALLOWED_EXTENSIONS, "unapproved_static_file")
                require(entry.size<400000,"oversized_game_asset")
                files[rel.name]=tar.extractfile(entry).read()
            if entry.isfile() and str(name)=="apps/living_cities/templates/living_cities/play.html":
                require(entry.size<80000,"oversized_html")
                files["play.html"]=tar.extractfile(entry).read()
    require(all(name in files for name in NEW_FILES+["play.html"]),"incomplete_game_build")
    for name in NEW_FILES:
        require(files[name] and b"\x00" not in files[name],"unusable_asset:"+name)
    require(b'businessRoadmap' in files["tycoon-panel.mjs"],"mission_engine_not_integrated")
    require(b'document.documentElement.dataset.lcEdition' in files["app.mjs"],"offline_gate_not_integration_tested")
    return files

def html_for_browser(original):
    template=original.decode("utf-8")
    require("<html lang=\"en\">" in template and "{% load static %}" in template,"unexpected_template_version")
    template=template.replace("{% load static %}","")
    template=template.replace("{% static 'living_cities/style.css' %}","/living-cities/static/living_cities/style.css")
    template=template.replace("{% static 'living_cities/app.mjs' %}","/living-cities/static/living_cities/app.mjs")
    template=template.replace("{{ csrf_token }}","")
    template=template.replace('<html lang="en">','<html lang="en" data-lc-edition="browser">',1)
    require("{%" not in template and "{{" not in template,"unresolved_html_template_token")
    notice=('<aside class="lc-browser-notice" role="status" style="position:relative;z-index:1200;'
      'background:#182c3b;color:#fff;padding:8px 12px;font:13px system-ui,sans-serif;text-align:center">'
      'Play locally: progress stays on this device. Account sync, product-code verification '
      'and MOJ1 Gem payments are not available in this browser edition.</aside>')
    template=template.replace("<body>","<body>\n"+notice,1)
    return template.encode("utf-8")

def prepare():
    check_layout()
    require(PUBLIC.is_dir(),"live_original_missing")
    require(marker(PUBLIC)==OLD_MARKER,"unmanaged_live_game_cannot_upgrade")
    require(not STAGE.exists() and not BACKUP.exists(),"an_upgrade_is_already_prepared")
    files=extracted_bytes()
    STAGE.mkdir(mode=0o700)
    try:
        static=STAGE/"static/living_cities"
        static.mkdir(parents=True,mode=0o700)
        for name,data in files.items():
            if name=="play.html":continue
            if name in ("app.mjs","tycoon-panel.mjs"):
                txt=data.decode("utf-8")
                txt=txt.replace("/api/living-cities/","/living-cities/api/living-cities/")
                txt=txt.replace("/api/auth/","/living-cities/api/auth/")
                data=txt.encode("utf-8")
            (static/name).write_bytes(data)
        html=html_for_browser(files["play.html"])
        play=STAGE/"play"
        play.mkdir(mode=0o700)
        (play/"index.html").write_bytes(html)
        (STAGE/"index.html").write_text(
            '<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta http-equiv="refresh" content="0;url=/living-cities/play/">'
            '<title>Living Cities</title><a href="/living-cities/play/">Play Living Cities</a></html>')
        (STAGE/".htaccess").write_text(
            "# "+NEW_MARKER+"\nPassengerEnabled off\nOptions -Indexes\nDirectoryIndex index.html\n")
        (STAGE/"LC-OWNER.txt").write_text(NEW_MARKER+"\n")
        for p in STAGE.rglob("*"):
            require(not p.is_symlink(),"stage_link_rejected")
            p.chmod(0o644 if p.is_file() else 0o755)
        STAGE.chmod(0o755)
        require(b'data-lc-edition="browser"' in (play/"index.html").read_bytes(),"offline_mode_missing")
        require(b'businessRoadmap' in (static/"tycoon-panel.mjs").read_bytes(),"roadmap_missing")
        require(b'./progression.mjs' in (static/"tycoon-panel.mjs").read_bytes(),"roadmap_import_missing")
        print("LIVING_CITIES_NEW_PLAYABILITY_STAGE=PASS")
        print("LIVING_CITIES_STAGE_ASSETS="+str(len(files)-1))
        print("LIVING_CITIES_BROWSER_SAVES_PRESERVED=true")
    except Exception:
        if STAGE.exists():shutil.rmtree(STAGE)
        raise

def publish():
    require(PUBLIC.is_dir() and STAGE.is_dir(),"game_not_prepared")
    require(marker(PUBLIC)==OLD_MARKER and marker(STAGE)==NEW_MARKER,"unexpected_game_ownership")
    require(not BACKUP.exists() and not BACKUP.is_symlink(),"rollback_exists")
    try:
        PUBLIC.rename(BACKUP)
        try:
            STAGE.rename(PUBLIC)
        except BaseException:
            BACKUP.rename(PUBLIC)
            raise
    except BaseException:
        raise
    require(marker(PUBLIC)==NEW_MARKER,"published_marker_mismatch")
    print("LIVING_CITIES_NEW_GAME_PUBLISHED_ATOMICALLY=PASS")
    print("LIVING_CITIES_ORIGINAL_BROWSER_ROLLBACK_PRESERVED=true")

def rollback():
    require(PUBLIC.is_dir() and not PUBLIC.is_symlink() and BACKUP.is_dir() and
            not BACKUP.is_symlink(),"rollback_preconditions_missing")
    require(marker(PUBLIC)==NEW_MARKER and marker(BACKUP)==OLD_MARKER,"unmanaged_rollback_forbidden")
    failed=ROOT/("failed-upgrade-"+SOURCE[:10]+"-"+secrets.token_hex(5))
    PUBLIC.rename(failed)
    try:
        BACKUP.rename(PUBLIC)
    except BaseException:
        failed.rename(PUBLIC)
        raise
    print("LIVING_CITIES_ORIGINAL_GAME_RESTORED=PASS")

def verify():
    require(PUBLIC.is_dir() and marker(PUBLIC)==NEW_MARKER,"new_game_not_published")
    static=PUBLIC/"static/living_cities"
    require(all((static/n).is_file() for n in NEW_FILES),"new_game_asset_missing")
    require(b'data-lc-edition="browser"' in (PUBLIC/"play/index.html").read_bytes(),"not_offline")
    require(BACKUP.is_dir() and marker(BACKUP)==OLD_MARKER,"previous_release_backup_lost")
    print("LIVING_CITIES_FINAL_GAME_FILES_AND_ROLLBACK=PASS")

if __name__=="__main__":
    require(len(sys.argv)==2 and sys.argv[1] in ("prepare","publish","rollback","verify"),"invalid_mode")
    {"prepare":prepare,"publish":publish,"rollback":rollback,"verify":verify}[sys.argv[1]]()
