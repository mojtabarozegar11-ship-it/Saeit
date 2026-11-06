#!/usr/bin/env python3
"""Private, non-mutating audit of Zomorod inquiry triage readiness.

Outputs only booleans, column names and aggregate counts. No customer rows,
credentials, logs, email addresses, tickets or request text are printed.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote


HOME = Path('/home/zomorod2')
WEB = HOME / 'public_html'
PRIVATE = HOME / '.private/zomorod-business'
APP = PRIVATE / 'app.php'
MANAGEMENT_DB = PRIVATE / 'management.sqlite3'
SOURCE_POINTER = PRIVATE / 'service_inquiries_source.path'
PUBLIC_INBOX = WEB / 'business/inquiries.php'
PRIVATE_INBOX = PRIVATE / 'service_inquiries.php'
STATUS = WEB / 'ask-master/status.php'
FORM = WEB / 'ask-master/index.php'


def emit(name: str, value: object) -> None:
    print(name + '=' + str(int(value) if isinstance(value, bool) else value))


def ensure_site_user() -> None:
    if os.geteuid() == 0 or os.geteuid() != WEB.stat().st_uid:
        raise RuntimeError('REFUSE_WRONG_SITE_USER')


def source(path: Path) -> str:
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(HOME):
        raise RuntimeError('REFUSE_UNEXPECTED_SOURCE')
    if not (100 <= path.stat().st_size <= 300000):
        raise RuntimeError('REFUSE_UNEXPECTED_SOURCE_SIZE')
    return path.read_text(encoding='utf-8', errors='replace')


def source_audit() -> None:
    app = source(APP)
    inbox = source(PRIVATE_INBOX)
    status = source(STATUS)
    form = source(FORM)
    wrapper = source(PUBLIC_INBOX)
    emit('MANAGER_APP_FINGERPRINT', hashlib.sha256(APP.read_bytes()).hexdigest())
    emit('MANAGER_COOKIE_NAME_MATCH', bool(re.search(r"session_name\(\s*['\"]ZM_BUSINESS['\"]", app)) and
         bool(re.search(r"session_name\(\s*['\"]ZM_BUSINESS['\"]", inbox)))
    emit('MANAGER_SESSION_UID_IN_APP', "$_SESSION['uid']" in app)
    emit('MANAGER_SESSION_UID_IN_INBOX', "$_SESSION['uid']" in inbox)
    emit('MANAGER_ROLE_RECHECK', 'SELECT role, active FROM users WHERE id=:uid' in inbox)
    emit('MANAGER_READONLY_INBOX_LINK', '/business/inquiries.php' in app)
    emit('INBOX_CONTENT_IS_PRIVATE', "require" in wrapper and 'service_inquiries.php' in wrapper)
    emit('INBOX_READONLY_SQLITE', 'SQLITE3_OPEN_READONLY' in inbox)
    emit('STATUS_READS_OPERATOR_REPLIES', 'customer_operator_replies' in status)
    emit('STATUS_REQUIRES_EMAIL_AND_TICKET', "$_POST['email']" in status and "$_POST['ticket']" in status)
    emit('FORM_RECOGNIZES_SERVICE_INQUIRY', '[SERVICE_INQUIRY]' in form and 'service_question' in form)
    binary = shutil.which('php') or '/opt/cpanel/ea-php82/root/usr/bin/php'
    for key, path in [('APP', APP), ('INBOX', PRIVATE_INBOX), ('STATUS', STATUS), ('FORM', FORM)]:
        result = subprocess.run([binary, '-l', str(path)], capture_output=True, timeout=20)
        emit('PHP_LINT_' + key, result.returncode == 0)


def open_immutable(path: Path) -> sqlite3.Connection:
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(HOME / '.private'):
        raise RuntimeError('REFUSE_UNEXPECTED_DATABASE')
    uri = 'file:' + quote(str(path), safe='/') + '?mode=ro&immutable=1'
    conn = sqlite3.connect(uri, uri=True, timeout=3)
    conn.execute('PRAGMA query_only=ON')
    return conn


def schema(conn: sqlite3.Connection, table: str) -> list[str]:
    # Only known table identifiers ever reach this query.
    return [row[1] for row in conn.execute('PRAGMA table_info(' + table + ')')]


def inspect_management() -> None:
    if not MANAGEMENT_DB.is_file():
        emit('MANAGEMENT_DATABASE_AVAILABLE', False)
        return
    emit('MANAGEMENT_DATABASE_AVAILABLE', True)
    with open_immutable(MANAGEMENT_DB) as db:
        cols = schema(db, 'users')
        emit('MANAGEMENT_USERS_SCHEMA_VALID', {'id', 'role', 'active'} <= set(cols))
        if {'id', 'role', 'active'} <= set(cols):
            wal = Path(str(MANAGEMENT_DB) + '-wal')
            if wal.is_file() and wal.stat().st_size > 0:
                emit('MANAGEMENT_STAFF_COUNTS_DEFERRED_WAL', True)
            else:
                # An aggregate count contains no identities or credentials.
                count = db.execute("SELECT COUNT(*) FROM users WHERE active=1 AND role IN ('admin','manager')").fetchone()[0]
                emit('MANAGEMENT_ACTIVE_INQUIRY_MANAGERS', count)


def inspect_customer_inbox() -> None:
    if SOURCE_POINTER.is_symlink() or not SOURCE_POINTER.is_file():
        emit('CUSTOMER_INBOX_POINTER_AVAILABLE', False)
        return
    path = Path(SOURCE_POINTER.read_text(encoding='utf-8').strip())
    if path.name != 'master_customer_inbox.sqlite3' or not path.resolve().is_relative_to(HOME / '.private'):
        raise RuntimeError('REFUSE_UNEXPECTED_CUSTOMER_DATABASE_POINTER')
    emit('CUSTOMER_INBOX_POINTER_AVAILABLE', True)
    with open_immutable(path) as db:
        questions = schema(db, 'customer_questions')
        replies = schema(db, 'customer_operator_replies')
        emit('CUSTOMER_QUESTION_COLUMNS', ','.join(sorted(questions)))
        emit('CUSTOMER_REPLY_COLUMNS', ','.join(sorted(replies)))
        emit('CUSTOMER_QUESTION_SCHEMA_VALID', {'tenant', 'kind', 'question', 'id'} <= set(questions))
        emit('CUSTOMER_REPLY_TABLE_AVAILABLE', bool(replies))
        wal = Path(str(path) + '-wal')
        if wal.is_file() and wal.stat().st_size > 0:
            emit('CUSTOMER_COUNT_DEFERRED_WAL', True)
            return
        if {'tenant', 'kind', 'question', 'id'} <= set(questions):
            total, service = db.execute(
                "SELECT COUNT(*),SUM(CASE WHEN kind='question' AND substr(question,1,length(?))=? THEN 1 ELSE 0 END) "
                'FROM customer_questions WHERE tenant=?',
                ('[SERVICE_INQUIRY] ', '[SERVICE_INQUIRY] ', 'zomorod'),
            ).fetchone()
            emit('CUSTOMER_ZOMOROD_TOTAL_INQUIRIES', int(total or 0))
            emit('CUSTOMER_ZOMOROD_SERVICE_INQUIRIES', int(service or 0))


def main() -> None:
    ensure_site_user()
    source_audit()
    inspect_management()
    inspect_customer_inbox()


def selftest() -> None:
    assert APP.parent == PRIVATE and SOURCE_POINTER.parent == PRIVATE
    assert STATUS.parent == FORM.parent
    assert PUBLIC_INBOX.name == 'inquiries.php'
    assert SOURCE_POINTER.name.endswith('.path')
    emit('SERVICE_LIFECYCLE_READONLY_SELFTEST', True)


if __name__ == '__main__':
    if sys.argv[1:] == ['origin']:
        main()
    elif sys.argv[1:] == ['selftest']:
        selftest()
    else:
        raise RuntimeError('UNKNOWN_OR_UNSAFE_MODE')
