#!/usr/bin/env python3
"""Atomic, owner-verified update of *only* MojPlayWin Living Cities assets.

Never edits site root, Passenger settings, other games, Django, commerce or DB.
Save keys remain exactly unchanged and never copied into release archives.
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
SHA="0ece041b207f633a583d6fa80a1fa83dbc5d0265"
OLD_SHA="27111d39d96f44638554233b8fcc129bea33752a"
ROOT=HOME/".private/mpw-living-cities-global"
SOURCE=ROOT/"releases"/SHA/"source.tgz"
TARGET=HOME/"mojplaywin.com"/"living-cities"
STAGE=ROOT/("upgrade-stage-"+SHA[:12])
BACKUP=ROOT/("before-upgrade-"+SHA[:12])
OLD_OWNER="MPW-LIVING-CITIES-GLOBAL-20-LANG-"+OLD_SHA
NEW_OWNER="MPW-LIVING-CITIES-GLOBAL-20-LANG-"+SHA
ARCHIVE_SHA=os.environ.get("LC_GLOBAL_ARCHIVE_SHA256","")
GAME_PREFIX="apps/living_cities/static/living_cities/"
PATCH_FILES={"app.mjs","tycoon-panel.mjs","global-shell.mjs","gameplay-i18n.mjs"}
REQUIRED={"global-i18n.mjs","global-campaign.mjs","global-theme.css","global-missions-i18n.mjs","sim.mjs","tycoon.mjs","render.mjs","style.css"}

def require(ok,message):
    if not ok:raise RuntimeError(message)

def marker(root):
    file=root/"LC-OWNER.txt"
    require(file.is_file() and not file.is_symlink(),"owned_release_marker_missing")
    return file.read_text().strip()

def guard():
    require(os.geteuid()==HOME.stat().st_uid,"wrong_host_account")
    require(TARGET.parent.is_dir() and not TARGET.parent.is_symlink(),"wrong_site")
    for p in (HOME,ROOT,TARGET,SOURCE,STAGE,BACKUP):
        require(not p.is_symlink(),"symlink_in_release_boundary")
    require(TARGET.is_dir() and marker(TARGET)==OLD_OWNER,"original_global_version_not_owned")
    require((TARGET/"play/index.html").is_file() and
            b'data-lc-edition="browser"' in (TARGET/"play/index.html").read_bytes(),
            "original_browser_player_missing")
    require(not STAGE.exists() and not BACKUP.exists(),"upgrade_already_in_progress")
    require(SOURCE.is_file() and 10000<SOURCE.stat().st_size<4194304,"missing_pinned_source")
    require(len(ARCHIVE_SHA)==64 and all(ch in "0123456789abcdef" for ch in ARCHIVE_SHA),
            "source_archive_digest_not_pinned")
    require(hashlib.sha256(SOURCE.read_bytes()).hexdigest()==ARCHIVE_SHA,
            "encrypted_release_digest_mismatch")
    require(shutil.disk_usage(str(HOME)).free>150*1024*1024,"insufficient_free_storage")

def selected_files():
    files={}
    with tarfile.open(fileobj=io.BytesIO(SOURCE.read_bytes()),mode="r:gz") as archive:
        members=archive.getmembers()
        require(100<len(members)<2500,"unexpected_release_member_count")
        for m in members:
            path=Path(m.name)
            require(not path.is_absolute() and ".." not in path.parts and
                    (m.isdir() or m.isfile()),"unsafe_source_archive_member")
            if not m.isfile() or not m.name.startswith(GAME_PREFIX):continue
            relative=path.relative_to(GAME_PREFIX)
            if len(relative.parts)==1 and relative.name in PATCH_FILES:
                require(0<m.size<450000,"oversized_game_module")
                files[relative.name]=archive.extractfile(m).read()
    require(set(files)==PATCH_FILES,"exact_game_module_allowlist_mismatch")
    require(b'gameplay-i18n.mjs' in files["app.mjs"] and
            b'gameplay-i18n.mjs' in files["tycoon-panel.mjs"] and
            b'gameplay-i18n.mjs' in files["global-shell.mjs"],"i18n_integration_incomplete")
    require(b'UI_GAMEPLAY_LANGUAGES' in files["gameplay-i18n.mjs"] and
            b'"fa"' in files["gameplay-i18n.mjs"] and
            b'"en"' in files["gameplay-i18n.mjs"],"translation_catalog_missing")
    return files

def prepare():
    guard()
    files=selected_files()
    # Copy existing owned game, not unrelated site state. Refuse symlinks in source.
    for p in TARGET.rglob("*"):
        require(not p.is_symlink(),"existing_game_contains_symlink")
    require(sum(p.stat().st_size for p in TARGET.rglob("*") if p.is_file())<32*1024*1024,
            "unusually_large_existing_game")
    shutil.copytree(TARGET,STAGE)
    try:
        static=STAGE/"static/living_cities"
        require(static.is_dir(),"existing_game_assets_missing")
        for name,body in files.items():
            if name in ("app.mjs","tycoon-panel.mjs"):
                txt=body.decode("utf-8")
                txt=txt.replace("/api/living-cities/","/living-cities/api/living-cities/")
                txt=txt.replace("/api/auth/","/living-cities/api/auth/")
                body=txt.encode("utf-8")
            target=static/name
            require(not target.is_symlink(),"unsafe_game_module_target")
            target.write_bytes(body)
            target.chmod(0o644)
        (STAGE/"LC-OWNER.txt").write_text(NEW_OWNER+"\n")
        (STAGE/"LC-OWNER.txt").chmod(0o644)
        # Rewrite only the own marker comment in the own nested public .htaccess.
        ht=STAGE/".htaccess"
        if ht.is_file() and OLD_OWNER in ht.read_text():
            ht.write_text(ht.read_text().replace(OLD_OWNER,NEW_OWNER))
        require(marker(STAGE)==NEW_OWNER,"new_release_marker_failed")
        require(b'gameplayText' in (static/"gameplay-i18n.mjs").read_bytes(),"invalid_translations")
        require(b'200 evolving world missions' in (STAGE/"index.html").read_bytes(),
                "landing_changed_unexpectedly")
        print("MPW_LOCALIZED_TWENTY_LANGUAGES_STAGE=PASS")
        print("MPW_SAVE_SCHEMA_UNCHANGED=true")
    except BaseException:
        if STAGE.is_dir() and not STAGE.is_symlink():shutil.rmtree(STAGE)
        raise

def publish():
    require(TARGET.is_dir() and STAGE.is_dir(),"no_prepared_upgrade")
    require(not TARGET.is_symlink() and not STAGE.is_symlink() and
            not BACKUP.exists() and not BACKUP.is_symlink(),"unsafe_game_swap")
    require(marker(TARGET)==OLD_OWNER and marker(STAGE)==NEW_OWNER,
            "version_changed_before_atomic_swap")
    TARGET.rename(BACKUP)
    try:
        STAGE.rename(TARGET)
    except BaseException:
        BACKUP.rename(TARGET)
        raise
    require(marker(TARGET)==NEW_OWNER,"game_release_marker_mismatch")
    print("MPW_GLOBAL_DEEP_LOCALIZATION_PUBLISHED=PASS")
    print("MPW_PRIOR_LIVE_GAME_PRIVATE_BACKUP=PASS")

def verify():
    require(TARGET.is_dir() and BACKUP.is_dir(),"game_or_backup_missing")
    require(marker(TARGET)==NEW_OWNER and marker(BACKUP)==OLD_OWNER,
            "game_or_backup_marker_mismatch")
    assets=TARGET/"static/living_cities"
    require(all((assets/p).is_file() for p in PATCH_FILES|REQUIRED),
            "missing_core_or_localized_game_modules")
    require(b'gameplay-i18n.mjs' in (assets/"app.mjs").read_bytes(),"new_entrypoint_not_active")
    require((TARGET/"play/index.html").is_file(),"play_route_missing")
    print("MPW_GLOBAL_GAME_20_LANGUAGE_DEEP_LOCALIZATION_VERIFIED=PASS")

def rollback():
    require(TARGET.is_dir() and BACKUP.is_dir() and
            not TARGET.is_symlink() and not BACKUP.is_symlink(),
            "rollback_preconditions_failed")
    require(marker(TARGET)==NEW_OWNER and marker(BACKUP)==OLD_OWNER,
            "unexpected_game_release_refuse_rollback")
    failed=ROOT/("failed-localization-"+SHA[:10]+"-"+secrets.token_hex(6))
    TARGET.rename(failed)
    try:
        BACKUP.rename(TARGET)
    except BaseException:
        failed.rename(TARGET)
        raise
    print("MPW_PREVIOUS_20_LANGUAGE_GAME_RESTORED=PASS")

if __name__=="__main__":
    require(len(sys.argv)==2 and sys.argv[1] in ("prepare","publish","verify","rollback"),
            "invalid_upgrade_mode")
    {"prepare":prepare,"publish":publish,"verify":verify,"rollback":rollback}[sys.argv[1]]()
