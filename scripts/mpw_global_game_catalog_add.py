#!/usr/bin/env python3
"""Bounded MojPlayWin Games catalog promotion of an already-live original game.

Patches only the active brand-specific template inside Saeit-staging after
exact digest verification and immutable private backup. No game code, other
templates, database, or Zomorod site is modified.
"""
from pathlib import Path
import hashlib
import os
import secrets
import sys

HOME=Path("/home/zomorod2")
ROOT=HOME/"Saeit-staging"
TEMPLATE=ROOT/"core/templates/brands/mojplaywin/page.html"
GAME=HOME/"mojplaywin.com/living-cities"
PRIVATE=HOME/".private/mpw-living-cities-global/catalog"
BACKUP=PRIVATE/"games-page-before-global.html"
MEMENTO=PRIVATE/"games-page-before-global.sha256"
ORIGINAL_HASH="f4150c91aa0a6294b5b6d1536bbdab32fd4d7c3fe6e6e151241a5335d483dddc"
SOURCE_SHA="27111d39d96f44638554233b8fcc129bea33752a"
OWNER="MPW-LIVING-CITIES-GLOBAL-20-LANG-"+SOURCE_SHA
MARKER="mpw-global-living-cities-feature-20261101"
ANCHOR="{% if page_key == 'games' %}"
PROMO=(
'<section class="mpw-page-cta" id="'+MARKER+'" aria-labelledby="mpw-global-lc-title">'
'<span class="eyebrow">NOW PLAYABLE · WORLDWIDE · 20 LANGUAGES</span>'
'<h2 id="mpw-global-lc-title">Living Cities — Build a world worth keeping</h2>'
'<p>An original free-to-play, 3D city-builder and business tycoon. Open 20 businesses, manage 12 characters,'
' discover up to 60 cities and progress through 200 missions across 20 world regions.'
' English by default, with 19 more languages selectable inside the game.</p>'
'<p><a class="primary" href="/living-cities/play/">▶ PLAY LIVING CITIES — FREE</a> '
'<a href="/living-cities/">Explore game features and languages →</a></p>'
'<p><small>Local browser save · no purchases or unverified MOJ1 payments.</small></p>'
'</section>'
)

def need(ok,message):
    if not ok:raise RuntimeError(message)

def safe():
    need(os.geteuid()==HOME.stat().st_uid,"account_owner_mismatch")
    for path in (ROOT,TEMPLATE,GAME,PRIVATE,BACKUP,MEMENTO):
        need(not path.is_symlink(),"symlink_rejected:"+path.name)
    need(ROOT.is_dir() and TEMPLATE.is_file(),"unexpected_active_template")
    need(GAME.is_dir() and (GAME/"LC-OWNER.txt").read_text().strip()==OWNER,
         "global_game_not_owned_or_unpublished")
    need(TEMPLATE.stat().st_size<180000,"unexpected_template_size")

def publish():
    safe()
    need(not BACKUP.exists() and not MEMENTO.exists(),"prior_catalog_operation_detected")
    prior=TEMPLATE.read_bytes()
    digest=hashlib.sha256(prior).hexdigest()
    need(digest==ORIGINAL_HASH,"active_template_has_changed_stop")
    template=prior.decode("utf-8")
    need(ANCHOR in template and MARKER not in template,"invalid_games_template_anchor")
    content=template.replace(ANCHOR,ANCHOR+"\n"+PROMO+"\n",1)
    need(content.count('id="'+MARKER+'"')==1,"duplicate_catalog_feature")
    need(content.count(ANCHOR)==template.count(ANCHOR),"template_conditions_must_be_preserved")
    PRIVATE.mkdir(parents=True,mode=0o700,exist_ok=True)
    with BACKUP.open("xb") as f:
        f.write(prior);f.flush();os.fsync(f.fileno())
    BACKUP.chmod(0o600)
    MEMENTO.write_text(digest+"\n");MEMENTO.chmod(0o600)
    need(hashlib.sha256(BACKUP.read_bytes()).hexdigest()==ORIGINAL_HASH,"backup_verify_failed")
    need(hashlib.sha256(TEMPLATE.read_bytes()).hexdigest()==ORIGINAL_HASH,"template_changed_during_preflight")
    temp=TEMPLATE.parent/(".mpw-global-games-"+secrets.token_hex(6)+".pending")
    with temp.open("xb") as f:
        f.write(content.encode("utf-8"));f.flush();os.fsync(f.fileno())
    temp.chmod(TEMPLATE.stat().st_mode & 0o777)
    os.replace(temp,TEMPLATE)
    print("MPW_GLOBAL_GAMES_TEMPLATE_FEATURE_INSTALLED=PASS")
    print("MPW_GLOBAL_GAMES_TEMPLATE_PRIVATE_BACKUP=PASS")
    print("MPW_GAMES_TEMPLATE_NEW_SHA256="+hashlib.sha256(TEMPLATE.read_bytes()).hexdigest())

def verify():
    safe()
    need(BACKUP.is_file() and MEMENTO.is_file(),"missing_catalog_backup")
    need(hashlib.sha256(BACKUP.read_bytes()).hexdigest()==ORIGINAL_HASH,"catalog_backup_corrupted")
    content=TEMPLATE.read_text()
    need(content.count('id="'+MARKER+'"')==1,"missing_global_games_card")
    need(content.count('href="/living-cities/play/"')==1,
         "global_game_link_missing_or_duplicated")
    print("MPW_GLOBAL_GAMES_TEMPLATE_FEATURE_VERIFIED=PASS")

def rollback():
    safe()
    need(BACKUP.is_file() and MEMENTO.is_file(),"no_owned_catalog_backup")
    need(MARKER in TEMPLATE.read_text(),"someone_else_modified_catalog")
    data=BACKUP.read_bytes()
    need(hashlib.sha256(data).hexdigest()==ORIGINAL_HASH,"catalog_backup_bad_sha")
    temp=TEMPLATE.parent/(".mpw-global-games-revert-"+secrets.token_hex(6))
    with temp.open("xb") as f:
        f.write(data);f.flush();os.fsync(f.fileno())
    temp.chmod(TEMPLATE.stat().st_mode & 0o777)
    os.replace(temp,TEMPLATE)
    print("MPW_GLOBAL_GAMES_CATALOG_ROLLBACK=PASS")

if __name__=="__main__":
    need(len(sys.argv)==2 and sys.argv[1] in ("publish","verify","rollback"),"unsupported_mode")
    {"publish":publish,"verify":verify,"rollback":rollback}[sys.argv[1]]()
