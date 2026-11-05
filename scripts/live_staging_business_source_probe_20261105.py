#!/usr/bin/env python3
"""Read-only discovery of staging duplicate-card source and private login robots."""

from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen


HOME = Path('/home/zomorod2')


class Cards(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str]] = []
        self.a: dict[str, str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == 'a':
            data = dict(attrs)
            self.a = {'href': data.get('href') or '', 'class': data.get('class') or '', 'label': ''}

    def handle_data(self, text: str) -> None:
        if self.a is not None:
            self.a['label'] += text

    def handle_endtag(self, tag: str) -> None:
        if tag == 'a' and self.a is not None:
            self.a['label'] = re.sub(r'\s+', ' ', self.a['label']).strip()[:95]
            if self.a['label']:
                self.links.append(self.a)
            self.a = None


def probe_public(url: str) -> dict[str, object]:
    try:
        with urlopen(Request(url, headers={'User-Agent': 'ZM-Multisite-ReadOnly/1.0'}), timeout=25) as response:
            data = response.read(180000)
            html = data.decode('utf-8', 'replace')
            cards = Cards()
            cards.feed(html)
            grouped: dict[str, list[dict[str, str]]] = {}
            for link in cards.links:
                grouped.setdefault(link['label'], []).append(link)
            duplicates = {label: destinations for label, destinations in grouped.items()
                          if len(destinations) > 1 and len(label) > 3}
            return {'http': response.status, 'x_robots_tag': response.headers.get('X-Robots-Tag'),
                    'cache_control': response.headers.get('Cache-Control'),
                    'age': response.headers.get('Age'),
                    'litespeed_cache': response.headers.get('X-LiteSpeed-Cache'),
                    'etag': response.headers.get('ETag'),
                    'title': re.findall(r'<title[^>]*>(.*?)</title>', html, re.I | re.S)[:1],
                    'total_links': len(cards.links), 'duplicate_link_labels': duplicates,
                    'h2_headings': [re.sub('<[^>]+>', '', x).strip()[:85] for x in
                                    re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.I | re.S)][:24],
                    'html_sha': hashlib.sha256(data).hexdigest()}
    except Exception as exc:
        return {'status': 'UNAVAILABLE', 'reason_type': type(exc).__name__}


def file_info(path: Path) -> dict[str, object]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 500000:
        return {'present_regular_bounded': False}
    content = path.read_bytes()
    text = content.decode('utf-8', 'replace')
    return {'present_regular_bounded': True, 'bytes': len(content),
            'sha256': hashlib.sha256(content).hexdigest(),
            'has_x_robots_tag': bool(re.search(r'X-Robots-Tag', text, re.I)),
            'has_robots_meta': bool(re.search(r'<meta[^>]*name=[\"\']robots[\"\']', text, re.I)),
            'is_php': text.lstrip().startswith('<?php'),
            'contains_staging_title': 'خدمات و اکوسیستم یکپارچه' in text,
            'contains_management_title': 'میز مدیریت و حسابداری' in text}


def source_inventory() -> dict[str, object]:
    selected = {
        'staging_web_htaccess': HOME / 'Saeit-staging-web/.htaccess',
        'staging_wsgi': HOME / 'Saeit-staging/admin-smoke/passenger_wsgi.py',
        'staging_core_services': HOME / 'Saeit-staging/core/templates/core/services.html',
        'staging_core_home': HOME / 'Saeit-staging/core/templates/core/home.html',
        'staging_root_index': HOME / 'Saeit-staging-web/index.html',
        'business_public_index': HOME / 'public_html/business/index.php',
        'business_public_app': HOME / 'public_html/business/app.php',
        'business_public_htaccess': HOME / 'public_html/business/.htaccess',
        'business_private_app': HOME / '.private/zomorod-business/app.php',
        'business_staging_app': HOME / 'Saeit-staging/content/zomorod-business/app.php',
        'business_primary_app': HOME / 'Saeit/content/zomorod-business/app.php',
    }
    return {name: file_info(path) for name, path in selected.items()}


def staging_public_card_source() -> dict[str, object]:
    path = HOME / 'Saeit-staging/core/templates/core/services.html'
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 12000:
        return {'status': 'SOURCE_UNAVAILABLE'}
    code = path.read_text('utf-8', 'replace')
    if re.search(r'(?i)(?:api[_-]?key|password|client[_-]?secret|private[_-]?key)', code):
        return {'status': 'SAFE_OUTPUT_GUARD'}
    articles = re.findall(r'<article\b[^>]*>[\s\S]*?</article>', code, re.I)
    cards = []
    for item in articles[:30]:
        title = re.search(r'<h2[^>]*>(.*?)</h2>', item, re.I | re.S)
        if title:
            cards.append({'title': re.sub('<[^>]+>', '', title.group(1)).strip(),
                          'source_snippet': item[:1250]})
    return {'status': 'READ', 'total_explicit_articles': len(articles), 'cards': cards}


def staging_active_wsgi_mapping() -> dict[str, object]:
    conf = HOME / 'Saeit-staging-web/.htaccess'
    text = conf.read_text('utf-8', 'replace')
    match = re.search(r'(?m)^PassengerAppRoot\s+([^\s]+)', text)
    if not match:
        return {'status': 'NO_PASSENGER_ROOT'}
    app_root = Path(match.group(1).strip('"'))
    if (not str(app_root).startswith(str(HOME / 'Saeit-staging/admin-smoke/')) or
            app_root.is_symlink() or not app_root.is_dir()):
        return {'status': 'PASSENGER_ROOT_NOT_IN_EXPECTED_STAGING_TREE'}
    wsgi = app_root / 'passenger_wsgi.py'
    details: dict[str, object] = {'status': 'READ', 'root_relative': str(app_root.relative_to(HOME)),
                                  'wsgi_entry': file_info(wsgi)}
    if wsgi.is_file() and not wsgi.is_symlink() and wsgi.stat().st_size < 20000:
        code = wsgi.read_text('utf-8', 'replace')
        details['wsgi_path_literal_mentions'] = re.findall(r'/home/zomorod2/[-\w/]+', code)[:15]
        details['wsgi_import_mentions'] = re.findall(r'(?m)^\s*(?:from\s+[\w.]+\s+import|import\s+[\w.]+)', code)[:20]
        if not re.search(r'(?i)(?:password|secret|token|api[_-]?key)', code):
            details['wsgi_code_without_private_values'] = code[:2500]
    settings_candidates = [app_root / 'config/settings.py',
                           HOME / 'Saeit-staging/config/settings.py',
                           HOME / 'Saeit-staging/releases/staff-c153e541e8cf/config/settings.py']
    details['settings_candidates'] = {str(p.relative_to(HOME)): file_info(p)
                                      for p in settings_candidates}
    root = HOME / 'Saeit-staging'
    found: list[dict[str, object]] = []
    scanned = 0
    for directory, directories, filenames in os.walk(root, followlinks=False):
        directories[:] = [d for d in directories if d not in ('.git', 'node_modules', '.venv',
                          '__pycache__', 'staticfiles', 'media', 'logs') and not (Path(directory) / d).is_symlink()]
        scanned += len(filenames)
        if scanned > 25000:
            break
        if 'services.html' in filenames:
            candidate = Path(directory) / 'services.html'
            if not candidate.is_symlink() and candidate.is_file() and candidate.stat().st_size < 16000:
                record = file_info(candidate)
                found.append({'relative': str(candidate.relative_to(HOME)),
                              'sha256': record.get('sha256'), 'bytes': record.get('bytes'),
                              'contains_staging_title': record.get('contains_staging_title')})
        if len(found) >= 35:
            break
    details['all_staging_services_templates'] = found
    details['scanned_file_count_bounded'] = scanned
    details['staging_settings'] = file_info(root / 'config/settings.py')
    return details



def staging_route_and_template_context() -> dict[str, object]:
    """Report only selected nonsecret lines, not settings values or credentials."""
    htaccess = HOME / 'Saeit-staging-web/.htaccess'
    if not htaccess.is_file() or htaccess.is_symlink():
        return {'status': 'HTACCESS_UNAVAILABLE'}
    match = re.search(r'(?m)^PassengerAppRoot\s+([^\s]+)', htaccess.read_text('utf-8', 'replace'))
    if not match:
        return {'status': 'PASSENGER_ROOT_MISSING'}
    root = Path(match.group(1).strip('"'))
    expected = HOME / 'Saeit-staging/admin-smoke'
    if root.is_symlink() or not root.is_dir() or expected not in root.parents:
        return {'status': 'ROOT_NOT_EXPECTED'}
    files = {
        'active_settings': root / 'config/settings.py',
        'active_root_urls': root / 'config/urls.py',
        'active_core_urls': root / 'core/urls.py',
        'active_core_views': root / 'core/views.py',
        'active_home_template': root / 'core/templates/core/home.html',
        'active_services_template': root / 'core/templates/core/services.html',
        'active_services_view': root / 'core/services_views.py',
        'active_priority_services_template': root / 'templates/core/services.html',
        'active_priority_generic_services_template': root / 'templates/services.html',
        'canonical_services_view': HOME / 'Saeit-staging/core/services_views.py',
        'canonical_priority_services_template': HOME / 'Saeit-staging/templates/core/services.html',
        'canonical_root_urls': HOME / 'Saeit-staging/config/urls.py',
        'canonical_core_urls': HOME / 'Saeit-staging/core/urls.py',
        'canonical_core_views': HOME / 'Saeit-staging/core/views.py',
        'canonical_home_template': HOME / 'Saeit-staging/core/templates/core/home.html',
    }
    focus = re.compile(r'(?i)(?:TEMPLATES|APP_DIRS|DIRS|loaders|BASE_DIR|ROOT_URLCONF|INSTALLED_APPS|services|homepage|home|index|urlpatterns|path\(|re_path\(|include\(|render\(|template_name|cached\.Loader|cache_page|cache\.get|cache\.set|@cache|never_cache|restart|passenger)')
    sensitive = re.compile(r'(?i)(?:password|secret|credential|private.?key|api.?key|database|smtp|authorization|bearer|ssh|token|session)')
    result = {}
    for label, path in files.items():
        metadata = file_info(path)
        item = {'sha256': metadata.get('sha256'), 'bytes': metadata.get('bytes'),
                'present': metadata.get('present_regular_bounded')}
        if not metadata.get('present_regular_bounded'):
            result[label] = item
            continue
        data = path.read_text('utf-8', 'replace')
        if path.suffix == '.html':
            item['h2_static'] = [re.sub(r'<[^>]+>', '', x).strip()[:90] for x in
                                 re.findall(r'<h2\b[^>]*>(.*?)</h2>', data, re.I | re.S)][:24]
            item['template_markers'] = sorted(set(re.findall(r'{%\s*(?:include|extends|block|for)\s+[^%]{0,80}%}', data)))[:18]
        else:
            lines = data.splitlines()
            filtered = []
            for index, line in enumerate(lines):
                if focus.search(line) and not sensitive.search(line):
                    filtered.append({'line': index + 1, 'content': line.strip()[:180]})
                if len(filtered) >= 85:
                    break
            item['relevant_nonsecret_lines'] = filtered
        result[label] = item
    return {'status': 'READ_ONLY', 'files': result}


def staging_delivery_context() -> dict[str, object]:
    """Read-only Passenger restart age, settings debug and web-cache directives."""
    conf = HOME / 'Saeit-staging-web/.htaccess'
    if conf.is_symlink() or not conf.is_file():
        return {'status': 'HTACCESS_UNAVAILABLE'}
    info: dict[str, object] = {'status': 'READ_ONLY'}
    safe_lines = []
    for line in conf.read_text('utf-8', 'replace').splitlines():
        stripped = line.strip()
        if re.search(r'(?i)(?:Passenger|LiteSpeed|Cache|Expires)', stripped) and not re.search(
            r'(?i)(?:secret|key|password|token|authorization|credential|private)', stripped
        ):
            safe_lines.append(stripped[:160])
    info['nonsecret_webserver_directives'] = safe_lines[:28]
    match = re.search(r'(?m)^PassengerAppRoot\s+([^\s]+)', conf.read_text('utf-8', 'replace'))
    if not match:
        return info
    root = Path(match.group(1).strip('"'))
    if root.is_symlink() or not root.is_dir() or (HOME / 'Saeit-staging/admin-smoke') not in root.parents:
        return info
    settings = root / 'config/settings.py'
    if settings.is_file() and not settings.is_symlink() and settings.stat().st_size < 20000:
        info['django_debug_declaration'] = [line.strip()[:160] for line in
            settings.read_text('utf-8', 'replace').splitlines()
            if re.match(r'^\s*DEBUG\s*=', line) and not re.search(
                r'(?i)(?:password|secret|token|key)', line)][:2]
    marker = root / 'tmp/restart.txt'
    info['restart_marker_present'] = marker.is_file() and not marker.is_symlink()
    if info['restart_marker_present']:
        info['restart_marker_epoch'] = int(marker.stat().st_mtime)
    uptime = None
    try:
        uptime = float(Path('/proc/uptime').read_text().split()[0])
    except (OSError, ValueError, IndexError):
        pass
    process_ages = []
    for candidate in Path('/proc').iterdir():
        if not candidate.name.isdecimal():
            continue
        try:
            cmdline = (candidate / 'cmdline').read_bytes().replace(b'\x00', b' ').decode('utf-8', 'replace')
            if str(root) not in cmdline:
                continue
            stat_data = (candidate / 'stat').read_text().split(') ', 1)[1].split()
            start_ticks = int(stat_data[19])
            if uptime is not None:
                age = max(0, int(uptime - start_ticks / os.sysconf('SC_CLK_TCK')))
                process_ages.append(age)
        except (OSError, IndexError, ValueError, PermissionError):
            continue
    info['matching_staging_passenger_process_count'] = len(process_ages)
    info['matching_staging_passenger_process_ages_sec'] = sorted(process_ages)[:10]
    return info


def staging_passenger_process_origins() -> dict[str, object]:
    """Inspect owned process workdirs without exposing commands or environments."""
    records = []
    for candidate in Path('/proc').iterdir():
        if not candidate.name.isdecimal():
            continue
        try:
            command = (candidate / 'cmdline').read_bytes().replace(b'\x00', b' ').decode('utf-8', 'replace')
            if 'Saeit-staging' not in command:
                continue
            workdir = os.readlink(str(candidate / 'cwd'))
            home_prefix = str(HOME) + '/'
            sanitized_workdir = workdir[len(home_prefix):] if workdir.startswith(home_prefix) else 'OUTSIDE_EXPECTED_HOME'
            arguments = command.lower()
            records.append({'cwd_relative': sanitized_workdir[:160],
                            'is_passenger': 'passenger' in arguments,
                            'is_active_root': 'admin-smoke/ab090d03f5bc-38498776878' in arguments})
        except (OSError, PermissionError):
            continue
    return {'changed_files': 0, 'matched_process_count': len(records), 'processes': records[:35]}


def staging_passenger_restart_tool_capability() -> dict[str, object]:
    """Check documented Passenger restart tool availability, without restarting."""
    import shutil
    choices = [
        shutil.which('passenger-config'),
        '/usr/bin/passenger-config',
        '/usr/local/bin/passenger-config',
        '/opt/cpanel/ea-ruby27/root/usr/bin/passenger-config',
        '/opt/cpanel/ea-ruby33/root/usr/bin/passenger-config',
        '/opt/cpanel/ea-ruby32/root/usr/bin/passenger-config',
    ]
    found = []
    for entry in choices:
        if not entry or entry in found:
            continue
        candidate = Path(entry)
        if candidate.is_file() and os.access(candidate, os.X_OK):
            found.append(str(candidate))
    import subprocess
    selector_choices = [shutil.which('cloudlinux-selector'),
                        '/usr/bin/cloudlinux-selector', '/usr/sbin/cloudlinux-selector']
    available = next((path for path in selector_choices if path
                      and Path(path).is_file() and os.access(path, os.X_OK)), None)
    report = {'changed_files': 0, 'documented_restart_tool_paths': found[:8],
              'cloudlinux_selector_path': available}
    if available is not None:
        try:
            proc = subprocess.run([available, 'get', '--json', '--interpreter', 'python', '--user', 'zomorod2'],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  check=False, timeout=14)
            report['selector_readonly_get_exit'] = proc.returncode
            if proc.returncode == 0 and len(proc.stdout) < 1000000:
                payload = json.loads(proc.stdout.decode('utf-8', 'replace'))
                selected = []
                def walk(obj: object, depth: int = 0) -> None:
                    if depth > 9 or len(selected) >= 12:
                        return
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            if key.lower().replace('-', '_') in ('app_root', 'approot') and isinstance(value, str):
                                if 'Saeit-staging' in value:
                                    selected.append(value[:170])
                            elif isinstance(value, (dict, list)):
                                walk(value, depth + 1)
                    elif isinstance(obj, list):
                        for element in obj[:100]:
                            walk(element, depth + 1)
                walk(payload)
                report['registered_staging_app_roots'] = selected
                report['selector_mentions_stage_root'] = 'Saeit-staging' in proc.stdout.decode('utf-8', 'replace')
                report['selector_top_level_fields'] = [str(k)[:50] for k in list(payload)[:18]] if isinstance(payload, dict) else ['NON_OBJECT']
        except (OSError, ValueError, subprocess.TimeoutExpired):
            report['selector_readonly_get_exit'] = 'UNAVAILABLE'
    return report


def staging_django_bootstrap_safety() -> dict[str, object]:
    """Static checks before any isolated Django template-origin introspection."""
    conf = HOME / 'Saeit-staging-web/.htaccess'
    if conf.is_symlink() or not conf.is_file():
        return {'status': 'CONF_UNAVAILABLE'}
    match = re.search(r'(?m)^PassengerAppRoot\s+([^\s]+)', conf.read_text('utf-8', 'replace'))
    if not match:
        return {'status': 'ROOT_MISSING'}
    root = Path(match.group(1).strip('"'))
    if root.is_symlink() or not root.is_dir() or (HOME / 'Saeit-staging/admin-smoke') not in root.parents:
        return {'status': 'ROOT_OUT_OF_SCOPE'}
    candidates = {
        'core_apps': root / 'core/apps.py',
        'command_center_apps': root / 'command_center/apps.py',
        'sitecore_apps': root / 'sitecore/apps.py',
        'core_services_view': root / 'core/services_views.py',
    }
    report = {}
    for label, path in candidates.items():
        info = file_info(path)
        if not info.get('present_regular_bounded'):
            report[label] = {'present': False}
            continue
        source = path.read_text('utf-8', 'replace')
        safe_lines = [line.strip()[:140] for line in source.splitlines()
                      if re.search(r'(?i)(?:class\s+\w+Config|def\s+ready\(|get_template\(|render\(|cache_page|lru_cache|template_name)', line)
                      and not re.search(r'(?i)(?:secret|password|credential|api.?key|private.?key|token)', line)]
        report[label] = {'present': True,
                         'sha256': info.get('sha256'),
                         'custom_ready_method_present': bool(re.search(r'\bdef\s+ready\s*\(', source)),
                         'scheduling_or_network_import_mentions': bool(re.search(
                            r'(?i)(?:scheduler|schedule\.|celery|threading\.Thread|requests\.(?:post|get)|httpx\.)', source)),
                         'safe_focus_lines': safe_lines[:28]}
    return {'status': 'READ_ONLY', 'components': report}


def staging_isolated_django_template_resolution() -> dict[str, object]:
    """Resolve the effective Django template in a no-bytecode, isolated process."""
    import subprocess
    conf = HOME / 'Saeit-staging-web/.htaccess'
    match = re.search(r'(?m)^PassengerAppRoot\s+([^\s]+)', conf.read_text('utf-8', 'replace')) if conf.is_file() and not conf.is_symlink() else None
    if not match:
        return {'status': 'PASSENGER_ROOT_UNAVAILABLE'}
    root = Path(match.group(1).strip('"'))
    if root.is_symlink() or not root.is_dir() or (HOME / 'Saeit-staging/admin-smoke') not in root.parents:
        return {'status': 'ROOT_OUT_OF_SCOPE'}
    python = HOME / 'virtualenv/Saeit-staging/3.11/bin/python'
    if not python.is_file() or not os.access(python, os.X_OK):
        return {'status': 'STAGING_PYTHON_UNAVAILABLE'}
    preflight = staging_django_bootstrap_safety()
    if preflight.get('status') != 'READ_ONLY' or any(
        x.get('custom_ready_method_present') or x.get('scheduling_or_network_import_mentions')
        for x in preflight.get('components', {}).values() if isinstance(x, dict)
    ):
        return {'status': 'BOOTSTRAP_PRECONDITION_NOT_MET'}
    code = r'''
import json, os, sys
from pathlib import Path
root = Path(os.environ['ZM_STAGING_APP_ROOT'])
sys.path.insert(0, str(root))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
import django
django.setup()
from django.template import engines
from django.apps import apps
from django.conf import settings
backend = engines['django']
loaded = backend.get_template('core/services.html')
origin = Path(loaded.template.origin.name)
if str(origin).startswith(str(root) + '/'):
    origin_label = str(origin.relative_to(root))
else:
    origin_label = 'OUTSIDE_ACTIVE_STAGING_ROOT'
loaders = [type(obj).__module__ + '.' + type(obj).__name__ for obj in backend.engine.template_loaders]
print('DJANGO_TEMPLATE_ORIGIN_READONLY=' + json.dumps({
    'origin_relative': origin_label,
    'core_registered': apps.is_installed('core'),
    'loader_classes': loaders,
    'django_debug': bool(settings.DEBUG),
    'cache_page_middleware_configured': any('CacheMiddleware' in str(x) for x in settings.MIDDLEWARE),
}, sort_keys=True))
'''
    env = os.environ.copy()
    env['ZM_STAGING_APP_ROOT'] = str(root)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['PYTHONNOUSERSITE'] = '1'
    try:
        proc = subprocess.run([str(python), '-I', '-B', '-c', code], cwd=root,
                              env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=18, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return {'status': 'SUBPROCESS_UNAVAILABLE'}
    marker = 'DJANGO_TEMPLATE_ORIGIN_READONLY='
    records = [row[len(marker):] for row in proc.stdout.decode('utf-8', 'replace').splitlines() if row.startswith(marker)]
    if proc.returncode == 0 and len(records) == 1:
        try:
            return {'status': 'READ_ONLY', 'resolved': json.loads(records[0])}
        except ValueError:
            pass
    return {'status': 'IMPORT_OR_RESOLUTION_UNAVAILABLE', 'exit_code': proc.returncode,
            'stderr_disclosed': False}

def staging_origin_bypass_readonly() -> dict[str, object]:
    """Compare public DNS route against explicitly-pinned hosting origin with TLS validation."""
    import shutil
    import socket
    import subprocess
    cli = shutil.which('curl')
    if not cli:
        return {'status': 'CURL_UNAVAILABLE', 'changed_files': 0}
    host = 'staging.zomorodmelal.ir'
    addresses = []
    try:
        addresses = sorted(set(addr[4][0] for addr in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
                               if addr[0] == socket.AF_INET))[:6]
    except OSError:
        pass
    routes = {
        'domain_dns': None,
        'pinned_cpanel_host': '178.239.147.125',
        'localhost_https': '127.0.0.1',
    }
    results = {}
    for route_name, route_ip in routes.items():
        argv = [cli, '--silent', '--show-error', '--max-time', '12', '--connect-timeout', '5',
                '--compressed', '--header', 'Cache-Control: no-cache, no-store',
                '--header', 'Pragma: no-cache', '--header', 'User-Agent: ZM-Staging-ReadOnly-Origin-Compare',
                '--write-out', '\n__ZM_HTTP_STATUS__%{http_code}']
        if route_ip is not None:
            argv += ['--resolve', host + ':443:' + route_ip]
        argv += ['https://' + host + '/?zm_origin_compare=20261105-' + route_name]
        try:
            p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               timeout=15, check=False)
        except (OSError, subprocess.TimeoutExpired):
            results[route_name] = {'status': 'COMMAND_UNAVAILABLE'}
            continue
        output = p.stdout[:230000]
        marker = b'\n__ZM_HTTP_STATUS__'
        position = output.rfind(marker)
        if p.returncode != 0 or position < 0:
            results[route_name] = {'status': 'HTTP_ROUTE_UNAVAILABLE', 'exit_code': p.returncode}
            continue
        body = output[:position]
        http_code = output[position + len(marker):].decode('ascii', 'replace')[:3]
        raw = body.decode('utf-8', 'replace')
        headings = [re.sub('<[^>]+>', '', x).strip()[:90] for x in
                    re.findall(r'<h2[^>]*>(.*?)</h2>', raw, re.I | re.S)]
        results[route_name] = {'status': 'READ_ONLY', 'http': http_code,
                               'body_sha256': hashlib.sha256(body).hexdigest(),
                               'heading_count': len(headings), 'headings': headings[:22]}
    return {'status': 'READ_ONLY', 'changed_files': 0,
            'public_dns_ipv4': addresses, 'routes': results}


def staging_owned_worker_restart_safety() -> dict[str, object]:
    """Read only: identify exact app-specific Passenger workers eligible for a targeted restart."""
    conf = HOME / 'Saeit-staging-web/.htaccess'
    if conf.is_symlink() or not conf.is_file():
        return {'status': 'CONF_UNAVAILABLE'}
    m = re.search(r'(?m)^PassengerAppRoot\s+([^\s]+)', conf.read_text('utf-8', 'replace'))
    if not m:
        return {'status': 'NO_ACTIVE_ROOT'}
    root = Path(m.group(1).strip('"'))
    base = HOME / 'Saeit-staging/admin-smoke'
    if root.is_symlink() or not root.is_dir() or base not in root.parents:
        return {'status': 'OUT_OF_SCOPE'}
    current_uid = os.geteuid()
    items = []
    matched = 0
    for folder in Path('/proc').iterdir():
        if not folder.name.isdecimal():
            continue
        try:
            command = (folder / 'cmdline').read_bytes().replace(b'\x00', b' ').decode('utf-8', 'replace')
            if str(root) not in command:
                continue
            matched += 1
            process_uid = (folder / 'status').read_text('utf-8', 'replace')
            uid_match = re.search(r'(?m)^Uid:\s+(\d+)', process_uid)
            owner_matches = bool(uid_match and int(uid_match.group(1)) == current_uid)
            executable = Path((folder / 'exe').resolve()).name[:55]
            cwd = os.readlink(str(folder / 'cwd'))
            same_workdir = cwd == str(root)
            is_passenger = 'passenger' in command.lower()
            items.append({'pid': int(folder.name), 'owner_matches': owner_matches,
                          'cwd_is_exact_active_root': same_workdir,
                          'is_passenger': is_passenger, 'executable_name': executable,
                          'eligible_for_targeted_restart': owner_matches and same_workdir and is_passenger})
        except (OSError, PermissionError, ValueError):
            continue
    return {'status': 'READ_ONLY', 'changed_files': 0,
            'matching_root_process_count': matched, 'details': items[:16]}


def staging_registered_passenger_apps() -> dict[str, object]:
    """List only staging cPanel Passenger registrations; omit environment variables."""
    import subprocess
    cli = Path('/usr/local/cpanel/bin/uapi')
    if not cli.is_file() or not os.access(cli, os.X_OK):
        return {'status': 'CPANEL_UAPI_UNAVAILABLE', 'changed_files': 0}
    try:
        # The SSH identity is already zomorod2; --user is privileged on some cPanel builds.
        p = subprocess.run(
            [str(cli), '--output=json', 'PassengerApps', 'list_applications'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=23, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return {'status': 'CPANEL_UAPI_COMMAND_UNAVAILABLE', 'changed_files': 0}
    result: dict[str, object] = {'status': 'READ_ONLY', 'changed_files': 0,
                                 'command_exit': p.returncode,
                                 'stderr_is_empty': not bool(p.stderr.strip())}
    if p.returncode != 0 or len(p.stdout) > 1500000:
        result['status'] = 'CPANEL_UAPI_FAILED'
        return result
    try:
        payload = json.loads(p.stdout.decode('utf-8', 'replace'))
    except (ValueError, UnicodeError):
        result['status'] = 'CPANEL_UAPI_INVALID_RESPONSE'
        return result
    api_result = payload.get('result', {}) if isinstance(payload, dict) else {}
    if not isinstance(api_result, dict):
        result['status'] = 'CPANEL_UAPI_UNEXPECTED_RESULT'
        return result
    result['api_success'] = api_result.get('status') == 1
    data = api_result.get('data')
    if not result['api_success'] or not isinstance(data, (dict, list)):
        result['status'] = 'CPANEL_UAPI_NO_REGISTRY'
        return result
    applications = []
    items = list(data.values()) if isinstance(data, dict) else data
    for row in items[:120]:
        if not isinstance(row, dict):
            continue
        path = str(row.get('path', ''))
        domain = str(row.get('domain', ''))
        if not (path.startswith('/home/zomorod2/Saeit-staging') or
                domain == 'staging.zomorodmelal.ir'):
            continue
        applications.append({
            'path_relative': path[len('/home/zomorod2/'):] if path.startswith('/home/zomorod2/') else 'OUTSIDE_EXPECTED_HOME',
            'domain_is_staging': domain == 'staging.zomorodmelal.ir',
            'name': str(row.get('name', ''))[:90],
            'enabled': row.get('enabled') == 1,
            'base_uri': str(row.get('base_uri', ''))[:90],
        })
    result['registered_staging_applications'] = applications[:12]
    result['total_entries'] = len(items)
    return result


def staging_template_settings_block() -> dict[str, object]:
    """Bounded, nonsecret TEMPLATES configuration block from active staging only."""
    conf = HOME / 'Saeit-staging-web/.htaccess'
    match = re.search(r'(?m)^PassengerAppRoot\s+([^\s]+)', conf.read_text('utf-8', 'replace')) if conf.is_file() and not conf.is_symlink() else None
    if not match:
        return {'status': 'ROOT_UNAVAILABLE'}
    root = Path(match.group(1).strip('"'))
    if root.is_symlink() or not root.is_dir() or (HOME / 'Saeit-staging/admin-smoke') not in root.parents:
        return {'status': 'ROOT_OUT_OF_SCOPE'}
    settings_file = root / 'config/settings.py'
    info = file_info(settings_file)
    if not info.get('present_regular_bounded'):
        return {'status': 'SETTINGS_UNAVAILABLE'}
    code = settings_file.read_text('utf-8', 'replace')
    beginning = re.search(r'(?m)^TEMPLATES\s*=\s*\[', code)
    if not beginning:
        return {'status': 'TEMPLATES_NOT_FOUND'}
    rest = code[beginning.start():]
    end = re.search(r'(?m)^\]\s*$', rest)
    if not end or end.end() > 2800:
        return {'status': 'TEMPLATE_BLOCK_NOT_BOUNDED'}
    block = rest[:end.end()]
    if re.search(r'(?i)(?:secret|password|private.?key|api.?key|token|credential)', block):
        return {'status': 'PRIVATE_VALUE_GUARD'}
    return {'status': 'READ_ONLY', 'active_settings_sha': info.get('sha256'),
            'templates_settings_block': block}

if __name__ == '__main__':
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise SystemExit('CPANEL_IDENTITY_MISMATCH')
    print('STAGING_BUSINESS_SOURCE_READONLY=' + json.dumps({
        'changed_files': 0,
        'public': {
            'staging': probe_public('https://staging.zomorodmelal.ir/'),
            'staging_query_uncached_candidate': probe_public('https://staging.zomorodmelal.ir/?zm_template_route_diag=20261105'),
            'business': probe_public('https://zomorodmelal.ir/business/'),
        }, 'source': source_inventory(), 'staging_card_source': staging_public_card_source(),
        'active_staging_routing': staging_active_wsgi_mapping(),
        'route_and_template_context': staging_route_and_template_context(),
        'staging_delivery_context': staging_delivery_context(),
        'staging_process_origins': staging_passenger_process_origins(),
        'passenger_restart_tool': staging_passenger_restart_tool_capability(),
        'registered_passenger_apps': staging_registered_passenger_apps(),
        'owned_worker_restart_safety': staging_owned_worker_restart_safety(),
        'origin_bypass_comparison': staging_origin_bypass_readonly(),
        'django_bootstrap_preflight': staging_django_bootstrap_safety(),
        'isolated_django_template_origin': staging_isolated_django_template_resolution(),
        'active_template_settings_block': staging_template_settings_block()},
        ensure_ascii=False, sort_keys=True))
