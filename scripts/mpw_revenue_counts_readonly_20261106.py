#!/usr/bin/env python3
"""Print privacy-preserving aggregates from live private MojPlayWin storage.

Never reads encrypted inquiry records, keys, email addresses, IPs or order data.
Only counts filenames and known anonymous aggregate metric counters.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import stat

PRIVATE = Path('/home/zomorod2/.private_mojplaywin_main_agents')
LIVE_REVENUE = Path('/home/zomorod2/mojplaywin.com/mpw-editorial/revenue')
LEADS = PRIVATE / 'revenue-inquiries'
METRICS = PRIVATE / 'revenue-metrics'
SLUGS = ('website-doctor', 'landing-page-studio', 'ai-automation',
         'business-spreadsheets', 'website-templates', 'social-media-kits',
         'resume-builder', 'logo-studio', 'browser-games', 'marketing-ai',
         'business-calculators', 'website-care')
EVENTS = ('quote_click', 'tool_generated', 'game_interacted', 'inquiry_submitted')
MONTHS = ('2026-10', '2026-11')


def safe_private(path: Path) -> bool:
    if path.is_symlink():
        raise RuntimeError('Unsafe symlink ' + path.name)
    if not path.exists():
        return False
    st = path.stat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.geteuid():
        raise RuntimeError('Unexpected private directory ' + path.name)
    if stat.S_IMODE(st.st_mode) & 0o077:
        raise RuntimeError('Private data directory permissions too broad')
    return True


def main() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('Wrong hosting identity')
    if not safe_private(PRIVATE):
        print('REVENUE_PRIVATE_STORAGE=ABSENT')
        return
    if safe_private(LEADS):
        by_month = Counter()
        other = 0
        for entry in LEADS.iterdir():
            if entry.name == '.inquiry-key':
                continue  # Never open or inspect encryption keys.
            if re.fullmatch(r'20[0-9]{6}-[0-9A-F]{18}\.json', entry.name):
                if entry.is_symlink() or not entry.is_file():
                    raise RuntimeError('Unexpected encrypted inquiry record type')
                by_month[entry.name[:6]] += 1
            elif not entry.name.startswith('.'):
                other += 1
        print('ENCRYPTED_INQUIRIES_TOTAL', sum(by_month.values()))
        for month in MONTHS:
            print('ENCRYPTED_INQUIRIES_MONTH', month, by_month.get(month.replace('-', ''), 0))
        print('UNCLASSIFIED_PRIVATE_ENTRY_COUNT', other)
    else:
        print('ENCRYPTED_INQUIRIES_DIR=ABSENT')

    if safe_private(METRICS):
        for month in MONTHS:
            path = METRICS / (month + '.json')
            if path.is_symlink():
                raise RuntimeError('Metric file symlink')
            if not path.exists():
                print('AGGREGATE_EVENTS_MONTH', month, 'ABSENT')
                continue
            st = path.stat()
            if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.geteuid() or
                    stat.S_IMODE(st.st_mode) & 0o077 or st.st_size > 40000):
                raise RuntimeError('Unexpected aggregate metric file')
            data = json.loads(path.read_text('utf-8'))
            if not isinstance(data, dict) or any(
                    not isinstance(k, str) or not isinstance(v, int) or v < 0
                    for k, v in data.items()):
                raise RuntimeError('Unexpected aggregate metric schema')
            print('AGGREGATE_EVENTS_MONTH', month, 'TOTAL', sum(data.values()))
            for event in EVENTS:
                count = sum(data.get(slug + ':' + event, 0) for slug in SLUGS)
                print('EVENT', month, event, count)
            print('UNKNOWN_METRIC_KEYS_COUNT', month,
                  sum(1 for key in data if key not in
                      {slug + ':' + event for slug in SLUGS for event in EVENTS}))
    else:
        print('AGGREGATE_METRICS_DIR=ABSENT')
    for filename in ('inquiry.php', 'metrics.php'):
        path = LIVE_REVENUE / filename
        if not path.is_file() or path.is_symlink() or path.stat().st_uid != os.geteuid():
            raise RuntimeError('Live PHP route missing or unsafe: ' + filename)
        blob = path.read_bytes()
        if not 200 < len(blob) < 35000:
            raise RuntimeError('Unexpected live PHP size')
        print('REVENUE_PHP_FILE', filename, 'SHA256', hashlib.sha256(blob).hexdigest(),
              'BYTES', len(blob))
        if filename == 'inquiry.php':
            print('INQUIRY_TRACKING_PIXEL', blob.count(b'event=inquiry_submitted'))
            print('INQUIRY_LIMIT_GUARD_REPAIRED',
                  b"if ((int)($_SERVER['CONTENT_LENGTH']??0)>12000)" in blob)
        else:
            print('PIXEL_GENERAL_ALLOWLIST', b"'general'" in blob)
    print('MPW_REVENUE_AGGREGATE_READ_ONLY=PASS')


if __name__ == '__main__':
    main()
