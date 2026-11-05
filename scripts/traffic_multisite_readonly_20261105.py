#!/usr/bin/env python3
"""One-time aggregate traffic inventory on the established cPanel SSH relay.

No customer records, raw access lines, IP addresses, user agents, or secrets leave
the cPanel host. This script never writes files or changes cPanel settings.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
import gzip
import json
import re
import subprocess


ROOT = Path('/home/zomorod2')
BASES = ('zomorodmelal.ir', 'mojplaywin.com')
NOW = datetime.now(timezone.utc)
CUTOFF = NOW - timedelta(days=30)
BOT = re.compile(r'bot|spider|crawl|monitor|uptime|headless|curl|wget|python-requests|postman|github-actions|go-http-client', re.I)
AI_AGENT = re.compile(r'(GPTBot|OAI-SearchBot|ChatGPT-User|ClaudeBot|Claude-SearchBot|Claude-User|PerplexityBot|Perplexity-User|Bytespider|CCBot|Google-Extended|meta-externalagent)', re.I)
BROWSER = re.compile(r'(?:Firefox|FxiOS|Chrome|CriOS|Edg|OPR|SamsungBrowser)/\d+|Version/\d+.*Safari/', re.I)
APACHE = re.compile(r'^(\S+)\s+\S+\s+\S+\s+\[([^\]]+)\]\s+"(GET|POST|HEAD)\s+(\S+)\s+HTTP/[^\"]+"\s+(\d{3})\s+.*?"[^\"]*"\s+"([^\"]*)"')
VALID = re.compile(r'^[a-z0-9][a-z0-9.-]{2,252}$')
REFERRER = re.compile(r'"\s+\d{3}\s+\S+\s+"([^"]*)"\s+"[^"]*"')


def report(key, data):
    print(key + '=' + json.dumps(data, sort_keys=True, ensure_ascii=False))


def domains():
    known = set(BASES)
    status = 'fallback_known_domains'
    try:
        proc = subprocess.run(['uapi', '--output=json', 'DomainInfo', 'list_domains'],
                              capture_output=True, timeout=18, check=False)
        if proc.returncode == 0 and len(proc.stdout) < 2000000:
            obj = json.loads(proc.stdout.decode('utf-8'))
            result = obj.get('result') or {}
            if result.get('status') in (1, True):
                data = result.get('data') or {}
                if isinstance(data, dict):
                    for field in ('main_domain', 'addon_domains', 'sub_domains', 'parked_domains'):
                        value = data.get(field, [])
                        values = value if isinstance(value, list) else [value]
                        for item in values:
                            if isinstance(item, str):
                                host = item.lower().strip('. ')
                                if VALID.fullmatch(host) and any(
                                    host == base or host.endswith('.' + base) for base in BASES
                                ):
                                    known.add(host)
                    status = 'cpanel_domaininfo'
    except (OSError, ValueError, TypeError, subprocess.TimeoutExpired):
        pass
    return sorted(known), status


def awstats(hosts):
    folder = ROOT / 'tmp' / 'awstats'
    stats = []
    inspected = 0
    if folder.is_dir() and not folder.is_symlink():
        for path in sorted(folder.iterdir(), key=lambda p: p.name):
            match = re.fullmatch(r'awstats(\d{2})(\d{4})\.(.+)\.txt', path.name)
            if not match or path.is_symlink() or not path.is_file():
                continue
            month, year, host = match.groups()
            if host not in hosts or not (1 <= int(month) <= 12):
                continue
            if (int(year), int(month)) < (CUTOFF.year, CUTOFF.month):
                continue
            if path.stat().st_size > 16000000 or inspected >= 150:
                continue
            inspected += 1
            info = {'domain': host, 'month': year + '-' + month}
            inside = False
            try:
                with path.open('rt', encoding='utf-8', errors='replace') as stream:
                    for line in stream:
                        if line.startswith('BEGIN_GENERAL'):
                            inside = True
                            continue
                        if line.startswith('END_GENERAL'):
                            break
                        if inside:
                            parts = line.strip().split(' ', 1)
                            if len(parts) == 2 and parts[0] in (
                                'TotalVisits', 'TotalUnique', 'TotalPages', 'TotalHits',
                                'TotalBytes', 'FirstTime', 'LastTime', 'LastUpdate'
                            ) and re.fullmatch(r'[0-9]+', parts[1]):
                                info[parts[0]] = int(parts[1])
                if len(info) > 2:
                    stats.append(info)
            except OSError:
                continue
    report('MULTISITE_AWSTATS', {
        'source': 'cpanel_local_monthly_awstats', 'folder_available': folder.is_dir(),
        'files_inspected': inspected, 'records': stats,
        'note': 'Calendar-month totals as stored by AWStats; not additive to raw-log hits.'
    })


def log_host(filename, hosts):
    for host in sorted(hosts, key=len, reverse=True):
        for prefix in (host, 'www.' + host):
            if filename.startswith((prefix + '-', prefix + '_', prefix + '.')):
                return host
    return None


def is_page(path):
    return path == '/' or path.endswith(('/', '.html', '.htm', '.php'))


def google_referral(line, destination_host):
    found = REFERRER.search(line)
    if not found or not found.group(1).startswith(('https://', 'http://')):
        return False, False, 'missing_or_hidden'
    try:
        hostname = (urlsplit(found.group(1)).hostname or '').lower().rstrip('.')
    except ValueError:
        return False, False, 'missing_or_hidden'
    if not hostname or not VALID.fullmatch(hostname):
        return False, False, 'missing_or_hidden'
    if re.fullmatch(r'(?:[a-z0-9-]+\.)*google\.[a-z]{2,}(?:\.[a-z]{2,})?', hostname):
        return True, True, 'google'
    if hostname in (destination_host, 'www.' + destination_host):
        return True, False, 'same_site_navigation'
    if any(hostname == base or hostname.endswith('.' + base) for base in BASES):
        return True, False, 'other_own_site'
    if any(hostname == site or hostname.endswith('.' + site) for site in
           ('bing.com', 'duckduckgo.com', 'yahoo.com', 'yandex.ru', 'yandex.com',
            'baidu.com', 'ecosia.org', 'brave.com', 'qwant.com')):
        return True, False, 'other_search_engine'
    social = {
        'instagram': ('instagram.com', 'instagr.am'),
        'facebook': ('facebook.com', 'fb.com', 'fb.me'),
        'telegram': ('t.me', 'telegram.org'),
        'linkedin': ('linkedin.com',),
        'youtube': ('youtube.com', 'youtu.be'),
        'x_twitter': ('twitter.com', 'x.com', 't.co'),
        'reddit': ('reddit.com',),
        'whatsapp': ('whatsapp.com', 'wa.me'),
        'pinterest': ('pinterest.com', 'pin.it'),
    }
    for source, names in social.items():
        if any(hostname == name or hostname.endswith('.' + name) for name in names):
            return True, False, source
    return True, False, 'other_external_site'



def ai_referrer_name(line):
    found = REFERRER.search(line)
    if not found or not found.group(1).startswith(('https://', 'http://')):
        return None
    try:
        host = (urlsplit(found.group(1)).hostname or '').lower().rstrip('.')
    except ValueError:
        return None
    services = {
        'chatgpt': ('chatgpt.com', 'chat.openai.com'),
        'perplexity': ('perplexity.ai',),
        'claude': ('claude.ai',),
        'gemini': ('gemini.google.com',),
        'copilot': ('copilot.microsoft.com',),
        'poe': ('poe.com',),
        'you': ('you.com',),
        'phind': ('phind.com',),
        'deepseek': ('chat.deepseek.com',),
    }
    for name, domains in services.items():
        if any(host == d or host.endswith('.' + d) for d in domains):
            return name
    return None


def page_group(host, path):
    p = path.lower()
    if host == 'mojplaywin.com':
        if p.startswith('/mojtaba.roozegar'):
            if p.rstrip('/') == '/mojtaba.roozegar':
                return 'personal_profile'
            return 'personal_other'
        if '/checkout/' in p or p.startswith('/checkout/'):
            return 'store_checkout'
        if p.startswith('/store/product/'):
            return 'store_product'
        if p.startswith('/store/'):
            return 'store_other'
        if p.startswith(('/games/', '/game/')):
            return 'gaming'
        if p == '/':
            return 'homepage'
        return 'other'
    if p.startswith(('/business/', '/services/', '/service/')):
        return 'corporate_business'
    if p.startswith(('/agriculture/', '/industry/')):
        return 'corporate_services'
    if p.startswith(('/contact/', '/contacts/')):
        return 'corporate_contact'
    if p.startswith(('/research/', '/knowledge/')):
        return 'corporate_knowledge'
    if p.startswith(('/auction/', '/auctions/')):
        return 'corporate_auction'
    if p.startswith(('/games/', '/game/', '/apps/')):
        return 'entertainment'
    if p == '/':
        return 'homepage'
    return 'other'


def raw_logs(hosts):
    folder = ROOT / 'logs'
    files = []
    skipped_oversize = 0
    if folder.is_dir() and not folder.is_symlink():
        for path in folder.iterdir():
            if not path.is_file() or path.is_symlink():
                continue
            host = log_host(path.name.lower(), hosts)
            if host is None or not path.name.lower().endswith(('.gz', '.log', '_log')):
                continue
            if path.stat().st_size > 120000000:
                skipped_oversize += 1
                continue
            files.append((host, path))
    files.sort(key=lambda x: x[1].stat().st_mtime, reverse=True)
    selected = files[:80]
    totals = defaultdict(lambda: {
        'files_scanned': 0, 'log_lines_scanned': 0, 'requests_30d': 0,
        'successful_page_requests': 0, 'likely_human_page_requests': 0,
        'likely_bot_page_requests': 0, 'store_page_requests': 0,
        'product_page_requests': 0, 'checkout_page_requests': 0,
        'personal_site_human_page_requests': 0,
        'source_categories': defaultdict(int),
        'personal_source_categories': defaultdict(int),
        'human_page_requests_with_referrer': 0,
        'google_referral_human_page_requests': 0,
        'personal_google_referral_human_page_requests': 0,
        'personal_site_bot_page_requests': 0,
        'personal_site_4xx_page_requests': 0,
        'personal_site_5xx_page_requests': 0,
        'http_4xx_page_requests': 0, 'http_5xx_page_requests': 0,
        'first_utc': None, 'last_utc': None,
    })
    unique = defaultdict(set)
    personal_unique = defaultdict(set)
    google_unique = defaultdict(set)
    personal_google_unique = defaultdict(set)
    quality = defaultdict(lambda: {
        'strict_browser_page_requests': 0,
        'nonbrowser_nonbot_page_requests': 0,
        'ai_agent_page_requests': defaultdict(int),
        'strict_browser_referrer_categories': defaultdict(int),
        'strict_browser_page_groups': defaultdict(int),
        'strict_browser_ai_referrals': defaultdict(int),
    })
    browser_events = defaultdict(list)
    truncated = False
    scanned = 0
    for host, path in selected:
        row = totals[host]
        row['files_scanned'] += 1
        opener = gzip.open if path.name.lower().endswith('.gz') else open
        try:
            with opener(path, 'rt', encoding='utf-8', errors='replace') as stream:
                for line in stream:
                    scanned += 1
                    row['log_lines_scanned'] += 1
                    if scanned > 1800000:
                        truncated = True
                        break
                    matched = APACHE.match(line)
                    if not matched:
                        continue
                    ip, timestamp, method, target, status, agent = matched.groups()
                    try:
                        at = datetime.strptime(timestamp, '%d/%b/%Y:%H:%M:%S %z').astimezone(timezone.utc)
                    except ValueError:
                        continue
                    if not CUTOFF <= at <= NOW + timedelta(minutes=5):
                        continue
                    row['requests_30d'] += 1
                    date = at.isoformat()
                    row['first_utc'] = min(row['first_utc'], date) if row['first_utc'] else date
                    row['last_utc'] = max(row['last_utc'], date) if row['last_utc'] else date
                    target = target.split('?', 1)[0]
                    if not is_page(target) or method != 'GET':
                        continue
                    personal = host == 'mojplaywin.com' and (
                        target == '/mojtaba.roozegar' or target.startswith('/mojtaba.roozegar/')
                    )
                    if status.startswith('4'):
                        row['http_4xx_page_requests'] += 1
                        if personal:
                            row['personal_site_4xx_page_requests'] += 1
                    elif status.startswith('5'):
                        row['http_5xx_page_requests'] += 1
                        if personal:
                            row['personal_site_5xx_page_requests'] += 1
                    if not status.startswith(('2', '3')):
                        continue
                    row['successful_page_requests'] += 1
                    ai_agent = AI_AGENT.search(agent)
                    if ai_agent:
                        quality[host]['ai_agent_page_requests'][ai_agent.group(1).lower()] += 1
                    if BOT.search(agent) or ai_agent:
                        row['likely_bot_page_requests'] += 1
                        if personal:
                            row['personal_site_bot_page_requests'] += 1
                        continue
                    row['likely_human_page_requests'] += 1
                    has_referrer, from_google, source_category = google_referral(line, host)
                    row['source_categories'][source_category] += 1
                    if BROWSER.search(agent):
                        quality[host]['strict_browser_page_requests'] += 1
                        bucket = page_group(host, target)
                        quality[host]['strict_browser_page_groups'][bucket] += 1
                        quality[host]['strict_browser_referrer_categories'][source_category] += 1
                        ai_source = ai_referrer_name(line)
                        if ai_source:
                            quality[host]['strict_browser_ai_referrals'][ai_source] += 1
                        browser_events[host].append((ip, agent, at, bucket, source_category, ai_source))
                    else:
                        quality[host]['nonbrowser_nonbot_page_requests'] += 1
                    if personal:
                        row['personal_source_categories'][source_category] += 1
                    if has_referrer:
                        row['human_page_requests_with_referrer'] += 1
                    if from_google:
                        row['google_referral_human_page_requests'] += 1
                        if len(google_unique[host]) < 100000:
                            google_unique[host].add(ip)
                        if personal:
                            row['personal_google_referral_human_page_requests'] += 1
                            if len(personal_google_unique[host]) < 100000:
                                personal_google_unique[host].add(ip)
                    if personal:
                        row['personal_site_human_page_requests'] += 1
                        if len(personal_unique[host]) < 100000:
                            personal_unique[host].add(ip)
                    if len(unique[host]) < 100000:
                        unique[host].add(ip)
                    if target.startswith('/store/'):
                        row['store_page_requests'] += 1
                    if target.startswith('/store/product/') and '/checkout/' not in target:
                        row['product_page_requests'] += 1
                    if '/checkout/' in target:
                        row['checkout_page_requests'] += 1
        except (OSError, EOFError, ValueError):
            row['file_read_errors'] = row.get('file_read_errors', 0) + 1
        if truncated:
            break
    for host, row in totals.items():
        row['approx_distinct_ips'] = len(unique[host])
        row['personal_site_approx_distinct_ips'] = len(personal_unique[host])
        row['google_referral_approx_distinct_ips'] = len(google_unique[host])
        row['personal_google_referral_approx_distinct_ips'] = len(personal_google_unique[host])
    for host, events in browser_events.items():
        events.sort(key=lambda e: (e[0], e[1], e[2]))
        q = quality[host]
        q['estimated_30min_browser_sessions'] = 0
        q['estimated_sessions_by_landing_source'] = defaultdict(int)
        q['estimated_sessions_by_landing_group'] = defaultdict(int)
        q['estimated_sessions_with_product'] = 0
        q['estimated_sessions_with_checkout'] = 0
        q['estimated_sessions_with_contact'] = 0
        q['estimated_sessions_with_business_or_services'] = 0
        q['estimated_sessions_with_personal_profile'] = 0
        q['estimated_sessions_with_multiple_page_requests'] = 0
        q['estimated_sessions_suspicious_40plus_pages'] = 0
        q['estimated_sessions_with_ai_referrer'] = 0

        def add_session(s):
            if s is None:
                return
            q['estimated_30min_browser_sessions'] += 1
            q['estimated_sessions_by_landing_source'][s['source']] += 1
            q['estimated_sessions_by_landing_group'][s['landing']] += 1
            groups = s['groups']
            for group, label in (
                ('store_product', 'estimated_sessions_with_product'),
                ('store_checkout', 'estimated_sessions_with_checkout'),
                ('corporate_contact', 'estimated_sessions_with_contact'),
                ('personal_profile', 'estimated_sessions_with_personal_profile'),
            ):
                if group in groups:
                    q[label] += 1
            if {'corporate_business', 'corporate_services'} & groups:
                q['estimated_sessions_with_business_or_services'] += 1
            if s['pages'] > 1:
                q['estimated_sessions_with_multiple_page_requests'] += 1
            if s['pages'] >= 40:
                q['estimated_sessions_suspicious_40plus_pages'] += 1
            if s['ai']:
                q['estimated_sessions_with_ai_referrer'] += 1

        current_key = None
        previous_at = None
        session = None
        for ip, ua, at, group, ref, ai in events:
            key = (ip, ua)
            if key != current_key or previous_at is None or at - previous_at > timedelta(minutes=30):
                add_session(session)
                session = {
                    'source': ref if ref != 'same_site_navigation' else 'missing_or_hidden',
                    'landing': group, 'groups': set(), 'pages': 0, 'ai': False,
                }
            session['groups'].add(group)
            session['pages'] += 1
            session['ai'] = session['ai'] or bool(ai)
            current_key, previous_at = key, at
        add_session(session)
    report('MULTISITE_QUALITY_AND_FUNNEL', {
        'source': 'cpanel_raw_access_30d_bounded_browser_heuristics',
        'generated_utc': NOW.isoformat(), 'cutoff_utc': CUTOFF.isoformat(),
        'domain_rows': dict(sorted(quality.items())),
        'limitations': (
            'Browser markers are not proof of humans; automated browsers can imitate them; '
            'IP plus user-agent plus 30-minute gap yields approximate sessions, not GA4 sessions. '
            'Page-group visit is not buyer intent; checkout page is not payment. '
            'No identities, IPs, UAs, URLs or orders are printed.'
        ),
    })
    report('MULTISITE_RAW_LOGS', {
        'source': 'cpanel_raw_access_30d', 'generated_utc': NOW.isoformat(),
        'cutoff_utc': CUTOFF.isoformat(), 'available': folder.is_dir(),
        'files_available': len(files), 'files_scanned': len(selected),
        'skipped_oversize': skipped_oversize, 'truncated': truncated,
        'domain_rows': dict(sorted(totals.items())),
        'limitations': 'Request counts are not visits or humans; IP counts are approximations; archives can lag or overlap.'
    })


if __name__ == '__main__':
    hosts, source = domains()
    report('MULTISITE_DOMAINS', {'source': source, 'hosts': hosts, 'readonly': True})
    awstats(hosts)
    raw_logs(hosts)
    report('MULTISITE_AUDIT', {'completed': True, 'remote_writes': False,
                               'raw_identifiers_printed': False})
