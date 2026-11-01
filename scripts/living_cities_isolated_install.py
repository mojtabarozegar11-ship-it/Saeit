#!/usr/bin/env python3
"""Confined Living Cities private installation and guarded first publication.

Modes: prepare | publish | rollback
Only manages /home/zomorod2/.private/living-cities-app and
/home/zomorod2/public_html/living-cities. No existing site files edited.
"""
import hashlib
import io
import json
import os
import secrets
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

SOURCE_SHA = "b3fe1b772368f3f0874481ab88ad82862bd24de2"
ARCHIVE_SHA = "aab0387619fecaf2ed5c181abab5ef775142ff1512c39c2a015de135775c744c"
HOME = Path("/home/zomorod2")
ROOT = HOME / ".private" / "living-cities-app"
RELEASE = ROOT / "releases" / SOURCE_SHA
STATE = ROOT / "state"
ARCHIVE = ROOT / "source.tgz"
PUBLIC = HOME / "public_html" / "living-cities"
OWNER_MARKER = "LC-OWNER-PINNED-" + SOURCE_SHA

def require(condition, message):
    if not condition:
        raise RuntimeError(message)

def safe_layout():
    require(HOME.is_dir() and not HOME.is_symlink(), "unexpected_account_home")
    require((HOME/"public_html").is_dir() and not (HOME/"public_html").is_symlink(), "unexpected_docroot")
    for path in (ROOT, ROOT/"releases", RELEASE, STATE, PUBLIC, ARCHIVE):
        require(not path.is_symlink(), "symlink_path_rejected:" + path.name)
    require(os.geteuid() == HOME.stat().st_uid, "unexpected_cpanel_owner")

def run(args, cwd=None, timeout=330, env=None):
    proc = subprocess.run(args, cwd=str(cwd) if cwd else None, env=env,
                          check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          universal_newlines=True, timeout=timeout)
    if proc.returncode:
        # Do not print secrets or full environment; emit last bounded tool output.
        print("ISOLATED_GAME_COMMAND_FAILED=" + str(args[:3]))
        print((proc.stdout or "")[-3500:])
        raise RuntimeError("command_failed_exit_" + str(proc.returncode))
    print("ISOLATED_GAME_STEP_PASS=" + str(args[1] if len(args)>1 else args[0]))
    return proc.stdout

def candidate_python():
    candidates = [
        "/opt/alt/python310/bin/python3.10",
        "/opt/alt/python310/bin/python",
        "/home/zomorod2/virtualenv/Saeit/3.10/bin/python",
        "/home/zomorod2/virtualenv/repositories/Saeit/3.10/bin/python",
        "/opt/alt/python311/bin/python3.11",
        "/usr/local/bin/python3.11",
        "/usr/bin/python3.11",
        "/usr/bin/python3.10",
        sys.executable,
    ]
    for name in candidates:
        p = Path(name)
        if not p.is_file() or p.is_symlink():
            continue
        try:
            out=subprocess.check_output([name,"-c",
                "import sys;print(int(sys.version_info >= (3,10)))"],
                stderr=subprocess.DEVNULL,timeout=8).decode().strip()
            if out == "1":
                print("ISOLATED_PYTHON_SELECTED=" + str(p))
                return name
        except (OSError, subprocess.SubprocessError):
            continue
    raise RuntimeError("no_independent_python_3_10_or_newer")

def safe_extract(payload, dest):
    require(not dest.exists(), "release_already_exists")
    dest.mkdir(mode=0o700, parents=True)
    try:
        with tarfile.open(fileobj=io.BytesIO(payload),mode="r:gz") as archive:
            items=archive.getmembers()
            require(100 < len(items) < 2000, "unexpected_payload_members")
            for entry in items:
                name=Path(entry.name)
                require(not name.is_absolute() and ".." not in name.parts, "tar_path_traversal")
                require(entry.isfile() or entry.isdir(), "tar_link_or_device_rejected")
                require(name.parts and name.parts[0] in ("manage.py","requirements.txt","config","apps","templates"),
                        "unapproved_tar_root")
                target=dest/name
                if entry.isdir():
                    target.mkdir(parents=True,exist_ok=True)
                    target.chmod(0o700)
                else:
                    target.parent.mkdir(parents=True,exist_ok=True)
                    with archive.extractfile(entry) as incoming, target.open("wb") as outgoing:
                        shutil.copyfileobj(incoming,outgoing)
                    target.chmod(0o600)
        require((dest/"manage.py").is_file() and (dest/"config/settings.py").is_file(), "incomplete_source")
    except Exception:
        shutil.rmtree(str(dest))
        raise

def configure_release():
    settings=RELEASE/"config/settings.py"
    s=settings.read_text()
    require("LC_ISOLATED_PROD_CONFIGURATION" not in s, "release_already_configured")
    s += """

# LC_ISOLATED_PROD_CONFIGURATION
STATIC_URL = "/living-cities/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DATABASES["default"] = {"ENGINE":"django.db.backends.sqlite3",
                        "NAME":Path(os.environ["LIVING_CITIES_STATE_DB_PATH"]),
                        "OPTIONS":{"timeout":20}}
SESSION_COOKIE_NAME = "lc_zm_session_v1"
CSRF_COOKIE_NAME = "lc_zm_csrf_v1"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
"""
    settings.write_text(s)
    (RELEASE/"config/urls.py").write_text("""from django.urls import path,include
from django.http import JsonResponse
from apps.living_cities.client import play
from apps.identity.api import login_view,logout_view,me_view
def health(_request):
    return JsonResponse({"game":"living-cities","ready":True,"payment_enabled":False})
urlpatterns=[
    path("play/",play),
    path("api/living-cities/",include("apps.living_cities.urls")),
    path("api/auth/login/",login_view),
    path("api/auth/logout/",logout_view),
    path("api/auth/me/",me_view),
    path("health/",health),
]
""")
    for name in ("app.mjs", "tycoon-panel.mjs"):
        file=RELEASE/"apps/living_cities/static/living_cities"/name
        js=file.read_text()
        require("/api/living-cities/" in js, "expected_client_api_route_missing:"+name)
        js=js.replace("/api/living-cities/","/living-cities/api/living-cities/")
        js=js.replace("/api/auth/","/living-cities/api/auth/")
        file.write_text(js)
    (RELEASE/"passenger_wsgi.py").write_text("""import sys,os
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root))
os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
from config.wsgi import application
""")
    (RELEASE/".env").write_text(
        "DEBUG=False\nALLOWED_HOSTS=zomorodmelal.ir\n"
        "CSRF_TRUSTED_ORIGINS=https://zomorodmelal.ir\n"
        "SECURE_SSL_REDIRECT=False\n"
        "SECRET_KEY=" + secrets.token_urlsafe(56) + "\n"
        "LIVING_CITIES_CODE_PEPPER=" + secrets.token_urlsafe(56) + "\n"
        "LIVING_CITIES_STATE_DB_PATH=" + str(STATE/"game.sqlite3") + "\n")
    (RELEASE/".env").chmod(0o600)
    print("ISOLATED_DJANGO_ROUTING_CONFIGURED=PASS")

def prepare():
    safe_layout()
    require(not PUBLIC.exists(), "public_route_already_owned_do_not_overwrite")
    require(not RELEASE.exists(), "release_directory_already_exists")
    require(not (STATE/"game.sqlite3").exists(), "existing_database_requires_separate_backup_upgrade")
    require(ARCHIVE.is_file() and not ARCHIVE.is_symlink(), "missing_source_archive")
    payload=ARCHIVE.read_bytes()
    require(hashlib.sha256(payload).hexdigest() == ARCHIVE_SHA, "source_archive_sha_mismatch")
    require(shutil.disk_usage(str(HOME)).free > 500*1024*1024, "insufficient_disk")
    (ROOT/"releases").mkdir(parents=True,mode=0o700,exist_ok=True)
    STATE.mkdir(parents=True,mode=0o700,exist_ok=True)
    safe_extract(payload,RELEASE)
    configure_release()
    interpreter=candidate_python()
    try:
        run([interpreter,"-m","venv",str(RELEASE/".venv")],cwd=RELEASE,timeout=90)
        py=str(RELEASE/".venv/bin/python")
        require(Path(py).is_file(), "isolated_venv_missing")
        run([py,"-m","pip","install","--disable-pip-version-check","--no-cache-dir",
             "Django==5.2.17","python-dotenv>=1.0,<2.0"],cwd=RELEASE,timeout=310)
        env=os.environ.copy()
        env["DJANGO_SETTINGS_MODULE"]="config.settings"
        env["PYTHONPATH"]=str(RELEASE)
        run([py,"manage.py","check"],cwd=RELEASE,timeout=45,env=env)
        run([py,"manage.py","migrate","--noinput"],cwd=RELEASE,timeout=115,env=env)
        run([py,"manage.py","migrate","--check"],cwd=RELEASE,timeout=45,env=env)
        run([py,"manage.py","collectstatic","--noinput"],cwd=RELEASE,timeout=90,env=env)
        qa="""import django;django.setup()
from django.test import Client
from pathlib import Path
from django.conf import settings
res=Client().get('/play/',HTTP_HOST='zomorodmelal.ir',secure=True)
assert res.status_code==200,('play_status',res.status_code)
assert b'LIVING CITIES' in res.content
assert b'/living-cities/static/living_cities/app.mjs' in res.content
assert (Path(settings.STATIC_ROOT)/'living_cities/app.mjs').is_file()
policy=Client().get('/api/living-cities/rewards/moj1-policy/',HTTP_HOST='zomorodmelal.ir',secure=True)
assert policy.status_code==200
assert policy.json().get('recipient_payout_enabled') is False
print('LOCAL_ISOLATED_DJANGO_QA=PASS')
"""
        run([py,"-c",qa],cwd=RELEASE,timeout=40,env=env)
        (RELEASE/"LC_VALIDATED.json").write_text(json.dumps(
            {"owner":OWNER_MARKER,"source":SOURCE_SHA,"archive":ARCHIVE_SHA,
             "app_root":str(RELEASE),"python":py},sort_keys=True))
        print("PRIVATE_CPANEl_RELEASE_PREPARED=PASS")
    except Exception:
        # Preserve failed private work for diagnosis without exposing public URLs.
        raise

def publish():
    safe_layout()
    require(not PUBLIC.exists(), "public_route_conflict_stop")
    manifest=RELEASE/"LC_VALIDATED.json"
    require(manifest.is_file(), "no_private_QA_manifest")
    info=json.loads(manifest.read_text())
    require(info.get("owner")==OWNER_MARKER and info.get("source")==SOURCE_SHA,"untrusted_release_manifest")
    py=Path(info["python"])
    require(py.is_file(),"release_python_missing")
    require((STATE/"game.sqlite3").is_file(), "database_not_ready")
    stage=HOME/"public_html"/(".living-cities-owned-"+SOURCE_SHA[:10]+".pending")
    require(not stage.exists() and not stage.is_symlink(),"public_stage_conflict")
    stage.mkdir(mode=0o700)
    try:
        shutil.copytree(RELEASE/"staticfiles",stage/"static")
        (stage/"static"/".htaccess").write_text("PassengerEnabled off\nOptions -Indexes\n")
        (stage/".htaccess").write_text(
           "# "+OWNER_MARKER+"\n"
           "PassengerEnabled on\n"
           "PassengerBaseURI /living-cities\n"
           "PassengerAppRoot "+str(RELEASE)+"\n"
           'PassengerPython "/opt/alt/python310/bin/lswsgi"\n'
           'SetEnv LS_PYTHONBIN "'+str(py)+'"\n'
           'SetEnv PYTHONHOME "'+str(RELEASE/".venv")+'"\n'
           'SetEnv PYTHONPATH "'+str(RELEASE)+'"\n'
           "PassengerAppEnv production\n"
           "PassengerFriendlyErrorPages off\n"
           "Options -Indexes\n")
        (stage/"LC-OWNER.txt").write_text(OWNER_MARKER+"\n")
        for p in stage.rglob("*"):
            if p.is_file(): p.chmod(0o644)
            elif p.is_dir(): p.chmod(0o755)
        stage.chmod(0o755)
        stage.rename(PUBLIC)
        print("PUBLIC_SCOPED_APP_DIRECTORY_PUBLISHED=PASS")
    except Exception:
        if stage.exists():shutil.rmtree(str(stage))
        raise

def rollback():
    safe_layout()
    if not PUBLIC.exists():
        print("NO_MANAGED_PUBLIC_GAME_TO_REVERT")
        return
    require(PUBLIC.is_dir() and not PUBLIC.is_symlink(),"unsafe_public_target")
    marker=PUBLIC/"LC-OWNER.txt"
    htaccess=PUBLIC/".htaccess"
    require(marker.is_file() and marker.read_text().strip()==OWNER_MARKER,"game_marker_mismatch")
    require(htaccess.is_file() and OWNER_MARKER in htaccess.read_text(),"game_route_changed_by_another_owner")
    quarantine=ROOT/"quarantine"/("rolled-back-"+SOURCE_SHA)
    quarantine.parent.mkdir(parents=True,mode=0o700,exist_ok=True)
    require(not quarantine.exists(),"quarantine_already_exists")
    PUBLIC.rename(quarantine)
    print("PUBLIC_LIVING_CITIES_ROLLED_BACK_ONLY_MANAGED_PATH=PASS")

if __name__ == "__main__":
    require(len(sys.argv)==2 and sys.argv[1] in ("prepare","publish","rollback"),"invalid_mode")
    {"prepare":prepare,"publish":publish,"rollback":rollback}[sys.argv[1]]()
