#!/usr/bin/env python3
"""Atomic upgrade of the established MojPlayWin Living Cities browser game.

Only owns /home/zomorod2/mojplaywin.com/living-cities and its private release
workspace. Preserves previous complete public build for immediate rollback.
No operations on site root, Passenger, customers or live game databases.
"""
import hashlib
import io
import os
from pathlib import Path
import secrets
import shutil
import sys
import tarfile

HOME=Path("/home/zomorod2")
SITE=HOME/"mojplaywin.com"
ROOT=HOME/".private/mpw-living-cities-global"
SOURCE_SHA="813629da154b8cb541641eaddf3b143007db4d4e"
BEFORE_SHA="27111d39d96f44638554233b8fcc129bea33752a"
ARCHIVE=ROOT/"releases"/SOURCE_SHA/"source.tgz"
STAGE=ROOT/("new-build-"+SOURCE_SHA)
PUBLIC=SITE/"living-cities"
BACKUP=ROOT/("previous-public-"+BEFORE_SHA)
EXPECTED_SHA=os.environ.get("LC_GAME_ARCHIVE_SHA256","")
NEW_OWNER="MPW-LIVING-CITIES-GLOBAL-20-LANG-"+SOURCE_SHA
OLD_OWNER="MPW-LIVING-CITIES-GLOBAL-20-LANG-"+BEFORE_SHA
GAME_ROOT="apps/living_cities/static/living_cities"
GAME_TEMPLATE="apps/living_cities/templates/living_cities/play.html"
REQUIRED=frozenset({
  "app.mjs","sim.mjs","render.mjs","style.css","tycoon.mjs",
  "tycoon-panel.mjs","tycoon-idempotency.mjs","tycoon.css",
  "progression.mjs","global-i18n.mjs","global-missions-i18n.mjs",
  "global-campaign.mjs","global-shell.mjs","global-theme.css",
  "global-extra-i18n.mjs","weekly-expeditions.mjs",
})

def require(ok,msg):
    if not ok:raise RuntimeError(msg)

def owner(folder):
    marker=folder/"LC-OWNER.txt"
    require(marker.is_file() and not marker.is_symlink(),"public_owner_marker_missing")
    return marker.read_text().strip()

def validate():
    require(os.geteuid()==HOME.stat().st_uid,"wrong_cpanel_uid")
    for p in (HOME,SITE,ROOT,ARCHIVE,STAGE,PUBLIC,BACKUP):
        require(not p.is_symlink(),"symlink_in_owned_path:"+p.name)
    require(SITE.is_dir() and ROOT.is_dir() and PUBLIC.is_dir(),"existing_mpw_game_not_found")
    require(owner(PUBLIC)==OLD_OWNER,"cannot_upgrade_unrecognized_public_build")
    require(not STAGE.exists() and not BACKUP.exists(),"upgrade_already_staged_or_built")
    require(ARCHIVE.is_file() and 10000<ARCHIVE.stat().st_size<4194304,"private_archive_missing")
    require(len(EXPECTED_SHA)==64 and all(c in "0123456789abcdef" for c in EXPECTED_SHA),
            "missing_verified_digest")
    require(hashlib.sha256(ARCHIVE.read_bytes()).hexdigest()==EXPECTED_SHA,
            "private_archive_digest_changed")
    require(shutil.disk_usage(str(SITE)).free>250*1024*1024,"insufficient_free_space")

def extract():
    found={}
    raw=ARCHIVE.read_bytes()
    require(hashlib.sha256(raw).hexdigest()==EXPECTED_SHA,"digest_mismatch")
    with tarfile.open(fileobj=io.BytesIO(raw),mode="r:gz") as tar:
        entries=tar.getmembers()
        require(100<len(entries)<2500,"unrecognized_archive_manifest")
        for entry in entries:
            path=Path(entry.name)
            require(not path.is_absolute() and ".." not in path.parts and
                    (entry.isfile() or entry.isdir()),"tar_traversal_or_link")
            if not entry.isfile():continue
            if entry.name==GAME_TEMPLATE:
                require(0<entry.size<120000,"invalid_html_template")
                found["__html__"]=tar.extractfile(entry).read()
            elif entry.name.startswith(GAME_ROOT+"/"):
                rel=path.relative_to(GAME_ROOT)
                if rel.name=="index.html" and len(rel.parts)==1:continue
                require(len(rel.parts)==1 and rel.suffix in {".mjs",".css"} and
                        0<entry.size<450000,"unapproved_game_asset")
                found[rel.name]=tar.extractfile(entry).read()
    require(REQUIRED.issubset(found) and "__html__" in found,"reviewed_game_files_missing")
    require(b'import "./global-shell.mjs";' in found["app.mjs"],"global_entrypoint_missing")
    require(b'weeklyExpedition' in found["global-shell.mjs"],"weekly_progress_not_integrated")
    require(b'gameLabel' in found["tycoon-panel.mjs"],"localized_businesses_not_integrated")
    require(b'YEARLY_CONTRACTS' in found["weekly-expeditions.mjs"],"weekly_contract_module_missing")
    require(b"fetch(" not in found["weekly-expeditions.mjs"],"unexpected_network_access_in_cosmetic_contract")
    return found

def page_html(src):
    html=src.decode("utf-8")
    require('<html lang="en">' in html and "{% load static %}" in html,"unrecognized_game_template")
    html=html.replace("{% load static %}","")
    html=html.replace("{% static 'living_cities/style.css' %}",
                      "/living-cities/static/living_cities/style.css")
    html=html.replace("{% static 'living_cities/app.mjs' %}",
                      "/living-cities/static/living_cities/app.mjs")
    html=html.replace("{{ csrf_token }}","")
    require("{%" not in html and "{{" not in html,"html_template_token_not_resolved")
    html=html.replace('<html lang="en">',
        '<html lang="en" data-lc-edition="browser">',1)
    html=html.replace("<title>LIVING CITIES • Worlds worth keeping</title>",
       '<title>Living Cities · 20 Languages · 252 Quests | MojPlayWin</title>\n'
       '<link rel="canonical" href="https://mojplaywin.com/living-cities/play/">\n'
       '<meta name="description" content="Play a global city-building and business game with 200 world missions plus 52 weekly expeditions. Available in 20 languages.">')
    html=html.replace("<body>","<body>\n"
      '<aside role="status" style="position:relative;z-index:1200;'
      'background:#092e35;color:#eaf8f1;padding:5px 12px;text-align:center;'
      'font:12px system-ui,sans-serif;">MOJPLAYWIN WORLD EDITION · 20 LANGUAGES · '
      '200 WORLD MISSIONS + 52 WEEKLY EXPEDITIONS · LOCAL SAVE · MOJ1 PAYMENTS UNAVAILABLE</aside>',1)
    require('data-lc-edition="browser"' in html and
            '/living-cities/static/living_cities/app.mjs' in html,
            "global_browser_mode_not_configured")
    return html.encode("utf-8")

def landing_html(old):
    require(b"200 evolving world missions" in old and
            b"/living-cities/play/" in old,"previous_global_landing_not_recognized")
    html=old.decode("utf-8")
    html=html.replace("200 evolving world missions",
        "200 evolving world missions and 52 rotating weekly expeditions")
    html=html.replace("<b>200</b>World missions",
        "<b>252</b>200 world missions + 52 weekly expeditions")
    return html.encode("utf-8")

def prepare():
    validate()
    files=extract()
    stage=STAGE
    stage.mkdir(mode=0o700,parents=True)
    try:
        static=stage/"static/living_cities"
        static.mkdir(parents=True,mode=0o700)
        for name,raw in files.items():
            if name=="__html__":continue
            if name in ("app.mjs","tycoon-panel.mjs"):
                js=raw.decode("utf-8").replace("/api/living-cities/","/living-cities/api/living-cities/")
                js=js.replace("/api/auth/","/living-cities/api/auth/")
                raw=js.encode("utf-8")
            (static/name).write_bytes(raw)
        (stage/"play").mkdir(mode=0o700)
        (stage/"play/index.html").write_bytes(page_html(files["__html__"]))
        (stage/"index.html").write_bytes(landing_html((PUBLIC/"index.html").read_bytes()))
        (stage/".htaccess").write_text(
          "# "+NEW_OWNER+"\nPassengerEnabled off\nOptions -Indexes\nDirectoryIndex index.html\n")
        (stage/"LC-OWNER.txt").write_text(NEW_OWNER+"\n")
        for p in stage.rglob("*"):
            require(not p.is_symlink(),"unsafe_staging_link")
            p.chmod(0o644 if p.is_file() else 0o755)
        stage.chmod(0o755)
        require(b'global-extra-i18n.mjs' in (static/"tycoon-panel.mjs").read_bytes(),
                "business_translation_not_published")
        require(b'weeklyExpedition' in (static/"global-shell.mjs").read_bytes(),
                "weekly_expeditions_not_published")
        print("MPW_FINAL_GLOBAL_LOCALE_AND_WEEKLY_STAGE=PASS")
        print("MPW_GLOBAL_REVIEWED_ASSET_COUNT="+str(len(files)-1))
        print("MPW_GLOBAL_LOCAL_SAVES_UNCHANGED=true")
    except BaseException:
        if stage.exists():shutil.rmtree(stage)
        raise

def publish():
    require(PUBLIC.is_dir() and STAGE.is_dir(),"unprepared_global_release")
    require(owner(PUBLIC)==OLD_OWNER and owner(STAGE)==NEW_OWNER,"release_owner_mismatch")
    require(not BACKUP.exists() and not BACKUP.is_symlink(),"existing_backup_conflict")
    PUBLIC.rename(BACKUP)
    try:
        STAGE.rename(PUBLIC)
    except BaseException:
        BACKUP.rename(PUBLIC)
        raise
    print("MPW_GLOBAL_252_MISSION_GAME_ATOMICALLY_PUBLISHED=PASS")
    print("MPW_PREVIOUS_GLOBAL_200_MISSION_BUILD_PRESERVED=PASS")

def verify():
    require(PUBLIC.is_dir() and BACKUP.is_dir() and
            owner(PUBLIC)==NEW_OWNER and owner(BACKUP)==OLD_OWNER,"release_integrity_failed")
    require(all((PUBLIC/"static/living_cities"/n).is_file() for n in REQUIRED),
            "public_game_module_missing")
    require(b'200 WORLD MISSIONS + 52 WEEKLY EXPEDITIONS' in
            (PUBLIC/"play/index.html").read_bytes(),"public_edition_mismatch")
    print("MPW_252_QUEST_GLOBAL_20_LANGUAGES_PUBLISHED_AND_ROLLBACK_VERIFIED=PASS")

def rollback():
    require(PUBLIC.is_dir() and BACKUP.is_dir() and not PUBLIC.is_symlink() and
            not BACKUP.is_symlink(),"cannot_restore_missing_old_release")
    require(owner(PUBLIC)==NEW_OWNER and owner(BACKUP)==OLD_OWNER,
            "rollback_cannot_modify_unowned_path")
    failed=ROOT/("failed-release-"+SOURCE_SHA+"-"+secrets.token_hex(5))
    PUBLIC.rename(failed)
    try:
        BACKUP.rename(PUBLIC)
    except BaseException:
        failed.rename(PUBLIC)
        raise
    print("MPW_PREVIOUS_VERIFIED_GLOBAL_BUILD_RESTORED=PASS")

if __name__=="__main__":
    require(len(sys.argv)==2 and sys.argv[1] in ("prepare","publish","verify","rollback"),
            "unsupported_living_cities_release_operation")
    {"prepare":prepare,"publish":publish,"verify":verify,"rollback":rollback}[sys.argv[1]]()
