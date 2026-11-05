#!/usr/bin/env python3
"""Initialize only the proven-empty primary SQLite schema after a private backup.

This never reads, writes, migrates or reconnects the staging MariaDB or MPW DB.
"""

from __future__ import annotations

import fcntl
import hashlib
import io
import json
import os
import pwd
import shutil
import sys
from pathlib import Path


HOME = Path('/home/zomorod2')
APP = HOME / 'Saeit'
DB = APP / 'db.sqlite3'
BACKUP_ROOT = HOME / '.private/newsletter-db-backups'
EMPTY_SHA = hashlib.sha256(b'').hexdigest()
EXPECTED_NEWSLETTER_TABLES = {
    'core_newsletterstory', 'core_newslettersource',
    'core_newsletterpublication', 'core_newsletterschedule',
}


def django_ready():
    if pwd.getpwuid(os.geteuid()).pw_name != 'zomorod2':
        raise RuntimeError('CPANEL_USER_MISMATCH')
    if APP.is_symlink() or not APP.is_dir() or DB.is_symlink() or not DB.is_file():
        raise RuntimeError('PRIMARY_APP_OR_DB_MISSING_OR_SYMLINK')
    if DB.stat().st_size != 0 or hashlib.sha256(DB.read_bytes()).hexdigest() != EMPTY_SHA:
        raise RuntimeError('PRIMARY_DATABASE_CHANGED_FROM_VERIFIED_EMPTY_STATE')
    for suffix in ('-wal', '-shm', '-journal'):
        if Path(str(DB) + suffix).exists():
            raise RuntimeError('PRIMARY_SQLITE_HAS_ACTIVE_JOURNAL')
    os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
    os.chdir(APP)
    sys.path.insert(0, str(APP))
    import django
    django.setup()
    from django.conf import settings
    from django.db import connection
    from django.db.migrations.loader import MigrationLoader
    if connection.vendor != 'sqlite' or Path(str(connection.settings_dict['NAME'])) != DB:
        raise RuntimeError('PRIMARY_SQLITE_TARGET_MISMATCH')
    if settings.DEBUG or 'zomorodmelal.ir' not in settings.ALLOWED_HOSTS:
        raise RuntimeError('UNEXPECTED_PRIMARY_SETTINGS')
    if connection.introspection.table_names():
        raise RuntimeError('PRIMARY_DATABASE_ALREADY_HAS_TABLES')
    loader = MigrationLoader(connection)
    pending = sorted(set(loader.disk_migrations).difference(loader.applied_migrations))
    if len(pending) != 21:
        raise RuntimeError('MIGRATION_PLAN_CHANGED')
    return connection, pending


def preview() -> None:
    connection, pending = django_ready()
    print('ZM_PRIMARY_SCHEMA_PREVIEW=' + json.dumps({
        'database': str(DB.relative_to(HOME)), 'database_initial_bytes': 0,
        'existing_tables': 0, 'pending_builtin_migrations': len(pending),
        'operation': 'migrate_run_syncdb',
        'newsletter_tables_required': sorted(EXPECTED_NEWSLETTER_TABLES),
        'staging_mariadb_accessed': False, 'payment_database_accessed': False}))


def publish(run: str) -> None:
    if not run.isascii() or not run.isdecimal() or not (9 <= len(run) <= 20):
        raise RuntimeError('INVALID_RELEASE_ID')
    os.umask(0o077)
    if not BACKUP_ROOT.parent.is_dir() or BACKUP_ROOT.parent.is_symlink():
        raise RuntimeError('PRIVATE_BACKUP_BASE_MISSING')
    BACKUP_ROOT.mkdir(mode=0o700, exist_ok=True)
    lock = BACKUP_ROOT / '.primary-schema-repair.lock'
    with lock.open('a+b') as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        connection, pending = django_ready()
        folder = BACKUP_ROOT / ('run-' + run)
        if folder.exists() or folder.is_symlink():
            raise RuntimeError('RELEASE_BACKUP_COLLISION')
        folder.mkdir(mode=0o700)
        original = folder / 'original-db.sqlite3'
        with DB.open('rb') as source, original.open('xb') as dest:
            os.fchmod(dest.fileno(), 0o600)
            shutil.copyfileobj(source, dest)
            dest.flush()
            os.fsync(dest.fileno())
        if original.stat().st_size != 0 or DB.stat().st_size != 0:
            raise RuntimeError('EMPTY_DATABASE_PRECONDITION_CHANGED')
        manifest = folder / 'manifest.json'
        with manifest.open('x') as output:
            os.fchmod(output.fileno(), 0o600)
            json.dump({'run': run, 'db': str(DB), 'initial_sha256': EMPTY_SHA,
                       'original_bytes': 0, 'pending_migrations': len(pending)}, output)
            output.flush()
            os.fsync(output.fileno())
        print('ZM_PRIMARY_SCHEMA_PRIVATE_BACKUP_VERIFIED=' + str(folder))
        from django.core.management import call_command
        try:
            call_command('migrate', run_syncdb=True, interactive=False, verbosity=0,
                         stdout=io.StringIO(), stderr=io.StringIO())
        except BaseException as exc:
            raise RuntimeError('SCHEMA_MIGRATION_FAILED_' + type(exc).__name__) from None
        from django.test import Client
        tables = set(connection.introspection.table_names())
        if not EXPECTED_NEWSLETTER_TABLES.issubset(tables):
            raise RuntimeError('NEWSLETTER_TABLES_MISSING_AFTER_MIGRATION')
        with connection.cursor() as cursor:
            cursor.execute('PRAGMA integrity_check')
            integrity = cursor.fetchone()[0]
        if integrity != 'ok':
            raise RuntimeError('POSTMIGRATION_SQLITE_INTEGRITY_FAILED')
        try:
            response = Client(raise_request_exception=True).get(
                '/newsletter/', secure=True, HTTP_HOST='zomorodmelal.ir')
        except BaseException as exc:
            raise RuntimeError('NEWSLETTER_VIEW_AFTER_MIGRATION_' + type(exc).__name__) from None
        if response.status_code != 200:
            raise RuntimeError('NEWSLETTER_NOT_HTTP_200_IN_DJANGO')
        print('ZM_PRIMARY_SCHEMA_PUBLISHED=' + json.dumps({
            'database': str(DB.relative_to(HOME)),
            'migration_backup_private': True,
            'tables_after': len(tables),
            'newsletter_tables': len(EXPECTED_NEWSLETTER_TABLES),
            'newsletter_django_status': response.status_code,
            'sqlite_integrity': 'ok', 'staging_or_payments_touched': False}))


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'preview':
        preview()
    elif len(sys.argv) == 3 and sys.argv[1] == 'publish':
        publish(sys.argv[2])
    else:
        raise SystemExit('USAGE: preview | publish RUN_ID')
