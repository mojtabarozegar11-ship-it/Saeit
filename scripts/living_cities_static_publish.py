#!/usr/bin/env python3
"""Publish owned Living Cities browser build without exposing private Django source.

Static offline progress only; account entitlements/physical codes/MOJ1 are NOT enabled.
Designed for an existing root Passenger application that shadows nested WSGI apps.
"""
from pathlib import Path
import html
import json
import os
import re
import secrets
import shutil
import sys

HOME=Path("/home/zomorod2")
SOURCE_SHA="b3fe1b772368f3f0874481ab88ad82862bd24de2"
RELEASE=HOME/".private/living-cities-app/releases"/SOURCE_SHA
PUBLIC=HOME/"public_html/living-cities"
ROOT=HOME/".private/living-cities-app"
MARKER="LC-STATIC-BROWSER-PUBLIC-"+SOURCE_SHA

def require(test,message):
    if not test:raise RuntimeError(message)

def guard():
    require(os.geteuid()==HOME.stat().st_uid,"unexpected_host_user")
    require(not PUBLIC.is_symlink() and (HOME/"public_html").is_dir(),"bad_public_root")
    require((RELEASE/"LC_VALIDATED.json").is_file(),"private_django_source_not_validated")
    require((RELEASE/"staticfiles/living_cities/app.mjs").is_file(),"missing_actual_game_client")

def publish():
    guard()
    require(not PUBLIC.exists(),"public_path_already_exists")
    stage=HOME/"public_html"/(".living-cities-static-"+SOURCE_SHA[:9]+".pending")
    require(not stage.exists() and not stage.is_symlink(),"staging_conflict")
    stage.mkdir(mode=0o700)
    try:
        shutil.copytree(RELEASE/"staticfiles/living_cities",stage/"static/living_cities")
        template=(RELEASE/"apps/living_cities/templates/living_cities/play.html").read_text()
        require('LIVING CITIES' in template and "{% load static %}" in template,"unknown_game_template")
        template=template.replace("{% load static %}","")
        template=template.replace("{% static 'living_cities/style.css' %}","/living-cities/static/living_cities/style.css")
        template=template.replace("{% static 'living_cities/app.mjs' %}","/living-cities/static/living_cities/app.mjs")
        template=template.replace("{{ csrf_token }}","")
        require("{%" not in template and "{{" not in template,"template_unresolved")
        notice=('<aside role="status" style="position:relative;z-index:1200;text-align:center;'
                'background:#182c3b;color:#fff;padding:8px 12px;font:14px sans-serif">'
                'Offline progress is saved on this device. Account sync, product-code verification '
                'and MOJ1 Gem payments are unavailable in this edition.</aside>')
        template=template.replace("<body>","<body>\n"+notice,1)
        require("/living-cities/static/living_cities/app.mjs" in template,"missing_static_entry")
        (stage/"play").mkdir()
        (stage/"play/index.html").write_text(template)
        (stage/"index.html").write_text('<!doctype html><html lang="en"><meta charset="utf-8">'
             '<meta http-equiv="refresh" content="0;url=/living-cities/play/">'
             '<title>Living Cities</title><a href="/living-cities/play/">Play Living Cities</a></html>')
        (stage/".htaccess").write_text(
            "# "+MARKER+"\n"
            "PassengerEnabled off\n"
            "Options -Indexes\n"
            "DirectoryIndex index.html\n")
        (stage/"LC-OWNER.txt").write_text(MARKER+"\n")
        for path in stage.rglob("*"):
            if path.is_file():path.chmod(0o644)
            elif path.is_dir():path.chmod(0o755)
        stage.chmod(0o755)
        stage.rename(PUBLIC)
        print("LIVING_CITIES_STATIC_ORIGINAL_GAME_PUBLISHED=PASS")
        print("LIVING_CITIES_ACCOUNT_AND_MOJ1_STILL_DISABLED=TRUE")
    except BaseException:
        if stage.exists():shutil.rmtree(stage)
        raise

def rollback():
    guard()
    if not PUBLIC.exists():
        print("NO_OWNED_PUBLIC_BROWSER_GAME")
        return
    require(PUBLIC.is_dir() and not PUBLIC.is_symlink(),"not_our_directory")
    marker=PUBLIC/"LC-OWNER.txt"
    require(marker.is_file() and marker.read_text().strip()==MARKER,"ownership_marker_mismatch")
    quarantine=ROOT/"quarantine"/("static-unpublished-"+SOURCE_SHA+"-"+secrets.token_hex(6))
    quarantine.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    PUBLIC.rename(quarantine)
    print("LIVING_CITIES_STATIC_PUBLIC_ROUTE_ROLLED_BACK=PASS")

if __name__=="__main__":
    require(len(sys.argv)==2 and sys.argv[1] in ("publish","rollback"),"unsupported_mode")
    {"publish":publish,"rollback":rollback}[sys.argv[1]]()
