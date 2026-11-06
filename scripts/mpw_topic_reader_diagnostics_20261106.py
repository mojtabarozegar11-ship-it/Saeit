#!/usr/bin/env python3
"""Read-only source-structure diagnostics for MojPlayWin's 340 public PHP topics.

Never reads passwords, databases or customer data; outputs only schema/layout hints
from the two public PHP route files, not their complete source.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import pwd
import re
import stat


ROOT = Path('/home/zomorod2/mojplaywin.com')
ROUTE = ROOT / 'design-preview-20261017/mpw-site-integrity-20261019/topic.php'
SEARCH = ROOT / 'design-preview-20261017/mpw-site-integrity-20261019/search.php'
RUNTIME = ROOT / '.htaccess'


def main() -> None:
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('wrong hosting user')
    for path in (ROOT, ROUTE, SEARCH, RUNTIME):
        if not path.exists() or path.is_symlink() or path.resolve() != path:
            raise RuntimeError('unexpected route path: ' + path.name)
        if path != ROOT and not stat.S_ISREG(path.stat().st_mode):
            raise RuntimeError('unexpected source type')
    routing = RUNTIME.read_text('utf-8', 'replace')
    if 'mpw-site-integrity-20261019/topic.php' not in routing:
        raise RuntimeError('live topic route changed')
    source = ROUTE.read_text('utf-8', 'replace')
    print('TOPICS_PHP_BYTES', ROUTE.stat().st_size)
    print('TOPICS_PHP_SHA256', hashlib.sha256(source.encode()).hexdigest())
    print('TOPICS_PHP_LINES', source.count('\n') + 1)
    print('TOPICS_SEMANTIC_FUNCTIONS', re.findall(r'function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(', source)[:35])
    snippets = []
    lines = source.splitlines()
    needles = ('This is a topic overview', 'function head_html', 'function safe',
               'topic_id', 'json_decode', 'file_get_contents', 'topics.json',
               '$records', '$topic', 'related section', 'top_nav();', 'footer_html();')
    for i, line in enumerate(lines):
        if not any(needle in line for needle in needles):
            continue
        if any(token in line.lower() for token in ('password', 'secret', 'private_key',
                                                   'credential', 'api_key', 'token=')):
            continue
        # Only short public rendering/schema lines; the report never emits data blobs.
        if len(line) > 420:
            snippets.append((i + 1, '<long-line-omitted>', len(line)))
        else:
            snippets.append((i + 1, line.strip()[:420]))
        if len(snippets) >= 65:
            break
    for row in snippets:
        print('TOPIC_RENDER_LINE', repr(row))
    print('TOPIC_PHP_READ_ONLY=PASS')


if __name__ == '__main__':
    main()
