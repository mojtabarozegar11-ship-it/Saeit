"""Guarded replacement of three dashboard evidence files only.

Must run on the authorized cPanel host after a private staging test. Does not
migrate a database, publish orders or touch the factory VPS.
"""
from __future__ import annotations
import datetime
import fcntl
import hashlib
import os
from pathlib import Path
import secrets
import shutil
import stat
import subprocess
import tempfile
import time

HOME=Path("/home/zomorod2")
SITE=HOME/"Saeit-staging"
WEB=HOME/"mojplaywin.com"
STAGE=HOME/".mpw-evidence-package-20261014"
BACKUPS=HOME/".mpw-evidence-release-backups"
PYTHON=HOME/"virtualenv/Saeit-staging/3.11/bin/python"
FILES=(
    ("command_center/urls.py","5f4e5c4acfb988ec776b9f83ecd0b4ee065b85c4","a059beeb76c508f9443b81de8a0b1f2827412224"),
    ("command_center/templates/command_center/dashboard.html","fd351be7235979a7b1f11fbf03f0112f2595c560","11d6e1922f0ea10ae8ab72f7f208f0e2414d7fb6"),
    ("command_center/evidence_metrics.py",None,"db7ab7ff7a5f5c3645306665379dbc27c7ffb41f"),
)


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest()


def check_paths():
    import pwd
    assert pwd.getpwuid(os.getuid()).pw_name=="zomorod2"
    assert SITE.is_dir() and WEB.is_dir() and PYTHON.is_file()
    assert STAGE.is_dir() and not STAGE.is_symlink()
    assert not BACKUPS.is_symlink()
    assert "/home/zomorod2/Saeit-staging" in (WEB/"passenger_wsgi.py").read_text()
    restart=WEB/"tmp/restart.txt"
    assert restart.parent.is_dir() and not restart.parent.is_symlink()
    assert not restart.is_symlink()
    assert "command_center" in (SITE/"config/settings.py").read_text()
    assert "staff/command-center/" in (SITE/"config/urls.py").read_text()
    return restart


def original_snapshot():
    records={}
    for rel,old_sha,new_sha in FILES:
        current=SITE/rel
        incoming=STAGE/rel
        assert incoming.is_file() and not incoming.is_symlink(), "Candidate missing"
        incoming_content=incoming.read_bytes()
        assert git_blob(incoming_content)==new_sha, "Candidate hash mismatch"
        if rel.endswith(".py"):
            compile(incoming_content.decode("utf-8"),str(incoming),"exec")
        if old_sha is None:
            assert not current.exists() and not current.is_symlink(), "New API already present"
            records[rel]=(None,0o640,incoming_content)
        else:
            assert current.is_file() and not current.is_symlink()
            original=current.read_bytes()
            assert git_blob(original)==old_sha, "Live file differs from approved release"
            mode=stat.S_IMODE(current.stat().st_mode)
            records[rel]=(original,mode,incoming_content)
    return records


def atomic_write(path,data,mode):
    assert path.parent.is_dir() and not path.parent.is_symlink()
    handle,temp=tempfile.mkstemp(prefix=".mpw-evidence-",dir=str(path.parent))
    try:
        with os.fdopen(handle,"wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp,mode)
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def smoke_http(paths):
    result={}
    for route in paths:
        args=["curl","-sS","--connect-timeout","8","--max-time","15",
              "-o","/dev/null","-w","%{http_code}",
              "https://mojplaywin.com"+route]
        call=subprocess.run(args,capture_output=True,text=True,timeout=20,check=False)
        assert call.returncode==0 and call.stdout.strip().isdigit(), "HTTPS request failed"
        code=int(call.stdout.strip())
        assert 200<=code<500, "Public endpoint unhealthy"
        result[route]=code
    return result


def django_smoke():
    code="""
import django
django.setup()
from django.core.checks import run_checks, Tags
from django.urls import resolve, reverse
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from types import SimpleNamespace
import json
from command_center.evidence_metrics import evidence_metrics
from command_center.views import dashboard
from core.models import Agent, Product, Order, PaymentIntent
assert not any(m.id=='urls.W005' for m in run_checks(tags=[Tags.urls]))
assert resolve('/admin/').view_name=='admin:index'
assert resolve('/staff/').view_name=='staff_admin:index'
assert reverse('command_center_evidence_metrics_api')=='/staff/command-center/api/evidence/'
factory=RequestFactory()
anon=factory.get('/staff/command-center/api/evidence/',HTTP_HOST='mojplaywin.com')
anon.user=AnonymousUser()
assert evidence_metrics(anon).status_code==302
staff=SimpleNamespace(is_authenticated=True,is_staff=True,is_active=True,is_superuser=True)
req=factory.get('/staff/command-center/api/evidence/',HTTP_HOST='mojplaywin.com')
req.user=staff
response=evidence_metrics(req)
assert response.status_code==200 and 'no-store' in response['Cache-Control']
data=json.loads(response.content)
assert data['agents']['registered']==Agent.objects.count()
assert data['catalog']['products']==Product.objects.count()
assert data['orders']['total']==Order.objects.count()
assert data['payments']['intents']==PaymentIntent.objects.count()
assert data['revenue']['verified_amounts_by_currency'] is None
assert data['factory']['state']=='unknown'
page=factory.get('/staff/command-center/',HTTP_HOST='mojplaywin.com')
page.user=staff
body=dashboard(page)
assert body.status_code==200 and b'staff-commerce' in body.content
print('MPW_EVIDENCE_DJANGO_CHECK_OK=True')
"""
    env=dict(os.environ,DJANGO_SETTINGS_MODULE="config.settings",PYTHONDONTWRITEBYTECODE="1")
    completed=subprocess.run([str(PYTHON),"-c",code],cwd=SITE,
        env=env,capture_output=True,text=True,timeout=95)
    if completed.returncode!=0 or "MPW_EVIDENCE_DJANGO_CHECK_OK=True" not in completed.stdout:
        raise RuntimeError("Django evidence test failed")
    print("MPW_EVIDENCE_DJANGO_CHECK_OK=True")


def main():
    restart=check_paths()
    paths=("/", "/admin/", "/staff/", "/store/")
    before=smoke_http(paths)
    records=original_snapshot()
    BACKUPS.mkdir(parents=True,exist_ok=True,mode=0o700)
    BACKUPS.chmod(0o700)
    with (BACKUPS/".deployment-lock").open("a+") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        checkpoint=BACKUPS/(datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+secrets.token_hex(4))
        checkpoint.mkdir(mode=0o700)
        for rel,(old,mode,new) in records.items():
            if old is not None:
                dest=checkpoint/(rel.replace("/","--"))
                dest.write_bytes(old)
                dest.chmod(0o600)
                assert dest.read_bytes()==old
        print("MPW_EVIDENCE_PRIVATE_PREIMAGE_BACKUPS_VERIFIED=True")
        applied=[]
        try:
            for rel,(old,mode,new) in records.items():
                current=SITE/rel
                assert (current.read_bytes() if old is not None else None)==old
                atomic_write(current,new,mode)
                applied.append(rel)
            django_smoke()
            restart.touch()
            good=False
            for _ in range(7):
                time.sleep(3)
                try:
                    after=smoke_http(paths)
                    good=all(before[k]>=400 or after[k]<400 for k in paths)
                    if good:
                        break
                except Exception:
                    continue
            if not good:
                raise RuntimeError("Public site smoke failed")
            print("MPW_EVIDENCE_PUBLIC_SITE_SMOKE_OK=True")
            print("MPW_EVIDENCE_LIVE_API_DEPLOYED=True")
            print("MPW_EVIDENCE_NO_DB_MIGRATION_OR_PAYMENT_CHANGES=True")
        except BaseException:
            for rel in reversed(applied):
                old,mode,new=records[rel]
                if old is None:
                    (SITE/rel).unlink(missing_ok=True)
                else:
                    atomic_write(SITE/rel,old,mode)
            restart.touch()
            print("MPW_EVIDENCE_ROLLBACK_EXECUTED=True")
            raise


if __name__=="__main__":
    main()
