#!/usr/bin/env python3
"""Publish CI-verified Living Cities worldwide edition ONLY on mojplaywin.com.

Isolated asset installer: no root rewrite, Passenger, DB, Zomorod, or other
MojPlayWin path changes. Separate private staging, atomic public rename,
exact owner marker and reversible quarantine.
"""
from __future__ import annotations

import hashlib
import html
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import sys
import tarfile

HOME=Path("/home/zomorod2")
SITE=HOME/"mojplaywin.com"
SHA="27111d39d96f44638554233b8fcc129bea33752a"
SCOPE=HOME/".private/mpw-living-cities-global"
RELEASE=SCOPE/"releases"/SHA
SOURCE=RELEASE/"source.tgz"
STAGE=SCOPE/("stage-"+SHA)
TARGET=SITE/"living-cities"
OWNER="MPW-LIVING-CITIES-GLOBAL-20-LANG-"+SHA
EXPECTED_SOURCE_HASH=os.environ.get("LC_GLOBAL_ARCHIVE_SHA256","")
GAME_ROOT="apps/living_cities/static/living_cities"
SOURCE_PAGE="apps/living_cities/templates/living_cities/play.html"
ALLOWED_EXT={".mjs",".css"}
REQUIRED={
  "app.mjs","sim.mjs","render.mjs","style.css","tycoon.mjs",
  "tycoon-panel.mjs","tycoon-idempotency.mjs","tycoon.css",
  "progression.mjs","global-i18n.mjs","global-missions-i18n.mjs",
  "global-campaign.mjs","global-shell.mjs","global-theme.css"
}

def demand(ok,message):
    if not ok:raise RuntimeError(message)

def guard():
    demand(os.geteuid()==HOME.stat().st_uid,"wrong_cpanel_account")
    for item in (HOME,SITE,SCOPE,RELEASE,SOURCE,STAGE,TARGET):
        demand(not item.is_symlink(),"symlink_in_restricted_path:"+item.name)
    demand(SITE.is_dir() and (SITE/"passenger_wsgi.py").is_file() and
        (SITE/".htaccess").is_file(),"MojPlayWin_routing_layout_unexpected")
    demand(not TARGET.exists(),"target_route_already_exists_do_not_overwrite")
    demand(not STAGE.exists(),"staging_already_exists")
    demand(SOURCE.is_file() and 10000<SOURCE.stat().st_size<4194304,
        "verified_release_payload_missing")
    demand(shutil.disk_usage(str(SITE)).free>250*1024*1024,"insufficient_free_space")

def read_allowed():
    source=SOURCE.read_bytes()
    demand(len(EXPECTED_SOURCE_HASH)==64 and all(c in "0123456789abcdef" for c in EXPECTED_SOURCE_HASH),"no_pinned_archive_digest")
    demand(hashlib.sha256(source).hexdigest()==EXPECTED_SOURCE_HASH,
           "signed_release_archive_hash_mismatch")
    files={}
    with tarfile.open(fileobj=io.BytesIO(source),mode="r:gz") as archive:
        members=archive.getmembers()
        demand(100<len(members)<2500,"unexpected_tar_catalog")
        for m in members:
            path=Path(m.name)
            demand(not path.is_absolute() and ".." not in path.parts and
                   (m.isfile() or m.isdir()),"unsafe_tar_member")
            if not m.isfile():continue
            if m.name==SOURCE_PAGE:
                demand(m.size<120000,"oversized_html_template")
                files["__template__"]=archive.extractfile(m).read()
            elif m.name.startswith(GAME_ROOT+"/"):
                rel=path.relative_to(GAME_ROOT)
                # Repository's illustrative index.html is not a production entrypoint.
                if rel.name=="index.html" and len(rel.parts)==1:continue
                demand(len(rel.parts)==1 and rel.suffix in ALLOWED_EXT,
                       "unexpected_release_asset:"+str(rel))
                demand(0<m.size<450000,"oversized_asset:"+rel.name)
                files[rel.name]=archive.extractfile(m).read()
    demand(REQUIRED.issubset(files) and "__template__" in files,
           "incomplete_global_game_release")
    demand(b'import "./global-shell.mjs";' in files["app.mjs"],
           "global_game_entrypoint_missing")
    demand(b'CAMPAIGN_TOTAL' in files["global-campaign.mjs"] and
           b'LANGUAGES' in files["global-i18n.mjs"],
           "game_global_campaign_unverified")
    demand(b'businessRoadmap' in files["tycoon-panel.mjs"],
           "legacy_business_progression_missing")
    demand(b'data-lc-edition="browser"' not in files["__template__"],
           "unexpected_template_edition")
    demand(b"fetch(" not in files["global-shell.mjs"],
           "global_game_must_not_include_network_payment")
    return files

def page_html(template):
    markup=template.decode("utf-8","strict")
    demand('<html lang="en">' in markup and '{% load static %}' in markup,
           "unrecognized_game_template")
    markup=markup.replace("{% load static %}","")
    markup=markup.replace("{% static 'living_cities/style.css' %}",
                          "/living-cities/static/living_cities/style.css")
    markup=markup.replace("{% static 'living_cities/app.mjs' %}",
                          "/living-cities/static/living_cities/app.mjs")
    markup=markup.replace("{{ csrf_token }}","")
    demand("{%" not in markup and "{{" not in markup,"unresolved_template_directive")
    markup=markup.replace('<html lang="en">',
      '<html lang="en" data-lc-edition="browser">',1)
    markup=markup.replace("<title>LIVING CITIES • Worlds worth keeping</title>",
      "<title>Living Cities — 20 Languages, 200 Quests | MojPlayWin</title>\n"
      '<link rel="canonical" href="https://mojplaywin.com/living-cities/play/">\n'
      '<meta property="og:title" content="Living Cities — Global World-Building Adventure">\n'
      '<meta property="og:description" content="Build cities, run businesses and explore 20 regions in 20 languages. Play free on MojPlayWin.">')
    markup=markup.replace("<body>","<body>\n"
      '<aside class="lc-mpw-notice" role="status" style="position:relative;z-index:1200;'
      'background:#092e35;color:#eaf8f1;padding:5px 12px;text-align:center;'
      'font:12px system-ui,sans-serif;">'
      'MOJPLAYWIN GLOBAL EDITION · 20 LANGUAGES · 200 WORLD MISSIONS · '
      'LOCAL SAVE · MOJ1 PAYMENTS UNAVAILABLE</aside>',1)
    demand('data-lc-edition="browser"' in markup and
           '/living-cities/static/living_cities/app.mjs' in markup,"invalid_global_play_page")
    return markup.encode("utf-8")

def landing_html():
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Living Cities — Global City Builder and Business Empire | MojPlayWin</title>
<meta name="description" content="Play Living Cities on MojPlayWin. An original 3D city builder and endless business simulator with 200 world missions and 20 global interface languages. Free browser play.">
<link rel="canonical" href="https://mojplaywin.com/living-cities/">
<meta name="theme-color" content="#081d2a">
<style>
:root{color-scheme:dark;font-family:system-ui,Arial,sans-serif;background:#071723;color:#e9f7f5}
*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(circle at 50% 0,#18515b,#0a2437 48%,#061724)}
main{max-width:1120px;padding:clamp(24px,6vw,80px) 22px;margin:auto}
small{font-weight:850;color:#eac980;letter-spacing:.15em}
h1{font:700 clamp(44px,8vw,92px)/1.0 Georgia,serif;letter-spacing:-.045em;margin:25px 0;color:#ffdf9e}
p{font-size:clamp(16px,2.1vw,21px);line-height:1.75;color:#c4d7d9;max-width:760px}
strong{color:#ffe2a5}.cta{display:inline-block;margin:25px 0 25px;background:#f3d389;color:#19303a;
text-decoration:none;font-size:19px;font-weight:850;padding:18px 32px;border-radius:15px;box-shadow:0 18px 44px #f6d08430}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:15px;margin:30px 0}
.stats div{padding:24px;background:#123748cc;border:1px solid #8cc6ba43;border-radius:16px}
.stats b{display:block;color:#f5dfb0;font-size:30px}
nav a{color:#b6e4e0;margin-right:17px}
@media(max-width:720px){.stats{grid-template-columns:repeat(2,1fr)}.stats div{padding:15px}.stats b{font-size:25px}}
</style></head><body><main>
<nav><a href="/">MojPlayWin</a><a href="/games/">Games</a><a href="/store/">Digital Store</a></nav>
<small>MOJPLAYWIN ORIGINAL GAMES · WORLDWIDE</small>
<h1>LIVING CITIES</h1>
<p>Build a world worth keeping. Run a business empire, discover new cities, manage a team, trade across territories and take on <strong>200 evolving world missions</strong>. Every choice grows your legacy — no prison and no forced restart.</p>
<a class="cta" href="/living-cities/play/">▶ PLAY FREE — ENTER THE WORLD</a>
<div class="stats"><div><b>20</b>Languages</div><div><b>200</b>World missions</div><div><b>20</b>Upgradeable businesses</div><div><b>60</b>Discoverable cities</div></div>
<p>English by default. Change languages instantly inside the game. Supports mobile and desktop WebGL. Local progress is saved in your browser; export your save to keep a copy.</p>
<p style="font-size:13px;color:#a3bcc0">Free browser edition. No real-money payouts or unverified cryptocurrency purchases.</p>
</main></body></html>
""".encode("utf-8")

def prepare():
    guard()
    files=read_allowed()
    STAGE.mkdir(mode=0o700,parents=True)
    try:
        static=STAGE/"static/living_cities"
        static.mkdir(parents=True)
        for name,body in files.items():
            if name=="__template__":continue
            if name in ("app.mjs","tycoon-panel.mjs"):
                text=body.decode("utf-8")
                text=text.replace("/api/living-cities/","/living-cities/api/living-cities/")
                text=text.replace("/api/auth/","/living-cities/api/auth/")
                body=text.encode("utf-8")
            (static/name).write_bytes(body)
        page=STAGE/"play"
        page.mkdir(mode=0o700)
        (page/"index.html").write_bytes(page_html(files["__template__"]))
        (STAGE/"index.html").write_bytes(landing_html())
        (STAGE/".htaccess").write_text(
          "# "+OWNER+"\nPassengerEnabled off\nOptions -Indexes\nDirectoryIndex index.html\n")
        (STAGE/"LC-OWNER.txt").write_text(OWNER+"\n")
        for p in STAGE.rglob("*"):
            demand(not p.is_symlink(),"stage_contains_symlink")
            p.chmod(0o644 if p.is_file() else 0o755)
        STAGE.chmod(0o755)
        print("MPW_GLOBAL_20_LANGUAGES_200_MISSIONS_STAGE=PASS")
        print("MPW_GLOBAL_ASSET_COUNT="+str(len(files)-1))
        print("MPW_GLOBAL_PRIVATE_SOURCE_SHA="+SHA)
    except BaseException:
        if STAGE.is_dir() and not STAGE.is_symlink():shutil.rmtree(STAGE)
        raise

def publish():
    demand(SITE.is_dir() and STAGE.is_dir(),"unprepared_global_game")
    demand(not TARGET.exists() and not TARGET.is_symlink(),"target_route_now_occupied")
    demand((STAGE/"LC-OWNER.txt").read_text().strip()==OWNER,"staging_owner_invalid")
    STAGE.rename(TARGET)
    print("MPW_GLOBAL_LIVING_CITIES_PUBLIC_PUBLISHED=PASS")

def verify():
    demand(TARGET.is_dir() and not TARGET.is_symlink(),"game_not_public")
    demand((TARGET/"LC-OWNER.txt").read_text().strip()==OWNER,"game_ownership_mismatch")
    for p in REQUIRED:
        demand((TARGET/"static/living_cities"/p).is_file(),"missing_global_static:"+p)
    demand(b'data-lc-edition="browser"' in (TARGET/"play/index.html").read_bytes(),
           "global_browser_mode_missing")
    demand(b'200 evolving world missions' in (TARGET/"index.html").read_bytes(),
           "mpw_global_landing_not_found")
    demand(b"20 global interface languages" in (TARGET/"index.html").read_bytes().lower(),"localized_game_landing_incomplete")
    print("MPW_GLOBAL_RELEASE_FILES_AND_ROUTE=PASS")

def rollback():
    if not TARGET.exists():
        print("MPW_GLOBAL_NO_MANAGED_RELEASE_TO_REVERT")
        return
    demand(TARGET.is_dir() and not TARGET.is_symlink(),"unsafe_public_game")
    require_file=TARGET/"LC-OWNER.txt"
    demand(require_file.is_file() and not require_file.is_symlink() and
           require_file.read_text().strip()==OWNER,"unmanaged_game_refuse_rollback")
    recover=SCOPE/("quarantined-"+SHA+"-"+secrets.token_hex(5))
    demand(not recover.exists() and not recover.is_symlink(),"rollback_destination_conflict")
    TARGET.rename(recover)
    print("MPW_GLOBAL_LIVING_CITIES_ROLLBACK_ISOLATED_PATH=PASS")

if __name__=="__main__":
    demand(len(sys.argv)==2 and sys.argv[1] in ("prepare","publish","verify","rollback"),"unknown_mode")
    {"prepare":prepare,"publish":publish,"verify":verify,"rollback":rollback}[sys.argv[1]]()
