#!/usr/bin/env python3
"""Exact-version MojPlayWin Living Cities landing-copy repair, with rollback.

Only touches /home/zomorod2/mojplaywin.com/living-cities/index.html after
strict owner and original-content checks. Original is backed up privately.
"""
from pathlib import Path
import hashlib
import os
import secrets
import sys

HOME=Path("/home/zomorod2")
ROOT=HOME/"mojplaywin.com/living-cities"
INDEX=ROOT/"index.html"
OWNER="MPW-LIVING-CITIES-GLOBAL-20-LANG-eca666cbb730a6fcf70d284328893a78ad966881"
BKP_DIR=HOME/".private/mpw-living-cities-global/landing-copy-eca666"
BKP=BKP_DIR/"index-original.html"
HASH=BKP_DIR/"index-original.sha256"
BEFORE=b"<b>252</b>200 world missions + 52 weekly expeditions"
AFTER=b"<b>252</b>Total quests (200 world + 52 weekly)"
INTRO=b"200 evolving world missions and 52 rotating weekly expeditions"

def need(ok,msg):
    if not ok:raise RuntimeError(msg)
def sha(data):
    return hashlib.sha256(data).hexdigest()
def guard():
    need(os.geteuid()==HOME.stat().st_uid,"different_account_uid")
    for p in (HOME,ROOT,INDEX,BKP_DIR,BKP,HASH):
        need(not p.is_symlink(),"linked_path:"+p.name)
    need(INDEX.is_file() and INDEX.stat().st_size<150000,"missing_or_oversized_game_landing")
    marker=ROOT/"LC-OWNER.txt"
    need(marker.is_file() and not marker.is_symlink() and
         marker.read_text().strip()==OWNER,"unrecognized_game_version_do_not_edit")
def fix(raw):
    need(INTRO in raw and b'href="/living-cities/play/"' in raw,
         "unexpected_global_game_page")
    need(raw.count(BEFORE)+raw.count(AFTER)==1,"unrecognized_game_mission_stat")
    return raw.replace(BEFORE,AFTER)
def backup():
    guard()
    raw=INDEX.read_bytes()
    fix(raw)
    BKP_DIR.mkdir(parents=True,mode=0o700,exist_ok=True)
    if BKP.exists():
        need(HASH.is_file() and sha(BKP.read_bytes())==HASH.read_text().strip(),
             "existing_backup_invalid")
        need(raw in (BKP.read_bytes(),fix(BKP.read_bytes())),
             "unrelated_public_game_modifications")
    else:
        with BKP.open("xb") as h:
            h.write(raw);h.flush();os.fsync(h.fileno())
        BKP.chmod(0o600)
        HASH.write_text(sha(raw)+"\n")
        HASH.chmod(0o600)
    print("MPW_LANDING_OLD_SHA256="+sha(BKP.read_bytes()))
    print("MPW_LANDING_PRIVATE_BACKUP_VERIFIED=PASS")
def apply():
    guard()
    need(BKP.is_file() and HASH.is_file(),"private_backup_absent")
    original=BKP.read_bytes()
    need(sha(original)==HASH.read_text().strip(),"private_backup_corrupt")
    current=INDEX.read_bytes()
    target=fix(original)
    need(current in (original,target),"concurrent_game_edit_refuse")
    if current==target:
        print("MPW_LANDING_ALREADY_CORRECT=PASS")
        return
    pending=INDEX.parent/(".living-cities-copy-"+secrets.token_hex(8)+".tmp")
    with pending.open("xb") as h:
        h.write(target);h.flush();os.fsync(h.fileno())
    pending.chmod(INDEX.stat().st_mode & 0o777)
    need(sha(INDEX.read_bytes())==sha(original),"public_file_changed_during_prepare")
    os.replace(pending,INDEX)
    need(INDEX.read_bytes()==target,"atomic_repair_failed")
    print("MPW_LANDING_CLEAN_252_TOTAL_QUESTS=PASS")
def verify():
    guard()
    raw=INDEX.read_bytes()
    need(AFTER in raw and BEFORE not in raw,"landing_mission_stat_still_malformed")
    need(BKP.is_file() and HASH.is_file() and
         sha(BKP.read_bytes())==HASH.read_text().strip(),"restore_source_unavailable")
    need(raw==fix(BKP.read_bytes()),"other_game_change_detected")
    print("MPW_LANDING_200_WORLD_PLUS_52_WEEKLY=PASS")
def rollback():
    guard()
    need(BKP.is_file() and HASH.is_file(),"missing_original_game_copy")
    old=BKP.read_bytes()
    need(sha(old)==HASH.read_text().strip(),"backup_changed")
    current=INDEX.read_bytes()
    need(current==fix(old),"unrecognized_edits_refuse_restore")
    if current==old:return
    pending=INDEX.parent/(".living-cities-revert-"+secrets.token_hex(8)+".tmp")
    with pending.open("xb") as h:
        h.write(old);h.flush();os.fsync(h.fileno())
    pending.chmod(INDEX.stat().st_mode & 0o777)
    os.replace(pending,INDEX)
    print("MPW_LANDING_PRIOR_COPY_RESTORED=PASS")
if __name__=="__main__":
    need(len(sys.argv)==2 and sys.argv[1] in ("backup","apply","verify","rollback"),
         "invalid_operation")
    {"backup":backup,"apply":apply,"verify":verify,"rollback":rollback}[sys.argv[1]]()
