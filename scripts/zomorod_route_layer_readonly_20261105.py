#!/usr/bin/env python3
"""Read-only evidence of why both Passenger and DocumentRoot routes stay 404."""

import ast
import hashlib
import json
import os
import re
import socket
import subprocess
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ACCOUNT = Path('/home/zomorod2')
APP = ACCOUNT / 'Saeit'
ROOT = ACCOUNT / 'public_html'
HT = ROOT / '.htaccess'


def http_summary(route):
    req = Request('https://zomorodmelal.ir' + route + '?zm_readonly_route_probe=20261105',
                  headers={'User-Agent': 'ZM-ReadOnly-Route-Trace/1.0', 'Cache-Control': 'no-cache'})
    try:
        resp = urlopen(req, timeout=10)
    except HTTPError as exc:
        resp = exc
    with resp:
        body = resp.read(350)
        return {'route': route, 'status': resp.status, 'final_path': resp.url.split('?')[0],
                'headers': {key: resp.headers.get(key) for key in
                            ('Server', 'Via', 'Age', 'CF-Cache-Status', 'X-Cache', 'Cache-Control',
                             'Content-Type', 'X-Powered-By') if resp.headers.get(key)},
                'body_prefix': body.decode('utf-8', errors='replace')[:150]}


def paths():
    return {str(p.relative_to(ACCOUNT)): {'exists': p.exists(), 'symlink': p.is_symlink(),
                                         'is_file': p.is_file()}
            for p in (ROOT, HT, APP / 'passenger_wsgi.py', APP / 'config/urls.py',
                      APP / 'config/settings.py', APP / 'tmp/restart.txt',
                      ROOT / 'robots.txt', ROOT / 'index.html', ROOT / 'carpets')}


def htaccess_shape():
    lines = HT.read_text(errors='replace').splitlines()
    pattern = re.compile(r'^\s*(Passenger\w+|RewriteEngine|RewriteRule|RewriteCond|DirectoryIndex|FallbackResource|ProxyPass|SetHandler)\b', re.I)
    found = []
    for line in lines:
        if pattern.match(line):
            pieces = line.strip().split()
            directive = pieces[0] if pieces else ''
            # Sanitized routing metadata; exclude rewrite queries and headers.
            arg = pieces[1] if len(pieces) > 1 and directive.lower() == 'rewriterule' else None
            item = {'directive': directive, 'match': arg}
            if directive.lower() == 'rewriterule' and len(pieces) > 2:
                item['target_no_query'] = pieces[2].split('?', 1)[0][:100]
                item['flags'] = pieces[3][:85] if len(pieces) > 3 else None
            if directive.lower() == 'rewritecond' and len(pieces) > 2:
                item['input_kind'] = pieces[1] if pieces[1] in {'%{REQUEST_FILENAME}', '%{REQUEST_URI}', '%{HTTP_HOST}'} else 'other'
                item['condition_class'] = pieces[2] if pieces[2] in {'!-f', '!-d', '-f', '-d'} else 'other'
            if directive.lower() in {'passengerbaseuri', 'passengerstartupfile', 'directoryindex'} and len(pieces) > 1:
                item['value'] = pieces[1][:90]
            found.append(item)
    return found[:55]


def setting_summary():
    src = (APP / 'config/settings.py').read_text(errors='replace')
    tree = ast.parse(src)
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in {'ROOT_URLCONF', 'FORCE_SCRIPT_NAME'} for t in node.targets):
            out['setting'] = ast.get_source_segment(src, node)[:150]
    return out


def origin_probe():
    # Compare the public URL with the same TLS hostname resolved directly to
    # the previously authenticated cPanel server, without writing anything.
    cmd = ['curl', '--silent', '--show-error', '--max-time', '12', '--resolve',
           'zomorodmelal.ir:443:178.239.147.125', '--output', '/dev/null',
           '--write-out', '%{http_code};%{remote_ip};%{ssl_verify_result}',
           'https://zomorodmelal.ir/carpets/?zm_origin_probe=20261105']
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=16, check=False)
        return {'http_code_and_ip': result.stdout[:100], 'curl_rc': result.returncode,
                'error_kind': (result.stderr[:120] if result.returncode else '')}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'error_kind': type(exc).__name__}


def run():
    if os.getuid() != ACCOUNT.stat().st_uid or not HT.is_file():
        raise SystemExit('ACCOUNT_OR_HOST_ROOT_MISMATCH')
    print('ZM_ROUTE_LAYER_TRACE=' + json.dumps({
        'identity': 'authenticated-cpanel-owner',
        'dns_A': socket.gethostbyname('zomorodmelal.ir'),
        'paths': paths(),
        'htaccess_directives': htaccess_shape(),
        'htaccess_sha256': hashlib.sha256(HT.read_bytes()).hexdigest(),
        'settings': setting_summary(),
        'urls_source_includes_carpet': 'path("carpets/"' in (APP / 'config/urls.py').read_text(),
        'public_checks': [http_summary(p) for p in ('/', '/newsletter/', '/carpets/', '/signals/')],
        'authenticated_origin_probe': origin_probe(),
    }, ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == '__main__':
    run()
