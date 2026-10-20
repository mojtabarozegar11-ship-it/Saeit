#!/usr/bin/env python3
"""Reversible PICM-only UX repair: default text-to-image, no mandatory photo.

Target is exclusively TWO existing PICM template assets. Refuse if production
files have changed since inspected baseline; never modify routes, authentication,
other subsites, private user uploads, workers or factory.
"""
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import sys
import tempfile

HOME=Path("/home/zomorod2")
APP=HOME/"Saeit-staging"
DOCROOT=HOME/"mojplaywin.com"
BACKUP_ROOT=HOME/".mojplaywin-backups"
FILES=(Path("templates/picm/index.html"),Path("templates/picm/text_image.js"))
EXPECTED={
    "templates/picm/index.html":"22cb5168e04ad23c962b55c1661917bb564dfb5b",
    "templates/picm/text_image.js":"1f72a59b9a6e0a1156e947cabb75cf4b712b6d33",
}
VALID_RUN=re.compile(r"^[0-9]{1,20}$")
VALID_HASH=re.compile(r"^[a-f0-9]{64}$")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def git_blob(data):
    return hashlib.sha1(("blob "+str(len(data))+"\0").encode("ascii")+data).hexdigest()


def write_atomic(target,raw,mode):
    if target.is_symlink() or target.parent.is_symlink():
        raise RuntimeError("PICM_UNSAFE_WRITE_TARGET")
    fd,tmp=tempfile.mkstemp(prefix=".picm-default-",dir=target.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp,target)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def sanity(run):
    if not VALID_RUN.fullmatch(run):
        raise RuntimeError("PICM_INVALID_RUN_ID")
    if pwd.getpwuid(os.getuid()).pw_name!="zomorod2":
        raise RuntimeError("PICM_WRONG_DEPLOY_ACCOUNT")
    for root in (APP,DOCROOT):
        if root.is_symlink() or not root.is_dir():
            raise RuntimeError("PICM_APP_ROOT_UNSAFE")
    passenger=DOCROOT/"passenger_wsgi.py"
    if passenger.is_symlink() or not passenger.is_file() or "Saeit-staging" not in passenger.read_text(errors="replace"):
        raise RuntimeError("PICM_WRONG_PASSENGER_APPLICATION")
    owner=HOME/".picm-queue/.owner-user-id"
    if owner.is_symlink() or not owner.is_file():
        raise RuntimeError("PICM_OWNER_NOT_BOUND")
    for path in FILES:
        target=APP/path
        if not target.is_file() or target.is_symlink() or target.parent.is_symlink():
            raise RuntimeError("PICM_MISSING_PROTECTED_TEMPLATE")
    if BACKUP_ROOT.is_symlink():
        raise RuntimeError("PICM_BACKUP_ROOT_UNSAFE")


def restart():
    for root in (APP,DOCROOT):
        d=root/"tmp"
        if d.is_symlink():
            raise RuntimeError("PICM_PASSENGER_MARKER_UNSAFE")
        d.mkdir(exist_ok=True)
        m=d/"restart.txt"
        if m.is_symlink():
            raise RuntimeError("PICM_PASSENGER_MARKER_UNSAFE")
        m.touch()


def backup_path(run):
    return BACKUP_ROOT/("picm-owner-default-"+run)


def stage_path(run):
    return HOME/(".picm-owner-default-stage-"+run)


def deploy(run,expected_index,expected_js):
    sanity(run)
    if not VALID_HASH.fullmatch(expected_index) or not VALID_HASH.fullmatch(expected_js):
        raise RuntimeError("PICM_BAD_SOURCE_CHECKSUM")
    stage=stage_path(run)
    if not stage.is_dir() or stage.is_symlink():
        raise RuntimeError("PICM_PRIVATE_STAGE_NOT_FOUND")
    payload={}
    prior={}
    targethash={}
    for rel,expected_sha in zip(FILES,(expected_index,expected_js)):
        staged=stage/rel
        live=APP/rel
        if not staged.is_file() or staged.is_symlink():
            raise RuntimeError("PICM_STAGED_FILE_MISSING")
        raw=staged.read_bytes()
        if len(raw)<1000 or sha256(raw)!=expected_sha:
            raise RuntimeError("PICM_STAGED_FILE_CHECKSUM_MISMATCH")
        old=live.read_bytes()
        if git_blob(old)!=EXPECTED[str(rel)]:
            raise RuntimeError("PICM_LIVE_FILE_CHANGED_REFUSE_OVERWRITE")
        payload[str(rel)]=raw
        prior[str(rel)]=old
        targethash[str(rel)]=expected_sha
    html=payload[str(FILES[0])].decode("utf-8")
    js=payload[str(FILES[1])].decode("utf-8")
    if not all(x in html for x in ('id="mode-text_image" type="button" aria-pressed="true"',
                                  'id="mode" name="mode" value="text_image"',
                                  'id="photo"','id="text-image-options"')):
        raise RuntimeError("PICM_NEW_DEFAULT_FORM_INVALID")
    if not all(x in js for x in ("form.noValidate=selected","photo.required=!selected",
                                'fetch("/picm/api/submit/"')):
        raise RuntimeError("PICM_NEW_TEXT_IMAGE_SCRIPT_INVALID")
    BACKUP_ROOT.mkdir(parents=True,mode=0o700,exist_ok=True)
    backup=backup_path(run)
    if backup.exists() or backup.is_symlink():
        raise RuntimeError("PICM_RUN_ALREADY_DEPLOYED")
    backup.mkdir(mode=0o700)
    manifest={"run":run,"source":{},"installed":targethash}
    for rel in FILES:
        item=backup/rel
        item.parent.mkdir(parents=True,exist_ok=True)
        item.write_bytes(prior[str(rel)])
        item.chmod(0o600)
        manifest["source"][str(rel)]=sha256(prior[str(rel)])
    (backup/"manifest.json").write_text(json.dumps(manifest,sort_keys=True),encoding="utf-8")
    (backup/"manifest.json").chmod(0o600)
    try:
        for rel in FILES:
            live=APP/rel
            write_atomic(live,payload[str(rel)],live.stat().st_mode&0o777)
        restart()
        print("PICM_OWNER_DEFAULT_TEXT_IMAGE_DEPLOYED")
        print("PICM_DEFAULT_BACKUP_ID="+run)
    except Exception:
        rollback(run)
        raise


def rollback(run):
    sanity(run)
    b=backup_path(run)
    manifest=b/"manifest.json"
    if not manifest.is_file() or manifest.is_symlink():
        raise RuntimeError("PICM_NO_VALID_BACKUP")
    m=json.loads(manifest.read_text(encoding="utf-8"))
    if m.get("run")!=run:
        raise RuntimeError("PICM_BACKUP_RUN_MISMATCH")
    for rel in FILES:
        live=APP/rel
        old=b/rel
        if old.is_symlink() or not old.is_file() or live.is_symlink():
            raise RuntimeError("PICM_BACKUP_FILE_UNSAFE")
        if sha256(old.read_bytes())!=m["source"][str(rel)]:
            raise RuntimeError("PICM_BACKUP_TAMPERED")
        current=sha256(live.read_bytes())
        if current not in (m["source"][str(rel)],m["installed"][str(rel)]):
            raise RuntimeError("PICM_ROLLBACK_REFUSES_NEWER_OWNER_CHANGES")
    for rel in FILES:
        live=APP/rel
        write_atomic(live,(b/rel).read_bytes(),live.stat().st_mode&0o777)
    restart()
    print("PICM_OWNER_DEFAULT_ROLLED_BACK")


if __name__=="__main__":
    if len(sys.argv)==5 and sys.argv[1]=="deploy":
        deploy(*sys.argv[2:])
    elif len(sys.argv)==3 and sys.argv[1]=="rollback":
        rollback(sys.argv[2])
    else:
        raise SystemExit("Usage: deploy RUN INDEX_SHA JS_SHA | rollback RUN")
