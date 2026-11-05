#!/usr/bin/env python3
"""Read-only, sanitized structure audit for existing ask-master PHP form.

Never reads customer records, databases, private configuration or credentials;
never submits a request or modifies production files.
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path

WEB = Path('/home/zomorod2/public_html')
FORM = WEB / 'ask-master/index.php'
TRACK = WEB / 'ask-master/status.php'
ALLOWED = (FORM, TRACK)


def safe_lines(source):
    seen = 0
    forbidden = re.compile(r'(?i)(password|secret|token|api[_-]?key|smtp|dsn|credential|authorization|private[_-]?key|\$db|\$pdo|\$mysqli)')
    for index, line in enumerate(source.splitlines(), 1):
        if not re.search(r'(?i)(\bkind\b|\boption\b|\bselect\b|in_array\s*\(|\bgeneral\b|\border\b)', line):
            continue
        if forbidden.search(line):
            continue
        if len(line) > 320 or len(line.strip()) < 3:
            continue
        if seen >= 22:
            break
        line = line.strip()
        # Only show logic and short labels, not values from runtime records.
        print('SAFE_KIND_SOURCE_LINE_' + str(index) + '=' + repr(line))
        seen += 1
    print('SAFE_KIND_LINES_REPORTED=' + str(seen))


def audit():
    if os.geteuid() == 0 or os.geteuid() != WEB.stat().st_uid:
        raise RuntimeError('REFUSE_WRONG_SITE_USER')
    for path in ALLOWED:
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('UNSAFE_OR_MISSING_PHP_FILE:' + str(path))
        if path.stat().st_size > 200000:
            raise RuntimeError('UNEXPECTED_SOURCE_SIZE:' + str(path))
        source = path.read_text(encoding='utf-8', errors='replace')
        print('FILE=' + str(path.relative_to(WEB)))
        print('BYTES=' + str(path.stat().st_size))
        print('SHA256=' + hashlib.sha256(path.read_bytes()).hexdigest())
        if path == FORM:
            print('HAS_KIND_POST=' + str(bool(re.search(r"\$_POST\s*\[\s*['\"]kind['\"]\s*\]", source))))
            print('HAS_KIND_FORM=' + str('name="kind"' in source or "name='kind'" in source))
            print('HAS_KIND_ENFORCEMENT=' + str(bool(re.search(r'(?i)(in_array|array_search|match|switch).*kind|kind.*(in_array|array_search|match|switch)', source))))
            print('HAS_INSERT=' + str(bool(re.search(r'(?i)\bINSERT\s+INTO\b', source))))
            print('HAS_REQUIRE=' + str(bool(re.search(r'(?i)\b(require|include)(_once)?\b', source))))
            safe_lines(source)
        else:
            print('TRACK_HAS_TICKET_FIELD=' + str('name="ticket"' in source))
            print('TRACK_HAS_EMAIL_FIELD=' + str('name="email"' in source))


if __name__ == '__main__':
    if sys.argv[1:] == ['origin']:
        audit()
    elif sys.argv[1:] == ['selftest']:
        assert list(ALLOWED) == [FORM, TRACK]
        print('ASK_MASTER_READONLY_SELFTEST_OK=1')
    else:
        raise RuntimeError('UNKNOWN_OR_UNSAFE_MODE')
