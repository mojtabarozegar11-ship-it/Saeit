#!/usr/bin/env python3
"""Read-only, sanitized structure audit for existing ask-master PHP form.

Never reads customer records, databases, private configuration or credentials;
never submits a request or modifies production files.
"""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import sys
from pathlib import Path
from urllib.parse import quote

WEB = Path('/home/zomorod2/public_html')
FORM = WEB / 'ask-master/index.php'
TRACK = WEB / 'ask-master/status.php'
ALLOWED = (FORM, TRACK)
ASK_DIR = WEB / 'ask-master'
SERVICE_TAG = '[SERVICE_INQUIRY]'


def bool_result(name, condition):
    print(name + '=' + ('1' if condition else '0'))


def inspect_flow(form_source, status_source):
    """Inspect source structure only, without opening customer databases or records.

    Keep the output deliberately limited to booleans and counts: PHP files can
    contain configuration details and must never be echoed in CI logs.
    """
    bool_result('FLOW_SERVICE_UI_OPTION', 'value="service_question"' in form_source)
    bool_result('FLOW_SERVICE_TO_QUESTION_MAP', bool(re.search(
        r"\$_POST\s*\[\s*['\"]kind['\"]\s*\]\s*=\s*['\"]question['\"]", form_source)))
    bool_result('FLOW_SERVICE_TAG_AT_INPUT', SERVICE_TAG in form_source)
    bool_result('FLOW_CREATE_SQL', bool(re.search(r'\bINSERT\s+INTO\b', form_source, re.I)))
    bool_result('FLOW_STATUS_POST', "REQUEST_METHOD" in status_source and 'POST' in status_source)
    bool_result('FLOW_STATUS_TICKET_INPUT', bool(re.search(
        r"\$_POST\s*\[\s*['\"]ticket['\"]\s*\]", status_source)))
    bool_result('FLOW_STATUS_EMAIL_INPUT', bool(re.search(
        r"\$_POST\s*\[\s*['\"]email['\"]\s*\]", status_source)))
    bool_result('FLOW_STATUS_SQL_LOOKUP', bool(re.search(r'\bSELECT\b', status_source, re.I)))
    bool_result('FLOW_STATUS_HAS_SERVICE_TAG', SERVICE_TAG in status_source)

    inspected = 0
    readers = 0
    service_readers = 0
    auth_readers = 0
    metrics = 0
    notification = 0
    # The scan is explicitly confined to PHP *source* inside this one module.
    # No DB files, log files, SQLite rows, sessions, or private files are read.
    for path in sorted(ASK_DIR.glob('**/*.php')):
        if path in ALLOWED or path.is_symlink() or not path.is_file():
            continue
        if any(part.startswith('.') for part in path.relative_to(ASK_DIR).parts):
            continue
        if path.stat().st_size > 200000 or inspected >= 80:
            continue
        inspected += 1
        source = path.read_text(encoding='utf-8', errors='replace')
        is_reader = bool(re.search(r'\bSELECT\b', source, re.I) and
                         re.search(r'\b(ticket|question|request|message)\b', source, re.I))
        if is_reader:
            readers += 1
            service_readers += SERVICE_TAG in source
            auth_readers += bool(re.search(r'\b(session_start|password_verify|hash_equals)\b|\$_SESSION', source))
        metrics += bool(re.search(r'\bCOUNT\s*\(', source, re.I))
        notification += bool(re.search(r'\b(mail|PHPMailer|sendmail|smtp)\s*\(', source, re.I))
    print('FLOW_OTHER_PHP_FILES=' + str(inspected))
    print('FLOW_MANAGEMENT_READER_CANDIDATES=' + str(readers))
    print('FLOW_MANAGEMENT_READERS_WITH_SERVICE_TAG=' + str(service_readers))
    print('FLOW_MANAGEMENT_READERS_WITH_AUTH_HINT=' + str(auth_readers))
    print('FLOW_METRICS_CODE_CANDIDATES=' + str(metrics))
    print('FLOW_NOTIFICATION_CODE_CANDIDATES=' + str(notification))


def inspect_storage_contract(form_source, status_source):
    """Report SQL identifiers and file *basenames*; never read database rows."""
    table_re = re.compile(r'\b(?:CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?|INSERT\s+INTO\s+)([A-Za-z_][A-Za-z_0-9]*)', re.I)
    select_re = re.compile(r'\bFROM\s+([A-Za-z_][A-Za-z_0-9]*)', re.I)
    db_name_re = re.compile(r'([A-Za-z_][A-Za-z_0-9.-]*\.(?:sqlite3?|db))\b', re.I)
    print('CONTRACT_FORM_TABLES=' + ','.join(sorted(set(table_re.findall(form_source))))[:250])
    print('CONTRACT_STATUS_FROM_TABLES=' + ','.join(sorted(set(select_re.findall(status_source))))[:250])
    print('CONTRACT_DB_FILE_BASENAMES=' + ','.join(sorted(set(db_name_re.findall(form_source + status_source))))[:250])
    bool_result('CONTRACT_USES_PDO_SQLITE', 'sqlite:' in form_source or 'sqlite:' in status_source)
    bool_result('CONTRACT_USES_PRIVATE_DIRECTORY', '.private' in form_source)
    bool_result('CONTRACT_STATUS_HAS_TENANT_FILTER', bool(re.search(r'\btenant\b', status_source)))
    bool_result('CONTRACT_STATUS_HAS_EMAIL_FILTER', bool(re.search(r'\bemail\b', status_source)))
    bool_result('CONTRACT_HAS_STATUS_UPDATE', bool(re.search(r'\bUPDATE\s+[A-Za-z_][A-Za-z_0-9]*\s+SET\b', form_source + status_source, re.I)))

    app = Path('/home/zomorod2/.private/zomorod-business/app.php')
    if app.is_file() and not app.is_symlink() and app.stat().st_size < 300000:
        print('CONTRACT_PRIVATE_BUSINESS_APP_SHA256=' + hashlib.sha256(app.read_bytes()).hexdigest())
    else:
        print('CONTRACT_PRIVATE_BUSINESS_APP_UNAVAILABLE=1')


def inspect_request_aggregate():
    """Read count-only aggregates, using an immutable SQLite snapshot.

    Never query a customer row or emit names, emails, tickets, messages, or
    database paths. Avoid reporting possibly stale counts when WAL is active.
    """
    private = Path('/home/zomorod2/.private')
    if not private.is_dir() or private.is_symlink():
        print('AGGREGATE_PRIVATE_DIR_UNAVAILABLE=1')
        return
    candidates = [p for p in private.rglob('master_customer_inbox.sqlite3')
                  if p.is_file() and not p.is_symlink()]
    print('AGGREGATE_DB_CANDIDATE_COUNT=' + str(len(candidates)))
    if len(candidates) != 1:
        return
    path = candidates[0]
    if not path.resolve().is_relative_to(private.resolve()):
        raise RuntimeError('REQUEST_DB_OUTSIDE_PRIVATE_DIRECTORY')
    wal = Path(str(path) + '-wal')
    wal_live = wal.is_file() and wal.stat().st_size > 0
    bool_result('AGGREGATE_WAL_PRESENT', wal_live)
    # immutable=1 prevents both write operations and SQLite shared-memory
    # creation. With a live WAL it may omit recent commits, so do not assert
    # exact counts from such a snapshot.
    uri = 'file:' + quote(str(path), safe='/') + '?mode=ro&immutable=1'
    with sqlite3.connect(uri, uri=True, timeout=2) as db:
        db.execute('PRAGMA query_only=ON')
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for name in ('customer_questions', 'customer_operator_replies', 'customer_order_events'):
            bool_result('AGGREGATE_TABLE_' + name.upper(), name in tables)
        if wal_live or 'customer_questions' not in tables:
            print('AGGREGATE_COUNTS_DEFERRED=1')
            return
        columns = {row[1] for row in db.execute('PRAGMA table_info(customer_questions)')}
        print('AGGREGATE_SCHEMA_COLUMNS=' + ','.join(sorted(columns))[:400])
        if not {'tenant', 'kind'} <= columns:
            print('AGGREGATE_UNEXPECTED_SCHEMA=1')
            return
        count = db.execute('SELECT COUNT(*) FROM customer_questions WHERE tenant=?', ('zomorod',)).fetchone()[0]
        print('AGGREGATE_ZOMOROD_REQUESTS=' + str(count))
        candidates = ('message', 'user_message', 'question', 'question_text',
                      'request_text', 'body', 'prompt', 'content', 'text', 'details')
        text_column = next((x for x in candidates if x in columns), None)
        if text_column is None:
            print('AGGREGATE_SERVICE_TEXT_COLUMN_UNKNOWN=1')
            return
        prefix = SERVICE_TAG + ' '
        # SQL identifier comes only from the fixed whitelist and PRAGMA schema.
        service = db.execute(
            f'SELECT COUNT(*) FROM customer_questions WHERE tenant=? AND kind=? AND substr("{text_column}",1,length(?))=?',
            ('zomorod', 'question', prefix, prefix)).fetchone()[0]
        print('AGGREGATE_ZOMOROD_SERVICE_REQUESTS=' + str(service))


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


def safe_flow_excerpt(source):
    lines = source.splitlines()
    forbidden = re.compile(r'(?i)(password|secret|token|api[_-]?key|smtp|dsn|credential|authorization|private[_-]?key|\$db|\$pdo|\$mysqli)')
    selected = list(range(112, 146)) + list(range(153, 165))
    for number in selected:
        if number > len(lines):
            continue
        line = lines[number - 1].strip()
        if not line or len(line) > 270 or forbidden.search(line):
            continue
        print('SAFE_FLOW_LINE_' + str(number) + '=' + repr(line))


def audit():
    if os.geteuid() == 0 or os.geteuid() != WEB.stat().st_uid:
        raise RuntimeError('REFUSE_WRONG_SITE_USER')
    sources = {}
    for path in ALLOWED:
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('UNSAFE_OR_MISSING_PHP_FILE:' + str(path))
        if path.stat().st_size > 200000:
            raise RuntimeError('UNEXPECTED_SOURCE_SIZE:' + str(path))
        source = path.read_text(encoding='utf-8', errors='replace')
        sources[path] = source
        print('FILE=' + str(path.relative_to(WEB)))
        print('BYTES=' + str(path.stat().st_size))
        print('SHA256=' + hashlib.sha256(path.read_bytes()).hexdigest())
        if path == FORM:
            print('HAS_KIND_POST=' + str(bool(re.search(r"\$_POST\s*\[\s*['\"]kind['\"]\s*\]", source))))
            print('HAS_KIND_FORM=' + str('name="kind"' in source or "name='kind'" in source))
            print('HAS_KIND_ENFORCEMENT=' + str(bool(re.search(r'(?i)(in_array|array_search|match|switch).*kind|kind.*(in_array|array_search|match|switch)', source))))
            print('HAS_INSERT=' + str(bool(re.search(r'(?i)\bINSERT\s+INTO\b', source))))
            print('HAS_REQUIRE=' + str(bool(re.search(r'(?i)\b(require|include)(_once)?\b', source))))
            print('HAS_STRICT_TYPES=' + str('declare(strict_types=1);' in source))
            safe_lines(source)
            safe_flow_excerpt(source)
        else:
            print('TRACK_HAS_TICKET_FIELD=' + str('name="ticket"' in source))
            print('TRACK_HAS_EMAIL_FIELD=' + str('name="email"' in source))
    inspect_flow(sources[FORM], sources[TRACK])
    inspect_storage_contract(sources[FORM], sources[TRACK])
    inspect_request_aggregate()


if __name__ == '__main__':
    if sys.argv[1:] == ['origin']:
        audit()
    elif sys.argv[1:] == ['selftest']:
        assert list(ALLOWED) == [FORM, TRACK]
        assert ASK_DIR == FORM.parent == TRACK.parent
        assert SERVICE_TAG.startswith('[') and SERVICE_TAG.endswith(']')
        print('ASK_MASTER_READONLY_SELFTEST_OK=1')
    else:
        raise RuntimeError('UNKNOWN_OR_UNSAFE_MODE')
