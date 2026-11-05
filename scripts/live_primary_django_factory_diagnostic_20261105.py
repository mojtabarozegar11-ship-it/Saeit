#!/usr/bin/env python3
"""Read-only request and startup probe for the real cPanel primary Django app."""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import sys
import traceback
from pathlib import Path


BASE = Path('/home/zomorod2')
PRIMARY = BASE / 'Saeit'
STAGING = BASE / 'Saeit-staging'
FACTORY = BASE / 'factory.zomorodmelal.ir'


def failure(exc: BaseException) -> dict[str, object]:
    msg = str(exc)
    signatures = {
        'UNKNOWN_COLUMN': r'unknown column|no such column|undefined column',
        'MISSING_TABLE': r'no such table|doesn.t exist|undefined table',
        'IMPORT': r'ModuleNotFoundError|ImportError|No module named',
        'TEMPLATE': r'TemplateDoesNotExist|TemplateSyntaxError',
        'HOST': r'DisallowedHost|Invalid HTTP_HOST|not in ALLOWED_HOSTS',
        'DATABASE_CONNECTION': r'can.t connect|connection refused|access denied',
        'MIGRATION': r'migration|relation does not exist',
    }
    frames = []
    for frame in traceback.extract_tb(exc.__traceback__)[-12:]:
        path = Path(frame.filename)
        try:
            rel = str(path.relative_to(BASE))
        except ValueError:
            rel = path.name
        if 'site-packages' in rel:
            rel = 'site-packages/' + path.name
        frames.append({'file': rel[:120], 'function': frame.name[:80], 'line': frame.lineno})
    return {'exception': type(exc).__name__,
            'error_signatures': [name for name, rx in signatures.items()
                                 if re.search(rx, msg, re.I)],
            'frames': frames[-6:]}


def file_indicators() -> dict[str, object]:
    roots = {'primary': PRIMARY, 'staging': STAGING, 'factory': FACTORY}
    results = {}
    for name, root in roots.items():
        files = {}
        for key in ('config/settings.py', 'config/urls.py', 'config/wsgi.py',
                    'core/newsletter_views.py', 'passenger_wsgi.py'):
            path = root / key
            if path.is_file() and not path.is_symlink():
                files[key] = {'exists': True,
                              'sha256prefix': hashlib.sha256(path.read_bytes()).hexdigest()[:16]}
            else:
                files[key] = {'exists': False}
        results[name] = files
    results['python_executables'] = {
        'Saeit-3.11': (BASE / 'virtualenv/Saeit/3.11/bin/python').is_file(),
        'Saeit-staging-3.11': (BASE / 'virtualenv/Saeit-staging/3.11/bin/python').is_file(),
        'alt-python3.10-lswsgi': Path('/opt/alt/python310/bin/lswsgi').is_file(),
    }
    return results


def probe_django() -> dict[str, object]:
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    os.chdir(PRIMARY)
    sys.path.insert(0, str(PRIMARY))
    result: dict[str, object] = {'status': 'START'}
    try:
        import django
        django.setup()
        from django.conf import settings
        from django.db import connection
        from django.test import Client
        from django.urls import Resolver404, resolve

        result['status'] = 'DJANGO_READY'
        result['django_version'] = django.get_version()
        result['debug_enabled'] = bool(settings.DEBUG)
        result['allowed_hosts'] = [host for host in settings.ALLOWED_HOSTS
                                   if isinstance(host, str) and len(host) < 140]
        result['db_vendor'] = connection.vendor
        try:
            tables = set(connection.introspection.table_names())
            result['newsletter_db_tables'] = {
                table: table in tables for table in
                ('core_newsletterstory', 'core_newslettersource',
                 'core_newsletterpublication', 'core_newsletterschedule')}
        except BaseException as exc:
            result['database_probe_error'] = failure(exc)
        for route in ('/', '/newsletter/', '/apps/', '/economy/'):
            try:
                match = resolve(route)
                result['resolved_' + route] = {
                    'view': match.view_name[:90] if match.view_name else '',
                    'url_name': match.url_name[:90] if match.url_name else ''}
            except Resolver404:
                result['resolved_' + route] = 'NOT_IN_DJANGO_URLCONF'
            except BaseException as exc:
                result['resolved_' + route] = failure(exc)
        for route in ('/newsletter/', '/apps/'):
            try:
                response = Client(raise_request_exception=True).get(
                    route, secure=True, HTTP_HOST='zomorodmelal.ir')
                result['request_' + route] = {
                    'status': response.status_code, 'bytes': len(response.content)}
            except BaseException as exc:
                result['request_' + route] = failure(exc)
    except BaseException as exc:
        result['status'] = 'DJANGO_SETUP_ERROR'
        result['setup_error'] = failure(exc)
    return result


def main() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise SystemExit('REFUSE_DIFFERENT_CPANEL_USER')
    if not PRIMARY.is_dir() or PRIMARY.is_symlink():
        raise SystemExit('PRIMARY_APP_MISSING_OR_SYMLINK')
    print('PRIMARY_APP_FILE_INDICATORS=' + json.dumps(file_indicators(), sort_keys=True))
    print('PRIMARY_DJANGO_RUNTIME=' + json.dumps(probe_django(), sort_keys=True))
    print('READ_ONLY_PRIMARY_DIAGNOSTIC_COMPLETE=1')


if __name__ == '__main__':
    main()
