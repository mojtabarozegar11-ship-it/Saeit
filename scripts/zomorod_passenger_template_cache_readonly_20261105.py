#!/usr/bin/env python3
"""Read-only, secret-safe evidence about live Zomorod template caching.

Runs as the cPanel account through the existing pinned SSH relay. Does not
write, restart a service, read .env, inspect credentials, or touch the DB.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import secrets
import stat
import sys
from pathlib import Path
from urllib.request import Request, urlopen

HOME = Path('/home/zomorod2')
APP = HOME / 'Saeit'
TEMPLATE = APP / 'templates/base.html'


def digest(p: Path) -> str | None:
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def stat_summary(p: Path) -> dict[str, object]:
    if not p.exists():
        return {'exists': False}
    s = p.stat()
    return {'exists': True, 'is_file': stat.S_ISREG(s.st_mode),
            'is_directory': stat.S_ISDIR(s.st_mode),
            'is_symlink': p.is_symlink(), 'owned_by_account': s.st_uid == os.getuid(),
            'writable_by_account': os.access(p, os.W_OK), 'mtime_epoch': int(s.st_mtime)}


def htaccess_summary(p: Path) -> dict[str, object]:
    if not p.is_file():
        return {'exists': False}
    # Whitelist only known Passenger directives; never print arbitrary config.
    source = p.read_text(errors='replace')
    directives = {}
    for name in ('PassengerAppRoot', 'PassengerBaseURI', 'PassengerEnabled',
                 'PassengerPython', 'PassengerRestartDir', 'PassengerAppEnv'):
        vals = re.findall(r'^\s*' + name + r'\s+([^\r\n#]+)', source, re.I | re.M)
        directives[name] = {'present': bool(vals), 'count': len(vals)}
        if name == 'PassengerAppRoot' and vals:
            directives[name]['matches_main_app'] = vals[-1].strip(' \t\"\'') == str(APP)
        if name == 'PassengerRestartDir' and vals:
            directives[name]['uses_default_tmp'] = vals[-1].strip(' \t\"\'') == 'tmp'
    return {'exists': True, 'sha256': digest(p), 'directives': directives}


def template_config() -> dict[str, object]:
    f = APP / 'config/settings.py'
    if not f.is_file():
        return {'exists': False}
    src = f.read_text(errors='replace')
    tree = ast.parse(src, filename='settings.py')
    nodes = [n for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))
             and ((isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'TEMPLATES' for t in n.targets))
                  or (isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == 'TEMPLATES'))]
    if len(nodes) != 1:
        return {'exists': True, 'template_blocks_found': len(nodes)}
    segment = ast.get_source_segment(src, nodes[0]) or ''
    return {'exists': True, 'sha256': digest(f),
            'explicit_template_loader': bool(re.search(r'[\'\"]loaders[\'\"]\s*:', segment)),
            'declares_app_dirs': 'APP_DIRS' in segment,
            'declares_project_templates': 'BASE_DIR / "templates"' in segment or "BASE_DIR / 'templates'" in segment,
            'contains_cached_loader': 'cached.Loader' in segment}


def public_probe() -> dict[str, object]:
    url = ('https://zomorodmelal.ir/newsletter/?zm_passenger_cache_audit='
           + secrets.token_hex(12))
    req = Request(url, headers={'User-Agent': 'ZM-ReadOnly-Passenger-Audit/1.0',
                                'Cache-Control': 'no-cache', 'Pragma': 'no-cache'})
    with urlopen(req, timeout=20) as response:
        html = response.read(220_000)
        return {'http_status': response.status,
                'has_personnel_href': b'href="/personnel/"' in html,
                'has_staff_href': b'href="/staff/"' in html,
                'has_gold_href': b'href="/gold/"' in html,
                'tala_link_occurrences': html.count(b'href="/tala/"'),
                'cache_control_present': 'Cache-Control' in response.headers,
                'age_header_present': 'Age' in response.headers,
                'x_cache_header_present': 'X-Cache' in response.headers}


def run() -> dict[str, object]:
    if os.getuid() != HOME.stat().st_uid:
        raise RuntimeError('NOT_EXPECTED_CPANEL_ACCOUNT')
    out = {
        'account_checked': os.getuid() == HOME.stat().st_uid,
        'app': stat_summary(APP),
        'template': {**stat_summary(TEMPLATE), 'sha256': digest(TEMPLATE)},
        'passenger_wsgi': stat_summary(APP / 'passenger_wsgi.py'),
        'app_tmp': stat_summary(APP / 'tmp'),
        'app_restart_marker': stat_summary(APP / 'tmp/restart.txt'),
        'main_htaccess': htaccess_summary(HOME / 'public_html/.htaccess'),
        'app_htaccess': htaccess_summary(APP / '.htaccess'),
        'staging_htaccess': htaccess_summary(HOME / 'Saeit-staging-web/.htaccess'),
        'template_settings': template_config(),
        'public': public_probe(),
        'writes_or_restarts_performed': 0,
    }
    return out


if __name__ == '__main__':
    if sys.argv[1:] != ['readonly']:
        raise SystemExit('USAGE: readonly')
    print('PASSENGER_CACHE_READONLY_RESULT=' + json.dumps(run(), sort_keys=True), flush=True)
