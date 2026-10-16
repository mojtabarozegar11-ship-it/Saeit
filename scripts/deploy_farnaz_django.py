#!/usr/bin/env python3
"""Install or safely roll back the isolated Farnaz Django subsite on cPanel."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

APP = Path("/home/zomorod2/Saeit-staging")
DOMAIN = Path("/home/zomorod2/mojplaywin.com")
BACKUPS = Path("/home/zomorod2/.mojplaywin-farnaz-backups")
PYTHON = Path("/home/zomorod2/virtualenv/Saeit-staging/3.11/bin/python")


def safe_regular(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def write_atomic(path: Path, text: str) -> None:
    temp = path.with_name(path.name + ".farnaz-new")
    temp.write_text(text, encoding="utf-8")
    os.chmod(temp, path.stat().st_mode & 0o777 if path.exists() else 0o644)
    os.replace(temp, path)


def updated_config(path: Path, before: str, after: str, label: str) -> str:
    text = path.read_text(encoding="utf-8")
    if after in text:
        return text
    if before not in text:
        raise RuntimeError(f"Expected safe insertion point missing in {label}")
    if text.count(before) != 1:
        raise RuntimeError(f"Ambiguous insertion point in {label}")
    return text.replace(before, after, 1)


def verify_layout() -> None:
    for path in (APP, DOMAIN):
        if not path.is_dir() or path.is_symlink():
            raise RuntimeError(f"Expected real directory: {path}")
    for path in (APP / "config/settings.py", APP / "config/urls.py",
                 APP / "manage.py", DOMAIN / ".htaccess"):
        if not safe_regular(path):
            raise RuntimeError(f"Expected regular file: {path}")
    if not PYTHON.is_file() or not os.access(PYTHON, os.X_OK):
        raise RuntimeError(f"Expected executable Django Python: {PYTHON}")
    if "Saeit-staging" not in (DOMAIN / "passenger_wsgi.py").read_text(encoding="utf-8", errors="replace"):
        raise RuntimeError("Passenger is not pointed at the expected staging source")


def restart_passenger() -> None:
    tmp = APP / "tmp"
    if tmp.exists() and (tmp.is_symlink() or not tmp.is_dir()):
        raise RuntimeError("Passenger restart directory is not a real directory")
    tmp.mkdir(exist_ok=True)
    (tmp / "restart.txt").touch()


def install(run_id: str, commit: str, stage: Path) -> None:
    verify_layout()
    payload = stage / "payload"
    package = payload / "farnaz"
    if not (package / "apps.py").is_file() or not (package / "migrations/0001_initial.py").is_file():
        raise RuntimeError("Farnaz app payload is incomplete")
    settings = APP / "config/settings.py"
    urls = APP / "config/urls.py"
    if not safe_regular(settings) or not safe_regular(urls):
        raise RuntimeError("Refusing to patch unsafe Django config files")

    backup = BACKUPS / run_id
    backup.mkdir(parents=True, exist_ok=False, mode=0o700)
    shutil.copy2(settings, backup / "settings.py")
    shutil.copy2(urls, backup / "urls.py")
    state = {"run_id": run_id, "commit": commit,
             "settings_sha256": hashlib.sha256(settings.read_bytes()).hexdigest(),
             "urls_sha256": hashlib.sha256(urls.read_bytes()).hexdigest()}
    (backup / "state.json").write_text(json.dumps(state, sort_keys=True), encoding="utf-8")

    try:
        new_settings = updated_config(
            settings, '    "core",',
            '    "core",\n    "farnaz.apps.FarnazConfig",',
            "INSTALLED_APPS",
        )
        new_urls = updated_config(
            urls, '    path("admin/", admin.site.urls),',
            '    path("farnaz/", include("farnaz.urls")),\n    path("admin/", admin.site.urls),',
            "urlpatterns",
        )
        if "from django.urls import include" not in new_urls and "from django.urls import include, path" not in new_urls:
            raise RuntimeError("Django URL include import is missing")
        write_atomic(settings, new_settings)
        write_atomic(urls, new_urls)
        app_dir = APP / "farnaz"
        if app_dir.exists() and (app_dir.is_symlink() or not app_dir.is_dir()):
            raise RuntimeError("Refusing to replace unsafe Farnaz app path")
        shutil.copytree(package, app_dir, dirs_exist_ok=True)
        subprocess.run([str(PYTHON), str(APP / "manage.py"), "check"], cwd=APP, check=True, timeout=90)
        subprocess.run([str(PYTHON), str(APP / "manage.py"), "migrate", "farnaz", "--noinput"], cwd=APP, check=True, timeout=180)
        route_check = (
            "from django.test import Client; "
            "response = Client(HTTP_HOST='mojplaywin.com').get('/farnaz/', secure=True); "
            "print('FARNAZ_DJANGO_CLIENT_STATUS=' + str(response.status_code)); "
            "assert response.status_code == 200"
        )
        subprocess.run([str(PYTHON), str(APP / "manage.py"), "shell", "-c", route_check],
                       cwd=APP, check=True, timeout=90)
        restart_passenger()
        print(f"FARNAZ_INSTALL_OK run={run_id} commit={commit}")
    except Exception:
        restore_config(run_id)
        restart_passenger()
        raise


def restore_config(run_id: str) -> None:
    backup = BACKUPS / run_id
    state_path = backup / "state.json"
    if not safe_regular(state_path):
        raise RuntimeError(f"Verified backup not found for run {run_id}")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    for name, key in (("settings.py", "settings_sha256"), ("urls.py", "urls_sha256")):
        source, target = backup / name, APP / "config" / name
        if not safe_regular(source) or not safe_regular(target):
            raise RuntimeError(f"Rollback file missing or unsafe: {name}")
        expected = state[key]
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise RuntimeError(f"Backup hash mismatch: {name}")
        shutil.copy2(source, target)
    # Keep the app code and database tables so any submitted enquiries remain recoverable.
    restart_passenger()
    print(f"FARNAZ_CONFIG_ROLLBACK_OK run={run_id}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("install", "rollback"))
    parser.add_argument("run_id")
    parser.add_argument("commit", nargs="?")
    parser.add_argument("stage", nargs="?")
    args = parser.parse_args()
    if args.action == "install":
        if not args.commit or not args.stage:
            parser.error("install requires run_id, commit SHA, and stage directory")
        install(args.run_id, args.commit, Path(args.stage))
    else:
        restore_config(args.run_id)


if __name__ == "__main__":
    main()
