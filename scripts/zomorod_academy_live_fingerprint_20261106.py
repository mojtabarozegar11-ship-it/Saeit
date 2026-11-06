#!/usr/bin/env python3
"""Read-only cPanel source fingerprint for the already-reviewed academy patch.

Run as the unprivileged zomorod2 cPanel account, via a pinned SSH relay.
Never print source, credentials, environment values, or user/database data.
"""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

HOME = Path('/home/zomorod2')
APP = HOME / 'Saeit'
WEB = HOME / 'public_html'
EXPECTED = {
    'config/settings.py': '02befe24a8a2636c498b51f4ad1fe7b237c636ec37f026a9e74209ee4eb9b6c5',
    'config/urls.py': 'c97c92579df9dd38676d65d2e1c8507750549e4f680197082834e64040e50823',
    'core/academy_views.py': '8e53348804828cb72a255efd517f206a12d8d1ded08a3f74a4a6c14174c5b3b0',
    'core/templates/core/education_course_detail.html': 'd3d9b83c9f6a4b389a109ca028fb8855488113da819ad33c49763c257a24f393',
    'core/templates/core/education_dashboard.html': 'c5050aa854e4db29582f64a59d267917106faa6fda2c933b0797e1029daf56cb',
    'core/templates/core/education_lesson.html': '6d407ecea2f692086b607c8f1f6ae39333bf474685bfaee6eac26c0c0ab390e7',
}
NEW_TEMPLATE = 'core/templates/registration/login.html'


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    if os.geteuid() == 0 or os.geteuid() != HOME.stat().st_uid:
        raise RuntimeError('CPANEL_USER_NOT_VERIFIED')
    if APP.is_symlink() or not APP.is_dir() or not (APP / 'manage.py').is_file():
        raise RuntimeError('DJANGO_APP_PATH_UNSAFE')
    if WEB.is_symlink() or not WEB.is_dir():
        raise RuntimeError('PUBLIC_SITE_PATH_UNSAFE')
    root_config = WEB / '.htaccess'
    if not root_config.is_file() or root_config.is_symlink():
        raise RuntimeError('ROOT_PASSENGER_CONFIG_NOT_VERIFIED')
    lines = root_config.read_text(errors='replace').splitlines()
    app_root = any('PassengerAppRoot' in line and '/home/zomorod2/Saeit' in line for line in lines)
    root_uri = any('PassengerBaseURI' in line and '"/"' in line for line in lines)
    print('PASSENGER_APP_ROOT_MATCH=' + str(app_root).lower())
    print('PASSENGER_ROOT_URI_MATCH=' + str(root_uri).lower())
    matches = 0
    for name, expected in EXPECTED.items():
        path = APP / name
        if path.is_symlink() or not path.is_file():
            result = 'MISSING_OR_SYMLINK'
        else:
            result = 'MATCH' if hash_file(path) == expected else 'DIFFERENT'
        matches += result == 'MATCH'
        print('ACADEMY_BASELINE_FILE=' + name + ' status=' + result)
    new_template = APP / NEW_TEMPLATE
    print('ACADEMY_NEW_LOGIN_TEMPLATE=' + (
        'ABSENT' if not new_template.exists() else
        'PRESENT' if new_template.is_file() and not new_template.is_symlink() else
        'UNSAFE'
    ))
    print('ACADEMY_BASELINE_MATCHED=' + str(matches) + '/' + str(len(EXPECTED)))
    # Release diagnostic: hashes alone identify unexpected concurrent writes.
    # No Python source, credentials, customer rows or environment are printed.
    for name in ('core/academy_views.py', 'core/templates/core/academy.html'):
        path = APP / name
        if path.is_file() and not path.is_symlink():
            print('LIVE_ACADEMY_FILE_SHA256=' + name + ' sha=' + hash_file(path))
        else:
            print('LIVE_ACADEMY_FILE_SHA256=' + name + ' status=ABSENT_OR_UNSAFE')
    print('APP_VENV_PYTHON_PRESENT=' + str((HOME / 'virtualenv/Saeit/3.10/bin/python').is_file()).lower())
    # Public route and layout inventory only; never output Python source text.
    urls = (APP / 'config/urls.py').read_text(errors='replace')
    route_names = ('accounts/login/', 'accounts/logout/', 'amozeshgah/',
                   'education/', 'education_enroll', 'education_lesson')
    for route in route_names:
        print('LIVE_URL_TEXT_HAS=' + route + ' status=' + str(route in urls).lower())
    print('LIVE_URL_LINE_COUNT=' + str(len(urls.splitlines())))
    print('LIVE_URL_PATTERN_LIST_PRESENT=' + str(bool(re.search(r'urlpatterns\s*=', urls))).lower())
    print('LIVE_URL_SHA256=' + hash_file(APP / 'config/urls.py'))
    for label, path in (
        ('APP_TEMPLATES', APP / 'templates'),
        ('CORE_TEMPLATES', APP / 'core/templates'),
        ('CORE_TEMPLATES_CORE', APP / 'core/templates/core'),
        ('CORE_TEMPLATES_REGISTRATION', APP / 'core/templates/registration'),
        ('PUBLIC_ACADEMY', WEB / 'amozeshgah'),
        ('STAGING_ROOT', HOME / 'Saeit-staging-web'),
    ):
        kind = 'SYMLINK' if path.is_symlink() else 'DIR' if path.is_dir() else 'FILE' if path.is_file() else 'ABSENT'
        print('ACADEMY_LAYOUT=' + label + ' status=' + kind)
        if kind == 'DIR' and label in ('APP_TEMPLATES','CORE_TEMPLATES_CORE','CORE_TEMPLATES_REGISTRATION'):
            print('ACADEMY_LAYOUT_HTML_COUNT=' + label + ' count=' + str(sum(
                item.is_file() and item.suffix == '.html' for item in path.iterdir()
            )))
            print('ACADEMY_LAYOUT_HTML_NAMES=' + label + ' names=' + ','.join(sorted(
                item.name for item in path.iterdir() if item.is_file() and
                not item.is_symlink() and item.suffix == '.html'
            )[:30]))
    print('LIVE_PASSENGER_WSGI_PRESENT=' + str((APP / 'passenger_wsgi.py').is_file()).lower())
    # Read only table names through the existing Django database connection.
    # No ORM queries, user records, writes, migrations or model data are read.
    interpreter = HOME / 'virtualenv/Saeit/3.10/bin/python'
    if interpreter.is_file():
        probe = '''
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
from django.db import connection
from django.template.loader import get_template
from django.urls import resolve
from pathlib import Path
origin = Path(get_template("core/academy.html").origin.name).resolve()
root = Path("/home/zomorod2/Saeit")
print("ACADEMY_DJANGO_TEMPLATE_ORIGIN=" + (
    str(origin.relative_to(root)) if origin.is_relative_to(root) else "OUTSIDE_APP_ROOT"))
print("ACADEMY_DJANGO_RESOLVER_MODULE=" + resolve("/academy/").func.__module__)
with connection.cursor():
    tables = set(connection.introspection.table_names())
for suffix in ("track", "course", "lesson", "enrollment", "progress",
               "bookmark", "assessment", "certificate"):
    name = "core_education" + suffix
    print("ACADEMY_DB_TABLE=" + name + " exists=" + str(name in tables).lower())
'''
        try:
            result = subprocess.run(
                [str(interpreter), '-B', '-c', probe], cwd=APP,
                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                capture_output=True, text=True, timeout=35, check=False,
            )
            if result.returncode:
                print('ACADEMY_DB_SCHEMA_INSPECTION=UNAVAILABLE')
            else:
                print('ACADEMY_DB_SCHEMA_INSPECTION=SUCCESS')
                for line in result.stdout.splitlines():
                    if line.startswith(('ACADEMY_DB_TABLE=', 'ACADEMY_DJANGO_TEMPLATE_ORIGIN=',
                                        'ACADEMY_DJANGO_RESOLVER_MODULE=')):
                        print(line)
        except Exception:
            print('ACADEMY_DB_SCHEMA_INSPECTION=UNAVAILABLE')
    # Do not mutate the app, restart Passenger, inspect credentials, or touch DB.


if __name__ == '__main__':
    main()
