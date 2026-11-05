#!/usr/bin/env python3
"""Strictly read-only diagnostics for live newsletter, routed sections and subdomains."""

from __future__ import annotations

import json
import os
import pwd
import re
import shutil
import subprocess
import sys
from pathlib import Path


HOME = Path('/home/zomorod2')
APP = HOME / 'Saeit-staging'
DOMAINS = ('zomorodmelal.ir', 'mojplaywin.com',
           'factory.zomorodmelal.ir', 'staging.zomorodmelal.ir')


def safe_problem(exc: BaseException) -> dict[str, str]:
    detail = str(exc)
    if re.search(r'no such table|does not exist|undefined table', detail, re.I):
        kind = 'MISSING_DATABASE_TABLE'
    elif re.search(r'no such column|unknown column|undefined column', detail, re.I):
        kind = 'MISSING_DATABASE_COLUMN'
    elif re.search(r'permission denied|access denied', detail, re.I):
        kind = 'PERMISSION_DENIED'
    elif re.search(r'connection refused|connect timeout|cannot connect', detail, re.I):
        kind = 'DATABASE_OR_SERVICE_CONNECTION'
    elif re.search(r'template.*does not exist', detail, re.I):
        kind = 'MISSING_TEMPLATE'
    else:
        kind = 'OTHER'
    return {'exception': type(exc).__name__, 'category': kind}


def domain_roots() -> list[dict[str, object]]:
    exe = shutil.which('uapi') or '/usr/local/cpanel/bin/uapi'
    if not Path(exe).is_file():
        return [{'status': 'UAPI_MISSING'}]
    results = []
    for domain in DOMAINS:
        try:
            proc = subprocess.run([exe, '--output=json', 'DomainInfo', 'domains_data',
                                   'domain=' + domain], capture_output=True,
                                  text=True, timeout=15, check=False)
            if proc.returncode != 0:
                results.append({'domain': domain, 'status': 'NONZERO'})
                continue
            doc = json.loads(proc.stdout)
            data = (doc.get('result') or {}).get('data') or {}
            nested_roots: list[str] = []

            def collect_roots(node: object) -> None:
                if isinstance(node, dict):
                    for key, value in node.items():
                        if key.lower().replace('_', '') in ('documentroot', 'homedir') and isinstance(value, str):
                            if value.startswith(str(HOME)):
                                nested_roots.append(value)
                        elif isinstance(value, (dict, list)):
                            collect_roots(value)
                elif isinstance(node, list):
                    for child in node[:200]:
                        collect_roots(child)

            collect_roots(data)
            if isinstance(data, list):
                data = data[0] if data else {}
            # cPanel installations disagree about the response envelope.
            if isinstance(data, dict) and domain in data and isinstance(data[domain], dict):
                data = data[domain]
            root = data.get('documentroot') or data.get('document_root') or (nested_roots[0] if nested_roots else '')
            if isinstance(root, str) and root.startswith(str(HOME)):
                path = Path(root)
                results.append({'domain': domain, 'status': 'OK',
                                'webroot': root, 'root_exists': path.is_dir(),
                                'symlink': path.is_symlink(),
                                'htaccess_present': (path / '.htaccess').is_file(),
                                'passenger_wsgi_present': (path / 'passenger_wsgi.py').is_file()})
            else:
                results.append({'domain': domain, 'status': 'ROOT_NOT_IN_USER_HOME_OR_UNKNOWN'})
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            results.append({'domain': domain, 'status': type(exc).__name__})
    return results


def newsletter_readonly_probe() -> dict[str, object]:
    if not APP.is_dir() or not (APP / 'config/settings.py').is_file():
        return {'status': 'DJANGO_APP_NOT_AVAILABLE'}
    venv = HOME / 'virtualenv/Saeit-staging/3.11/bin/python'
    result: dict[str, object] = {'python_venv_exists': venv.is_file()}
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        import django
        django.setup()
        from django.db import connection
        from django.test import Client, RequestFactory
        from core.newsletter_views import newsletter_home
        from core.models import NewsletterStory, NewsletterSource, NewsletterPublication, NewsletterSchedule

        result['django_ready'] = True
        result['db_engine'] = connection.vendor
        tables = set(connection.introspection.table_names())
        models = [NewsletterStory, NewsletterSource, NewsletterPublication, NewsletterSchedule]
        results = []
        for model in models:
            table = model._meta.db_table
            item: dict[str, object] = {'table': table, 'table_exists': table in tables}
            if table in tables:
                cols = {col.name for col in connection.introspection.get_table_description(
                    connection.cursor(), table)}
                item['missing_model_columns'] = sorted(field.column for field in model._meta.concrete_fields
                                                        if field.column not in cols)
            results.append(item)
        result['model_schema_checks'] = results
        try:
            request = RequestFactory().get('/newsletter/', secure=True,
                                           HTTP_HOST='zomorodmelal.ir')
            response = newsletter_home(request)
            result['view_result'] = {'status': getattr(response, 'status_code', None),
                                     'rendered_bytes': len(response.content)}
        except BaseException as exc:
            result['view_result'] = {'status': 'ERROR', **safe_problem(exc)}
        result['full_request_results'] = []
        for hostname in ('zomorodmelal.ir', 'mojplaywin.com'):
            try:
                response = Client(raise_request_exception=True).get(
                    '/newsletter/', secure=True, HTTP_HOST=hostname)
                result['full_request_results'].append(
                    {'host': hostname, 'status': response.status_code,
                     'bytes': len(response.content)})
            except BaseException as exc:
                result['full_request_results'].append(
                    {'host': hostname, 'status': 'ERROR', **safe_problem(exc)})
    except BaseException as exc:
        result['django_ready'] = False
        result['problem'] = safe_problem(exc)
    return result


def known_route_inventory() -> dict[str, object]:
    roots = [HOME / 'public_html', APP]
    routes = ('apps', 'newsletter', 'economic-reports', 'auction', 'ai',
              'auctions', 'economy', 'agents')
    state = {}
    for root in roots:
        key = 'public_html' if root.name == 'public_html' else 'django_app'
        state[key] = {route: {'directory': (root / route).is_dir(),
                              'index_html': (root / route / 'index.html').is_file(),
                              'index_php': (root / route / 'index.php').is_file()}
                      for route in routes}
    return state


def public_routing_indicators() -> dict[str, object]:
    ht = HOME / 'public_html/.htaccess'
    if ht.is_symlink() or not ht.is_file():
        return {'status': 'UNAVAILABLE'}
    text = ht.read_text('utf-8', 'replace')
    routing = []
    for line in text.splitlines():
        stripped = line.strip()
        if not re.match(r'^(?:RewriteRule|RewriteCond|Passenger|AddHandler|SetHandler|ErrorDocument)\b',
                        stripped, re.I):
            continue
        if re.search(r'(?:token|secret|password|credential|cookie|authorization|api[_-]?key)',
                     stripped, re.I):
            continue
        routing.append(stripped[:260])
    candidates = {}
    for short in ('factory.zomorodmelal.ir', 'staging.zomorodmelal.ir',
                  'public_html/factory', 'public_html/staging'):
        path = HOME / short
        candidates[short] = {'directory': path.is_dir(),
                             'passenger_wsgi': (path / 'passenger_wsgi.py').is_file(),
                             'htaccess': (path / '.htaccess').is_file()}
    return {'status': 'READ', 'routing_lines_without_sensitive_patterns': routing[:70],
            'subdomain_root_candidates': candidates}


def main() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise SystemExit('CPANEL_USER_MISMATCH')
    print('LIVE_SUBSITE_DOMAIN_ROOTS=' + json.dumps(domain_roots(), ensure_ascii=False))
    print('LIVE_SECTION_PATHS=' + json.dumps(known_route_inventory(), ensure_ascii=False))
    print('LIVE_ROOT_ROUTING=' + json.dumps(public_routing_indicators(), ensure_ascii=False))
    print('LIVE_NEWSLETTER_DIAGNOSTIC=' + json.dumps(newsletter_readonly_probe(),
                                                      ensure_ascii=False, sort_keys=True))
    print('READ_ONLY_DIAGNOSTIC_COMPLETE=1')


if __name__ == '__main__':
    main()
