#!/usr/bin/env python3
"""Main MojPlayWin-only additive cPanel release with exact-file backup and rollback.

A shared Passenger Django process also serves protected child sites. Do not replace
global settings, app URLs, public root, shared templates, or child paths. Verify
public child-site status before and after any graceful app reload.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone

ROOT=Path("/home/zomorod2/Saeit-staging")
WSGI=Path("/home/zomorod2/mojplaywin.com/passenger_wsgi.py")
PRIVATE=Path("/home/zomorod2/.private_mojplaywin_main_agents")
EVO=PRIVATE/"evolution_runtime_20261018"
MARKER=EVO/"mpw_five_live_enabled_20261019.json"
PYTHON="/home/zomorod2/virtualenv/Saeit-staging/3.11/bin/python"
FILES=(
  "command_center/models.py",
  "command_center/mpw_public.py",
  "command_center/mpw_workflow.py",
  "command_center/mpw_operations.py",
  "command_center/mpw_monitor_views.py",
  "command_center/mpw_private_telemetry.py",
  "command_center/migrations/__init__.py",
  "command_center/migrations/0001_mpw_record.py",
  "command_center/templatetags/__init__.py",
  "command_center/templatetags/mpw_main.py",
  "command_center/templates/command_center/mpw_operations.html",
  "command_center/templates/command_center/mpw_agent_monitor.html",
  "core/templates/mojplaywin/mpw_managed_blocks.html",
  "core/templates/mojplaywin/mpw_managed_offers.html",
)
PATCHED=(
  "command_center/urls.py",
  "command_center/templates/command_center/dashboard.html",
  "core/templates/mojplaywin/home.html",
  "core/templates/mojplaywin/store.html",
  "core/templates/mojplaywin/section.html",
)
GUARD="<!-- MPW_FIVE_MAIN_20261019 -->"


def require(condition,reason):
    if not condition: raise RuntimeError(reason)


def safe_file(path):
    if path.is_symlink(): raise RuntimeError("SYMLINK_BLOCKED:"+path.name)
    if path.exists() and not path.is_file(): raise RuntimeError("NONFILE_BLOCKED:"+path.name)


def precheck():
    require(ROOT.is_dir() and not ROOT.is_symlink(),"WRONG_APP_ROOT")
    require(WSGI.is_file() and not WSGI.is_symlink()
            and "APP='/home/zomorod2/Saeit-staging'" in WSGI.read_text("utf8","replace"),
            "PASSENGER_MAIN_APP_NOT_VERIFIED")
    require(Path(PYTHON).is_file(), "MAIN_VENV_MISSING")
    require(PRIVATE.is_dir() and EVO.is_dir()
            and not PRIVATE.is_symlink() and not EVO.is_symlink(),
            "MAIN_PRIVATE_ROOT_MISSING")
    require(ROOT.stat().st_uid==os.geteuid()==PRIVATE.stat().st_uid,"TENANT_OWNERSHIP_MISMATCH")
    require((ROOT/"command_center/urls.py").is_file(),"COMMAND_CENTER_MISSING")
    require((ROOT/"core/templates/mojplaywin/store.html").is_file(),"STORE_MISSING")
    store=(ROOT/"core/templates/mojplaywin/store.html").read_text("utf8","replace")
    require(store.count('id="mpw-sale-book72"')==1 and
            store.count('id="mpw-sale-book225"')==1,"PROTECTED_BOOK_CARDS_MISMATCH")
    for rel in FILES+PATCHED:
        safe_file(ROOT/rel)
    if MARKER.is_symlink(): raise RuntimeError("MAIN_MARKER_SYMLINK")
    require(MARKER.parent.stat().st_mode & 0o077==0,"MAIN_PRIVATE_PERMISSIONS_WEAK")


def patch_url(source):
    if "name=\"mpw_operations\"" in source:
        raise RuntimeError("MAIN_ROUTE_ALREADY_INSTALLED")
    marker="urlpatterns = ["
    require(marker in source,"UNEXPECTED_COMMAND_CENTER_URLS")
    extra=(
      'from .mpw_operations import desk as mpw_operations\n'
      'from .mpw_monitor_views import dashboard as mpw_monitor, telemetry_api as mpw_monitor_api\n'
    )
    source=extra+source
    entry=(
      '    path("mpw-operations/", mpw_operations, name="mpw_operations"),\n'
      '    path("mpw-agents/", mpw_monitor, name="mpw_agent_monitor"),\n'
      '    path("api/mpw-agents/", mpw_monitor_api, name="mpw_agent_monitor_api"),\n'
    )
    return source.replace(marker,marker+"\n"+entry,1)


def patch_dashboard(source):
    require("staff-nav" in source and "</nav>" in source,"UNEXPECTED_DASHBOARD")
    key='<nav class="staff-nav"'
    offset=source.find(key)
    require(offset>=0,"DASHBOARD_STAFF_NAV_ABSENT")
    end=source.find("</nav>",offset)
    require(end>offset,"DASHBOARD_NAV_TERMINATOR_MISSING")
    links=(
      ' <a href="/staff/command-center/mpw-operations/">مدیریت سایت اصلی، کارت‌ها و فروشگاه</a>'
      ' <a href="/staff/command-center/mpw-agents/">پایش واقعی ربات‌ها و ایجنت‌ها</a>'
    )
    return source[:end]+links+source[end:]


def patch_template(source,rel):
    require("{% endblock %}" in source,"PAGE_CONTENT_BLOCK_ABSENT")
    require("{% extends \"base.html\" %}" in source[:350],"UNEXPECTED_LIVE_MPW_TEMPLATE_PARENT")
    if GUARD in source: raise RuntimeError("MAIN_PAGE_ALREADY_INTEGRATED")
    loader='{% load mpw_main %}'
    if loader not in source:
        if "{% load static %}" in source:
            source=source.replace("{% load static %}","{% load static %}\n"+loader,1)
        else:
            spot=source.find("{% block title %}")
            require(spot>0,"PAGE_TAG_INSERT_POINT_ABSENT")
            source=source[:spot]+loader+"\n"+source[spot:]
    block=(
       '\n'+GUARD+'\n'
       '{% mpw_main_data request as mpw_data %}\n'
       '{% if mpw_data.mpw_managed_blocks %}'
       '{% include "mojplaywin/mpw_managed_blocks.html" %}{% endif %}\n'
    )
    if rel.endswith("/store.html"):
        block+=('{% if mpw_data.mpw_managed_offers %}'
               '{% include "mojplaywin/mpw_managed_offers.html" %}{% endif %}\n')
    idx=source.rfind("{% endblock %}")
    return source[:idx]+block+source[idx:]


def atomic_write(path,contents,original_mode=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    require(not path.is_symlink(),"SYMLINK_RACE")
    fd,temp=tempfile.mkstemp(prefix=".mpw5-",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(contents)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temp,original_mode if original_mode is not None else 0o600)
        os.replace(temp,path)
    finally:
        if os.path.lexists(temp):os.unlink(temp)


def run_checked(command,timeout=100):
    done=subprocess.run(command,cwd=str(ROOT),capture_output=True,text=True,timeout=timeout)
    if done.returncode:
        raise RuntimeError("COMMAND_FAILED:"+command[-1]+":"+str(done.returncode)+":"+done.stderr[-260:])
    return done.stdout.strip()


def load_manifest(stage):
    manifest=stage/"manifest.json"
    require(manifest.is_file() and not manifest.is_symlink(),"ROLLBACK_MANIFEST_MISSING")
    obj=json.loads(manifest.read_text("utf8"))
    require(obj.get("tenant")=="mojplaywin-main","ROLLBACK_WRONG_TENANT")
    require(set(obj["originals"])==set(FILES+PATCHED),"ROLLBACK_PATHS_MISMATCH")
    return obj


def rollback(stage):
    precheck()
    obj=load_manifest(stage)
    for rel,info in obj["originals"].items():
        path=ROOT/rel
        safe_file(path)
        if info["exists"]:
            copy=stage/"backup"/rel
            require(copy.is_file() and not copy.is_symlink(),"BACKUP_FILE_MISSING:"+rel)
            require(hashlib.sha256(copy.read_bytes()).hexdigest()==info["sha256"],"BACKUP_CORRUPTED:"+rel)
            atomic_write(path,copy.read_bytes(),info["mode"])
        elif path.exists():
            path.unlink()
    if obj.get("marker_created") and MARKER.is_file() and not MARKER.is_symlink():
        MARKER.unlink()
    if obj.get("passenger_reload_requested"):
        (ROOT/"tmp").mkdir(exist_ok=True)
        (ROOT/"tmp/restart.txt").touch()
    print("MPW_FIVE_ROLLBACK=restored_original_files")
    print("MPW_FIVE_DB_TABLE=preserved_for_data_safety")


def install(stage):
    precheck()
    manifest_path=stage/"manifest.json"
    require(not manifest_path.exists(),"RELEASE_STAGE_ALREADY_USED")
    pack=stage/"payload.tar.gz"
    require(pack.is_file() and not pack.is_symlink() and pack.stat().st_size < 700000,
            "INVALID_RELEASE_PAYLOAD")
    originals={}
    for rel in FILES+PATCHED:
        f=ROOT/rel
        exists=f.is_file()
        raw=f.read_bytes() if exists else b""
        originals[rel]={"exists":exists,"mode":stat.S_IMODE(f.stat().st_mode) if exists else 0o600,
                         "sha256":hashlib.sha256(raw).hexdigest() if exists else None}
        if exists:
            target=stage/"backup"/rel
            target.parent.mkdir(parents=True,exist_ok=True)
            atomic_write(target,raw,0o600)
    obj={"tenant":"mojplaywin-main","created":datetime.now(timezone.utc).isoformat(),
         "originals":originals,"marker_created":False,"passenger_reload_requested":False}
    atomic_write(manifest_path,json.dumps(obj,sort_keys=True).encode(),0o600)
    try:
        with tarfile.open(pack,"r:gz") as archive:
            members=archive.getmembers()
            require(set(m.name for m in members)==set(FILES),"PAYLOAD_FILE_LIST_MISMATCH")
            require(all(m.isfile() and m.size < 250000 and not m.issym() and not m.islnk()
                        for m in members),"PAYLOAD_UNSAFE_ARCHIVE")
            for item in members:
                stream=archive.extractfile(item)
                require(stream is not None,"INVALID_PAYLOAD_DATA")
                contents=stream.read()
                atomic_write(ROOT/item.name,contents,originals[item.name]["mode"])
        for rel in PATCHED:
            current=(ROOT/rel).read_text("utf8","replace")
            if rel=="command_center/urls.py":
                revised=patch_url(current)
            elif rel.endswith("/dashboard.html"):
                revised=patch_dashboard(current)
            else:
                revised=patch_template(current,rel)
            atomic_write(ROOT/rel,revised.encode("utf8"),originals[rel]["mode"])
        run_checked([PYTHON,"manage.py","check"],timeout=100)
        # Only create the isolated command_center table; never run all-site migrations.
        run_checked([PYTHON,"manage.py","migrate","command_center","--noinput"],timeout=150)
        test_code=(
            "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');"
            "import django; django.setup();"
            "from django.db import connection;"
            "from django.urls import reverse;"
            "from command_center.models import MpwRecord;"
            "assert 'command_center_mpwrecord' in connection.introspection.table_names(), 'MPW_DB_TABLE_MISSING';"
            "assert reverse('mpw_operations').endswith('/mpw-operations/'), 'MPW_REVERSE_OPERATIONS_FAIL';"
            "assert reverse('mpw_agent_monitor').endswith('/mpw-agents/'), 'MPW_REVERSE_MONITOR_FAIL';"
            "from django.test import Client;"
            "c=Client(HTTP_HOST='mojplaywin.com');"
            "assert c.get('/store/',secure=True).status_code==200, 'MPW_STORE_HTTPS_SMOKE_FAILED';"
            "assert c.get('/staff/command-center/mpw-operations/',secure=True).status_code==302, 'MPW_PRIVATE_AUTH_SMOKE_FAILED';"
            "print('MPW_DJANGO_MAIN_ONLY_TESTS=passed')"
        )
        run_checked([PYTHON,"-c",test_code],timeout=90)
        # Main-only switch; checkout stays hard-disabled.
        require(not MARKER.exists(),"MAIN_FEATURE_MARKER_ALREADY_PRESENT")
        atomic_write(MARKER,json.dumps({"tenant":"mojplaywin-main","enabled":True,"schema":1}).encode(),0o600)
        obj["marker_created"]=True
        atomic_write(manifest_path,json.dumps(obj,sort_keys=True).encode(),0o600)
        # Verify marked public pages through fresh Django before reloading any service.
        live_test=(
            "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings');"
            "import django; django.setup();"
            "from django.test import Client;"
            "from command_center.mpw_public import feature_enabled;"
            "assert feature_enabled('MPW_CONTROL_ENABLED'), 'MPW_MAIN_MARKER_UNREADABLE';"
            "c=Client(HTTP_HOST='mojplaywin.com');"
            "assert c.get('/',secure=True).status_code==200, 'MPW_MAIN_RENDER_FAILED';"
            "assert c.get('/store/',secure=True).status_code==200, 'MPW_STORE_RENDER_FAILED';"
            "print('MPW_FIVE_MAIN_MARKED_VIEWS=200')"
        )
        run_checked([PYTHON,"-c",live_test],timeout=100)
        # Passenger graceful recycle; external HTTP tests MUST validate child paths.
        (ROOT/"tmp").mkdir(exist_ok=True)
        (ROOT/"tmp/restart.txt").touch()
        obj["passenger_reload_requested"]=True
        atomic_write(manifest_path,json.dumps(obj,sort_keys=True).encode(),0o600)
        print("MPW_FIVE_DEPLOY=applied_with_graceful_reload")
        print("MPW_FIVE_PAYMENT=disabled_until_separate_wallet_test")
        print("MPW_FIVE_BACKUP=private_release_stage")
    except BaseException:
        rollback(stage)
        raise


def main():
    require(len(sys.argv)==3 and sys.argv[1] in ("install","rollback"),"USAGE")
    run_id=sys.argv[2]
    require(re.fullmatch(r"[0-9]{6,20}",run_id) is not None,"INVALID_RELEASE_ID")
    stage=PRIVATE/"mpw_five_releases"/run_id
    require(stage.is_dir() and not stage.is_symlink(),"RELEASE_STAGE_MISSING")
    if sys.argv[1]=="install": install(stage)
    else: rollback(stage)


if __name__=="__main__":
    main()
