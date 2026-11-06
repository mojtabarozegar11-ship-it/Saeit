#!/usr/bin/env python3
"""Public-domain, read-only cPanel inventory; do not print secrets or file contents."""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import shutil
import subprocess
from pathlib import Path


HOME = Path('/home/zomorod2')
ALLOWED_SUFFIXES = ('.zomorodmelal.ir', '.mojplaywin.com')
MAIN_DOMAINS = ('zomorodmelal.ir', 'mojplaywin.com')
HOST_RE = re.compile(r'(?i)^(?:[a-z0-9-]+\.)+[a-z]{2,63}$')


def public_host(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    host = value.strip().lower().rstrip('.')
    if HOST_RE.fullmatch(host) and (host in MAIN_DOMAINS or host.endswith(ALLOWED_SUFFIXES)):
        return host
    return None


def cpanel_domains() -> dict[str, object]:
    candidate = shutil.which('uapi')
    if not candidate and Path('/usr/local/cpanel/bin/uapi').is_file():
        candidate = '/usr/local/cpanel/bin/uapi'
    if not candidate:
        return {'status': 'UAPI_NOT_FOUND', 'domains': list(MAIN_DOMAINS)}
    try:
        proc = subprocess.run([candidate, '--output=json', 'DomainInfo', 'list_domains'],
                              capture_output=True, text=True, timeout=25, check=False)
        if proc.returncode != 0:
            return {'status': 'UAPI_NONZERO', 'domains': list(MAIN_DOMAINS)}
        doc = json.loads(proc.stdout)
        result = doc.get('result', {})
        data = result.get('data') or {}
        if not isinstance(data, dict):
            return {'status': 'UAPI_UNEXPECTED_SCHEMA', 'domains': list(MAIN_DOMAINS)}
        domains: set[str] = set(MAIN_DOMAINS)
        for key in ('main_domain', 'all_domains', 'addon_domains', 'sub_domains',
                    'parked_domains', 'alias_domains'):
            values = data.get(key, [])
            if isinstance(values, str):
                values = [values]
            if isinstance(values, list):
                for value in values:
                    host = public_host(value)
                    if host:
                        domains.add(host)
        return {'status': 'UAPI_OK', 'domains': sorted(domains),
                'registered_count': len(domains)}
    except (ValueError, OSError, subprocess.TimeoutExpired) as exc:
        return {'status': 'UAPI_FAILED_' + type(exc).__name__, 'domains': list(MAIN_DOMAINS)}


def file_metadata(path: Path) -> dict[str, object]:
    if path.is_symlink():
        return {'status': 'SYMLINK_NOT_FOLLOWED'}
    if not path.is_file():
        return {'status': 'ABSENT'}
    st = path.stat()
    if st.st_size > 1_000_000:
        return {'status': 'PRESENT_TOO_LARGE', 'bytes': st.st_size}
    return {'status': 'PRESENT', 'bytes': st.st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def root_info(label: str, root: Path) -> dict[str, object]:
    data: dict[str, object] = {'label': label}
    if root.is_symlink():
        data['status'] = 'SYMLINK_NOT_FOLLOWED'
        return data
    if not root.is_dir():
        data['status'] = 'NOT_PRESENT'
        return data
    data['status'] = 'EXISTS'
    data['files'] = {name: file_metadata(root / name) for name in
                     ('index.php', 'index.html', 'passenger_wsgi.py', '.htaccess',
                      'robots.txt', 'sitemap.xml')}
    return data


def main() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise SystemExit('CPANEL_USER_MISMATCH')
    if not HOME.is_dir() or HOME.is_symlink():
        raise SystemExit('CPANEL_HOME_MISMATCH')
    report = {
        'source': 'authenticated_cpanel_readonly',
        'domains': cpanel_domains(),
        'roots': [root_info('zomorod_webroot', HOME / 'public_html'),
                  root_info('mojplaywin_webroot', HOME / 'mojplaywin.com'),
                  root_info('django_app_root', HOME / 'Saeit-staging')],
        'verified_private_management_entry':
            file_metadata(HOME / '.private/zomorod-business/app.php'),
        'guarantee': 'No site files, databases, orders, accounts or settings changed',
    }
    print('LIVE_MULTISITE_CPANEL_INVENTORY=' + json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
