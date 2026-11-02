#!/usr/bin/env python3
"""Stage the exact Living Cities 50/250 browser release privately on cPanel.

Never publishes, renames or edits the existing public game, other site assets,
Passenger, customer account data or any production database. Fail closed.
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
ROOT=HOME/".private/mpw-living-cities-50-20261102"
SOURCE_SHA="57f8de80f45cbc8bec52c687bd6141d5cefc2d03"
BEFORE_SHA="eca666cbb730a6fcf70d284328893a78ad966881"
ARCHIVE=ROOT/"releases"/SOURCE_SHA/"source.tgz"
STAGE=ROOT/("new-build-"+SOURCE_SHA)
PUBLIC=SITE/"living-cities"
BACKUP=ROOT/("previous-public-"+BEFORE_SHA)
EXPECTED_SHA=os.environ.get("LC_GAME_ARCHIVE_SHA256","")
NEW_OWNER="MPW-LIVING-CITIES-FIFTY-CAST250-"+SOURCE_SHA
OLD_OWNER="MPW-LIVING-CITIES-GLOBAL-20-LANG-"+BEFORE_SHA
GAME_ROOT="apps/living_cities/static/living_cities"
GAME_TEMPLATE="apps/living_cities/templates/living_cities/play.html"
REQUIRED=frozenset({
  "app.mjs","sim.mjs","render.mjs","style.css","tycoon.mjs",
  "tycoon-panel.mjs","tycoon-idempotency.mjs","tycoon.css",
  "progression.mjs","global-i18n.mjs","global-missions-i18n.mjs",
  "global-campaign.mjs","global-shell.mjs","global-theme.css",
  "gameplay-i18n.mjs","weekly-expeditions.mjs",
  "career-catalog.mjs","customer-orders-i18n.mjs",
  "starter-journey.mjs","starter-guide-i18n.mjs",
  "render-2d.mjs","global-extra-i18n.mjs",
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
    require(b'gameplayText' in found["tycoon-panel.mjs"],"localized_businesses_not_integrated")
    require(b'YEARLY_CONTRACTS' in found["weekly-expeditions.mjs"],"weekly_contract_module_missing")
    require(b"fetch(" not in found["weekly-expeditions.mjs"],"unexpected_network_access_in_cosmetic_contract")
    require(b"Expected 50 professions" in found["career-catalog.mjs"],"fifty_careers_not_in_source")
    require(b"acceptCustomerOrder" in found["tycoon-panel.mjs"],"interactive_order_loop_not_integrated")
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
       '<title>Living Cities · 50 Careers · 250 Characters · Living Cities | MojPlayWin</title>\n'
       '<link rel="canonical" href="https://mojplaywin.com/living-cities/play/">\n'
       '<meta name="description" content="Build fifty unique businesses with 250 recruitable characters, interactive customer orders, story chapters and worldwide missions in 20 languages.">')
    html=html.replace("<body>","<body>\n"
      '<aside role="status" style="position:relative;z-index:1200;'
      'background:#092e35;color:#eaf8f1;padding:5px 12px;text-align:center;'
      'font:12px system-ui,sans-serif;">MOJPLAYWIN WORLD EDITION · 20 LANGUAGES · '
      '50 CAREERS · 250 CHARACTERS · 10 CHAPTERS · LOCAL SAVE · MOJ1 PAYMENTS UNAVAILABLE</aside>',1)
    require('data-lc-edition="browser"' in html and
            '/living-cities/static/living_cities/app.mjs' in html,
            "global_browser_mode_not_configured")
    return html.encode("utf-8")

def landing_html(old):
    require(b"/living-cities/play/" in old,"existing_game_landing_unrecognized")
    return old

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
        require(b'gameplay-i18n.mjs' in (static/"tycoon-panel.mjs").read_bytes(),
                "business_translation_not_published")
        require(b'weeklyExpedition' in (static/"global-shell.mjs").read_bytes(),
                "weekly_expeditions_not_published")
        require(b'acceptCustomerOrder' in (static/"tycoon-panel.mjs").read_bytes(),
                "order_cycle_not_staged")
        print("MPW_50_250_PRIVATE_STATIC_STAGE=PASS")
        print("MPW_50_REVIEWED_ASSET_COUNT="+str(len(files)-1))
        print("MPW_GLOBAL_LOCAL_SAVES_UNCHANGED=true")
    except BaseException:
        if stage.exists():shutil.rmtree(stage)
        raise

def verify():
    require(PUBLIC.is_dir() and STAGE.is_dir() and not STAGE.is_symlink(),
            "private_stage_not_prepared")
    require(owner(PUBLIC)==OLD_OWNER and owner(STAGE)==NEW_OWNER,
            "existing_public_game_changed_or_unrecognized")
    require(not BACKUP.exists(),"unexpected_public_backup_mutation")
    require(all((STAGE/"static/living_cities"/n).is_file() for n in REQUIRED),
            "private_stage_module_missing")
    require(b'data-lc-edition="browser"' in (STAGE/"play/index.html").read_bytes(),
            "browser_edition_missing")
    print("MPW_50_PRIVATE_STAGE_VERIFIED=PASS")
    print("MPW_PUBLIC_GAME_UNCHANGED_BY_STAGER=PASS")

if __name__=="__main__":
    require(len(sys.argv)==2 and sys.argv[1] in ("prepare","verify"),
            "unsupported_staging_operation")
    {"prepare":prepare,"verify":verify}[sys.argv[1]]()
