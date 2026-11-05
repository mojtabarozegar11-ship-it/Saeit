#!/usr/bin/env python3
"""Find the active cPanel routing source without printing secrets or writing files.

This inventory intentionally reads only preselected route/template/.htaccess
files in the authenticated account, not credentials, databases, or user data.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path


def inspect_file(path: Path, home: Path) -> dict[str, object]:
    result: dict[str, object] = {'path': str(path.relative_to(home))}
    if path.is_symlink():
        result['state'] = 'symlink_skipped'
        return result
    if not path.is_file():
        result['state'] = 'missing'
        return result
    if path.stat().st_size > 512_000:
        result['state'] = 'oversized_skipped'
        return result
    data = path.read_bytes()
    content = data.decode('utf-8', 'replace')
    result.update({'state': 'file', 'sha256': hashlib.sha256(data).hexdigest(),
                   'size': len(data)})
    if path.name == '.htaccess':
        roots = re.findall(r'(?im)^\s*PassengerAppRoot\s+([^\s#]+)', content)
        result['passenger_roots_under_account'] = [
            root for root in roots if root.startswith(str(home) + '/')
        ][:3]
        result['gold_rule_present'] = bool(re.search(r'(?i)gold', content))
    elif path.name == 'urls.py':
        result.update({
            'gold_django_route': bool(re.search(r'path\s*\(\s*[\'"]gold/', content)),
            'sector_routes': [segment for segment in ('carpets', 'personnel',
                              'real-estate', 'restaurant', 'signals')
                              if re.search(r'(?i)\b' + re.escape(segment) + r'/', content)],
        })
    else:
        result['broken_nav_hrefs'] = [segment for segment in ('carpets',
            'gold', 'personnel', 'real-estate', 'restaurant', 'signals')
            if re.search(r'(?i)href\s*=\s*[\'"]/+' + re.escape(segment) + '/', content)]
    return result


def audit() -> dict[str, object]:
    home = Path('/home/zomorod2')
    if os.getuid() != home.stat().st_uid:
        raise SystemExit('WRONG_CPANEL_ACCOUNT')
    allowed_roots = [home, home / 'public_html', home / 'zomorodmelal.ir']
    for child in sorted(home.iterdir()):
        if (child.is_dir() and not child.is_symlink()
                and re.search(r'(?i)^saeit(?:-|_|$)', child.name)):
            allowed_roots.append(child)
    allowed_roots = list(dict.fromkeys(allowed_roots))[:18]
    suffixes = ('.htaccess', 'core/templates/base.html',
                'templates/base.html', 'config/urls.py',
                'newsletter/.htaccess', 'newsletter/index.html')
    records = [inspect_file(root / suffix, home) for root in allowed_roots
               for suffix in suffixes]
    # Include exact files even when absent: absence is useful source evidence.
    return {'account_verified': True, 'roots_inspected': len(allowed_roots),
            'existing_files': [item for item in records if item['state'] != 'missing'],
            'main_site_writes': 0, 'staging_writes': 0, 'secrets_printed': 0}


if __name__ == '__main__':
    if sys.argv[1:] != ['readonly']:
        raise SystemExit('USAGE: readonly')
    print('ROUTE_SOURCE_INVENTORY=' + json.dumps(audit(), ensure_ascii=False,
          sort_keys=True), flush=True)
