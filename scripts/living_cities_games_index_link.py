#!/usr/bin/env python3
"""Safely add Living Cities to the existing Zomorod games directory.

Only touches the static games index after successful verified gameplay rollout.
Maintains a private exact-byte backup and guarded rollback.
"""
from pathlib import Path
import hashlib
import os
import re
import secrets
import sys

HOME=Path("/home/zomorod2")
ROOT=HOME/".private/living-cities-app"
LIVE=HOME/"public_html/living-cities"
INDEX=HOME/"public_html/games/index.html"
BACKUP=ROOT/"games-index-before-living-cities.html"
SHA_FILE=ROOT/"games-index-before-living-cities.sha256"
MARKER="LC-STATIC-BROWSER-PUBLIC-50a44804d1b90df1bd6098ca75da2c3af6632e18"
LINK="/living-cities/play/"

CARD = r'''<section id="zm-living-cities" aria-labelledby="zm-living-cities-title"
style="margin:24px auto;padding:22px;max-width:1100px;border:1px solid #b39c59;border-radius:18px;background:linear-gradient(135deg,#102a38,#214b43);color:#fcf7e9;box-shadow:0 12px 35px #05131c25;text-align:right;direction:rtl">
  <h2 id="zm-living-cities-title" style="margin:0 0 9px;font-size:clamp(19px,3vw,26px);color:#f8e0a0">🎮 بازی مدیریت کسب‌وکار و شهرسازی Living Cities</h2>
  <p style="margin:0 0 15px;line-height:1.9;font-size:15px;color:#e1e9e7">۲۰ کسب‌وکار قابل ارتقا، ۱۲ مدیر، شهرسازی و تجارت؛ همراه با مأموریت‌های پیشرفت و ذخیرهٔ بازی روی همین دستگاه. اجرای رایگان در مرورگر، بدون زندان یا حذف اجباری پیشرفت.</p>
  <a href="/living-cities/play/" style="display:inline-block;padding:12px 22px;border-radius:11px;background:#e9c677;color:#172733;text-decoration:none;font-weight:800;min-height:44px">ورود به بازی مدیریت کسب‌وکار</a>
  <p style="font-size:12px;line-height:1.7;color:#bed6d4;margin:13px 0 0">نسخهٔ مرورگری با ذخیرهٔ محلی است؛ پرداخت MOJ1 و تأیید کد کالا در این نسخه فعال نیست.</p>
</section>
'''

def require(condition,message):
    if not condition:raise RuntimeError(message)

def prepare():
    require(os.geteuid()==HOME.stat().st_uid,"unexpected_account_owner")
    for p in (INDEX,INDEX.parent,LIVE,ROOT,BACKUP,SHA_FILE):
        require(not p.is_symlink(),"symlink_path")
    require(LIVE.is_dir() and (LIVE/"LC-OWNER.txt").is_file() and
            (LIVE/"LC-OWNER.txt").read_text().strip()==MARKER,"new_game_not_published")
    require(INDEX.is_file() and INDEX.stat().st_size<1024*1024,"unrecognized_games_index")
    require(not BACKUP.exists() and not SHA_FILE.exists(),"games_index_already_modified")
    original=INDEX.read_bytes()
    html=original.decode("utf-8")
    require("<html" in html.lower() and re.search(r"</body\s*>",html,re.I),"not_html")
    require(LINK not in html and 'id="zm-living-cities"' not in html,"game_already_listed")
    close=re.search(r"</main\s*>",html,re.I)
    if not close:close=re.search(r"</body\s*>",html,re.I)
    require(close is not None,"insert_marker_not_found")
    modified=html[:close.start()]+CARD+"\n"+html[close.start():]
    require(modified.count('id="zm-living-cities"')==1,"duplicate_game_card")
    oldhash=hashlib.sha256(original).hexdigest()
    BACKUP.write_bytes(original)
    BACKUP.chmod(0o600)
    SHA_FILE.write_text(oldhash+"\n")
    SHA_FILE.chmod(0o600)
    require(hashlib.sha256(BACKUP.read_bytes()).hexdigest()==oldhash,"backup_not_recoverable")
    require(hashlib.sha256(INDEX.read_bytes()).hexdigest()==oldhash,"concurrent_index_change")
    tmp=INDEX.parent/(".living-cities-index-"+secrets.token_hex(7)+".pending")
    with tmp.open("xb") as f:
        f.write(modified.encode("utf-8"))
        f.flush()
        os.fsync(f.fileno())
    tmp.chmod(INDEX.stat().st_mode & 0o777)
    os.replace(tmp,INDEX)
    print("LIVING_CITIES_DIRECTORY_CARD_INSTALLED=PASS")
    print("GAMES_INDEX_PRIOR_VERSION_HASH="+oldhash)

def verify():
    require(INDEX.is_file() and BACKUP.is_file() and SHA_FILE.is_file(),"index_or_backup_missing")
    originalhash=SHA_FILE.read_text().strip()
    require(hashlib.sha256(BACKUP.read_bytes()).hexdigest()==originalhash,"backup_corrupt")
    live=INDEX.read_text()
    require(LINK in live and live.count('id="zm-living-cities"')==1,"index_link_not_present_once")
    print("LIVING_CITIES_GAMES_INDEX_DISCOVERABILITY=PASS")

def rollback():
    require(INDEX.is_file() and BACKUP.is_file() and SHA_FILE.is_file(),"no_known_index_backup")
    require(LINK in INDEX.read_text() and INDEX.read_text().count('id="zm-living-cities"')==1,
            "unexpected_edited_index_refuse_rollback")
    data=BACKUP.read_bytes()
    require(hashlib.sha256(data).hexdigest()==SHA_FILE.read_text().strip(),"backup_hash_mismatch")
    tmp=INDEX.parent/(".living-cities-index-rollback-"+secrets.token_hex(6))
    with tmp.open("xb") as f:
        f.write(data);f.flush();os.fsync(f.fileno())
    tmp.chmod(INDEX.stat().st_mode & 0o777)
    os.replace(tmp,INDEX)
    print("LIVING_CITIES_PREVIOUS_GAMES_DIRECTORY_RESTORED=PASS")

if __name__=="__main__":
    require(len(sys.argv)==2 and sys.argv[1] in ("prepare","verify","rollback"),"unknown_operation")
    {"prepare":prepare,"verify":verify,"rollback":rollback}[sys.argv[1]]()
