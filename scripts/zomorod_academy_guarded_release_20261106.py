#!/usr/bin/env python3
"""Surgical cPanel academy release with exact SHA guards and rollback.

The GitHub runner packs reviewed repository bytes into PACKED_FILES; this runs
as the unprivileged zomorod2 user on the existing Passenger application.
Never replaces config/urls.py wholesale or touches DB, payments or other sites.
"""
from __future__ import annotations

import base64
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

PACKED_FILES = None  # Replaced with exact reviewed academy source files on runner.
HOME = Path('/home/zomorod2')
APP = HOME / 'Saeit'
BACKUP_ROOT = HOME / '.backups/zomorod-academy-guarded-20261106'
EXPECTED_OLD = {
    'config/settings.py': '02befe24a8a2636c498b51f4ad1fe7b237c636ec37f026a9e74209ee4eb9b6c5',
    'core/academy_views.py': '8e53348804828cb72a255efd517f206a12d8d1ded08a3f74a4a6c14174c5b3b0',
    'config/urls.py': '6ef4ac41e979926a8bed074007bdc788aadafefb4faa3edd0cffb578ebba28db',
}
NEW_NAMES = (
    'core/templates/core/academy.html',
    'core/templates/core/education_catalog_filters.html',
    'core/templates/core/education_course_detail.html',
    'core/templates/core/education_dashboard.html',
    'core/templates/core/education_lesson.html',
    'core/templates/core/education_assessment.html',
    'core/templates/core/education_assessment_result.html',
    'core/templates/core/education_certificate.html',
    'core/templates/registration/login.html',
)
REVIEWED_NAMES = tuple(k for k in EXPECTED_OLD if k != 'config/urls.py') + NEW_NAMES
VENV_PYTHON = HOME / 'virtualenv/Saeit/3.10/bin/python'


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def release_id(value: str) -> str:
    if not re.fullmatch(r'[0-9]{6,20}', value):
        raise RuntimeError('INVALID_RELEASE_ID')
    return value


def files() -> dict[str, bytes]:
    if not isinstance(PACKED_FILES, dict) or set(PACKED_FILES) != set(REVIEWED_NAMES):
        raise RuntimeError('ACADEMY_PACKAGE_INCOMPLETE')
    result = {name: base64.b64decode(PACKED_FILES[name], validate=True) for name in REVIEWED_NAMES}
    if b'LOGIN_URL = "/accounts/login/"' not in result['config/settings.py']:
        raise RuntimeError('ACADEMY_SETTINGS_CONTRACT_FAILED')
    if b'status__in=("active", "completed")' not in result['core/academy_views.py']:
        raise RuntimeError('ACADEMY_VIEWS_CONTRACT_FAILED')
    if b'{% csrf_token %}' not in result['core/templates/registration/login.html']:
        raise RuntimeError('LOGIN_CSRF_REQUIRED')
    for name, data in result.items():
        if not data or len(data) > 200_000 or b'\x00' in data:
            raise RuntimeError('ACADEMY_PACKAGE_SIZE_OR_CONTENT_INVALID:' + name)
    return result


def patched_urls(original: bytes) -> bytes:
    text = original.decode('utf-8')
    if ('accounts/login/' in text or 'accounts/logout/' in text or
            text.count('from django.contrib import admin') != 1 or
            text.count('urlpatterns = [') != 1 or
            not ('name="education"' in text or "name='education'" in text) or
            'from django.urls import' not in text):
        raise RuntimeError('ACADEMY_URL_PATCH_CONTEXT_CHANGED')
    text = text.replace(
        'from django.contrib import admin',
        'from django.contrib import admin\nfrom django.contrib.auth.views import LoginView, LogoutView', 1,
    )
    text = text.replace(
        'urlpatterns = [',
        '''urlpatterns = [
    # Guarded academy login: retain all pre-existing business and public routes.
    path("accounts/login/", LoginView.as_view(
        template_name="registration/login.html", redirect_authenticated_user=True,
    ), name="login"),
    path("accounts/logout/", LogoutView.as_view(next_page="education"), name="logout"),''',
        1,
    )
    compile(text, 'config/urls.py', 'exec')
    return text.encode('utf-8')


def guarded_host() -> None:
    if os.geteuid() == 0 or os.geteuid() != HOME.stat().st_uid:
        raise RuntimeError('CPANEL_USER_MISMATCH')
    if APP.is_symlink() or not APP.is_dir() or not (APP / 'manage.py').is_file():
        raise RuntimeError('PASSENGER_APP_ROOT_INVALID')
    root_config = HOME / 'public_html/.htaccess'
    if root_config.is_symlink() or not root_config.is_file():
        raise RuntimeError('ROOT_CONFIG_NOT_VERIFIED')
    if not any('PassengerAppRoot' in line and '/home/zomorod2/Saeit' in line
               for line in root_config.read_text(errors='replace').splitlines()):
        raise RuntimeError('ROOT_PASSENGER_ROUTE_CHANGED')
    for name in EXPECTED_OLD:
        p = APP / name
        if p.is_symlink() or not p.is_file() or not p.parent.is_dir() or p.parent.is_symlink():
            raise RuntimeError('EXISTING_TARGET_INVALID:' + name)
    for rel in ('core/templates', 'core/templates/core'):
        p = APP / rel
        if p.is_symlink() or not p.is_dir():
            raise RuntimeError('ACADEMY_TEMPLATE_PARENT_INVALID:' + rel)
    if not (APP / 'templates/base.html').is_file() or not VENV_PYTHON.is_file():
        raise RuntimeError('ACADEMY_TEMPLATE_BASE_OR_VENV_MISSING')
    if BACKUP_ROOT.is_symlink() or (BACKUP_ROOT.exists() and not BACKUP_ROOT.is_dir()):
        raise RuntimeError('ACADEMY_BACKUP_ROOT_UNSAFE')
    dest = APP / 'core/templates/registration'
    if dest.is_symlink() or (dest.exists() and not dest.is_dir()):
        raise RuntimeError('LOGIN_TEMPLATE_PARENT_UNSAFE')


def old_data() -> dict[str, bytes]:
    return {name: (APP / name).read_bytes() for name in EXPECTED_OLD}


def preflight(pack: dict[str, bytes], before: dict[str, bytes]) -> bytes:
    for name, expected in EXPECTED_OLD.items():
        if digest(before[name]) != expected:
            raise RuntimeError('LIVE_ACADEMY_BASELINE_CHANGED_ABORT:' + name)
    for name in NEW_NAMES:
        if (APP / name).exists() or (APP / name).is_symlink():
            raise RuntimeError('NEW_ACADEMY_TEMPLATE_COLLISION_ABORT:' + name)
    return patched_urls(before['config/urls.py'])


def atomic_replace(destination: Path, data: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.zm-academy-', delete=False) as f:
            temporary = f.name
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def atomic_add(destination: Path, data: bytes) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.zm-academy-', delete=False) as f:
            temporary = f.name
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temporary, 0o644)
        os.link(temporary, destination)  # Fails instead of overwriting a concurrent file.
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def restart_passenger() -> None:
    temp = APP / 'tmp'
    if temp.is_symlink() or (temp.exists() and not temp.is_dir()):
        raise RuntimeError('PASSENGER_RESTART_DIR_UNSAFE')
    temp.mkdir(mode=0o755, exist_ok=True)
    marker = temp / 'restart.txt'
    if marker.is_symlink():
        raise RuntimeError('PASSENGER_RESTART_MARKER_UNSAFE')
    marker.touch()


def django_check_and_templates() -> None:
    code = '''
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.core.checks import run_checks
from django.template.loader import get_template
from django.urls import resolve
errors = run_checks()
if errors: raise RuntimeError("DJANGO_SYSTEM_CHECK_FAILED")
for name in ("registration/login.html","core/academy.html",
             "core/education_course_detail.html","core/education_dashboard.html",
             "core/education_lesson.html","core/education_assessment.html",
             "core/education_assessment_result.html","core/education_certificate.html"):
    get_template(name)
if resolve("/accounts/login/").url_name != "login":
    raise RuntimeError("LOGIN_ROUTE_NOT_INSTALLED")
print("ACADEMY_DJANGO_CHECK_AND_TEMPLATES=PASS")
'''
    result = subprocess.run(
        [str(VENV_PYTHON), '-B', '-c', code], cwd=APP,
        env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
        capture_output=True, text=True, timeout=40, check=False,
    )
    if result.returncode or 'ACADEMY_DJANGO_CHECK_AND_TEMPLATES=PASS' not in result.stdout:
        raise RuntimeError('ACADEMY_DJANGO_CHECK_OR_TEMPLATE_FAILED')


def public_check() -> bool:
    urls = (
        ('https://zomorodmelal.ir/accounts/login/', b'id_username'),
        ('https://zomorodmelal.ir/', b'<html'),
        ('https://zomorodmelal.ir/amozeshgah/', b'<html'),
    )
    for url, marker in urls:
        with urlopen(Request(url + ('?zm_login_check=' + str(time.time_ns()) if '?' not in url else ''),
                             headers={'Cache-Control': 'no-cache',
                                      'User-Agent': 'ZM-Academy-Guarded-Release/1.0'}), timeout=18) as f:
            if f.status != 200 or marker not in f.read(500_000):
                return False
    return True


def backup_dir(run_id: str) -> Path:
    return BACKUP_ROOT / release_id(run_id)


def main(mode: str, run_id: str) -> None:
    pack = files()
    if mode == 'selftest':
        if digest(pack['config/settings.py']) == EXPECTED_OLD['config/settings.py']:
            raise RuntimeError('SETTINGS_PAYLOAD_UNCHANGED')
        if digest(pack['core/academy_views.py']) == EXPECTED_OLD['core/academy_views.py']:
            raise RuntimeError('VIEWS_PAYLOAD_UNCHANGED')
        print('ACADEMY_PACKAGE_VALID=yes')
        return
    guarded_host()
    backup = backup_dir(run_id)
    originals = old_data()
    if mode == 'preview':
        preflight(pack, originals)
        if backup.exists():
            raise RuntimeError('RELEASE_ID_ALREADY_USED')
        print('ACADEMY_GUARDED_PREFLIGHT=READY')
        return
    if mode == 'publish':
        urls = preflight(pack, originals)
        if backup.exists():
            raise RuntimeError('RELEASE_ID_ALREADY_USED')
        backup.mkdir(parents=True, mode=0o700, exist_ok=False)
        for name, data in originals.items():
            path = backup / name
            path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            with path.open('xb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            path.chmod(0o600)
        registration = APP / 'core/templates/registration'
        registration.mkdir(mode=0o755, exist_ok=True)
        for name in NEW_NAMES:
            atomic_add(APP / name, pack[name])
        for name in ('config/settings.py', 'core/academy_views.py'):
            atomic_replace(APP / name, pack[name])
        atomic_replace(APP / 'config/urls.py', urls)
        django_check_and_templates()
        restart_passenger()
        print('ACADEMY_GUARDED_PUBLISHED=yes')
        return
    if mode == 'verify':
        if not backup.is_dir():
            raise RuntimeError('ACADEMY_BACKUP_NOT_FOUND')
        urls = patched_urls((backup / 'config/urls.py').read_bytes())
        expected = {**pack, 'config/urls.py': urls}
        for name, data in expected.items():
            if digest((APP / name).read_bytes()) != digest(data):
                raise RuntimeError('ACADEMY_RELEASE_FILE_HASH_MISMATCH:' + name)
        django_check_and_templates()
        for attempt in range(6):
            try:
                if public_check():
                    print('ACADEMY_GUARDED_PUBLIC_VERIFIED=yes')
                    return
            except Exception:
                pass
            if attempt < 5:
                time.sleep(4)
        raise RuntimeError('ACADEMY_PUBLIC_LOGIN_NOT_READY')
    if mode == 'rollback':
        if not backup.is_dir():
            print('ACADEMY_NOTHING_TO_ROLLBACK=yes')
            return
        originals = {name: (backup / name).read_bytes() for name in EXPECTED_OLD}
        if any(digest(originals[name]) != sha for name, sha in EXPECTED_OLD.items()):
            raise RuntimeError('ACADEMY_BACKUP_HASH_INVALID')
        urls = patched_urls(originals['config/urls.py'])
        expected = {**pack, 'config/urls.py': urls}
        for name, data in expected.items():
            path = APP / name
            if path.is_symlink():
                raise RuntimeError('ACADEMY_ROLLBACK_TARGET_SYMLINK:' + name)
            if path.exists() and digest(path.read_bytes()) not in {
                    digest(data), EXPECTED_OLD.get(name, '')}:
                raise RuntimeError('ACADEMY_CONCURRENT_CHANGE_REFUSE_ROLLBACK:' + name)
        for name in EXPECTED_OLD:
            atomic_replace(APP / name, originals[name])
        for name in NEW_NAMES:
            path = APP / name
            if path.exists():
                path.unlink()
        restart_passenger()
        print('ACADEMY_GUARDED_ROLLED_BACK=yes')
        return
    raise RuntimeError('ACADEMY_UNKNOWN_RELEASE_MODE')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('USAGE: release.py selftest|preview|publish|verify|rollback RUN_ID')
    main(sys.argv[1], sys.argv[2])
