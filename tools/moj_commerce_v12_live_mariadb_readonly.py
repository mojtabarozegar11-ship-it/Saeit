#!/usr/bin/env python3
"""Read-only MojPlayWin MariaDB release preflight on authorized cPanel.

No database modifications, dumps, snapshots, migrations, writes, or restarts.
Reads only explicitly scoped configuration and database metadata. Never prints
or exports DB URL, names, users, passwords, local paths, or connection errors.
A config-file connection is NOT proof of effective Passenger DB settings.
"""
from __future__ import annotations
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit, unquote

ROOT = Path('/home/zomorod2')
CONFIGS = (
    ROOT / 'Saeit-staging/.env',
    ROOT / 'Saeit-staging/.env.production',
    ROOT / 'Saeit/.env',
    ROOT / 'Saeit/.env.production',
    ROOT / 'mojplaywin.com/.env',
)
DB_URL = re.compile(r'^\s*(?:export\s+)?DATABASE_URL\s*=\s*(.*?)\s*$')


def _run(argv, *, env=None, timeout=15, cap=200_000):
    try:
        p = subprocess.run(argv, env=env, stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL, timeout=timeout, check=False)
        return p.stdout if p.returncode == 0 and len(p.stdout) <= cap else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def _url_candidates(paths=CONFIGS):
    urls = []
    for path in paths:
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
                continue
            for line in path.read_text(encoding='utf8', errors='replace').splitlines():
                m = DB_URL.fullmatch(line)
                if m:
                    value = m.group(1).strip().strip('"').strip("'")
                    parsed = urlsplit(value)
                    if parsed.scheme.lower() not in ('mysql', 'mariadb', 'mysql2'):
                        continue
                    if parsed.username and parsed.password and parsed.path.strip('/'):
                        urls.append(parsed)
        except (OSError, ValueError, UnicodeError):
            continue
    return urls


def _uapi_databases():
    data = _run(['uapi', '--output=json', 'Mysql', 'list_databases'], timeout=20)
    try:
        envelope = json.loads(data).get('result', {})
        names = envelope.get('data', [])
        if envelope.get('status') not in (1, '1') or not isinstance(names, list):
            return None
        return {entry['database'] for entry in names
                if isinstance(entry, dict) and isinstance(entry.get('database'), str)}
    except (TypeError, KeyError, ValueError, AttributeError):
        return None


def _mysql_connection(url):
    if not shutil.which('mariadb'):
        return False, None
    name, user = unquote(url.path.lstrip('/')), unquote(url.username or '')
    password = unquote(url.password or '')
    if not name or not user or not password:
        return False, None
    # The only SQL statements are read-only. No table names or rows are logged.
    sql = (
        "START TRANSACTION READ ONLY;"
        "SELECT 1;"
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema=DATABASE() AND table_type='BASE TABLE' "
        "AND engine <> 'InnoDB';"
        "COMMIT"
    )
    argv = ['mariadb', '--no-defaults', '--batch', '--skip-column-names',
            '--connect-timeout=5', '--host='+str(url.hostname or 'localhost'),
            '--user='+user, '--database='+name, '--execute='+sql]
    if url.port is not None:
        argv.append('--port='+str(url.port))
    env = dict(os.environ, MYSQL_PWD=password)
    reply = _run(argv, env=env, timeout=18, cap=256)
    if reply is None:
        return False, None
    try:
        lines = reply.decode('ascii').strip().splitlines()
        if len(lines) != 2 or lines[0] != '1':
            return False, None
        bad_engines = int(lines[1])
        return True, bad_engines if 0 <= bad_engines < 100_000 else None
    except (ValueError, UnicodeError):
        return False, None


def _quota():
    reply = _run(['uapi', '--output=json', 'Quota', 'get_local_quota_info'], timeout=15)
    try:
        env = json.loads(reply).get('result', {})
        values = env.get('data', {}) if env.get('status') in (1, '1') else {}
        used = values.get('bytes_used', values.get('disk_used'))
        limit = values.get('byte_limit', values.get('disk_limit'))
        used, limit = int(used), int(limit)
        return {'quota_measured': True,
                'quota_over_limit': used > limit if limit > 0 else False,
                'quota_has_positive_capacity': limit > used if limit > 0 else False}
    except (ValueError, TypeError, AttributeError):
        return {'quota_measured': False, 'quota_over_limit': None,
                'quota_has_positive_capacity': None}


def inspect():
    urls = _url_candidates()
    databases = _uapi_databases()
    unique = {(u.hostname, unquote(u.path.lstrip('/')), unquote(u.username or ''))
              for u in urls}
    resolved = len(unique) == 1 and len(urls) >= 1
    # If multiple configs point to same endpoint but different passwords,
    # do not attempt to resolve or select a production credential automatically.
    resolved = resolved and len({(u.hostname, u.path, u.username, u.password, u.port)
                                 for u in urls}) == 1
    url = urls[0] if resolved else None
    cpanel_matches = bool(url and databases is not None and
                          unquote(url.path.lstrip('/')) in databases)
    sql_ok, non_innodb_count = _mysql_connection(url) if cpanel_matches else (False, None)
    return {
        'classification': 'MOJ_COMMERCE_V12_PRODUCTION_METADATA_READ_ONLY',
        'cPanel_database_inventory_verified': databases is not None,
        'config_scoped_mysql_url_count': len(urls),
        'config_single_unambiguous_database_url': bool(resolved),
        'config_matches_cpanel_database': cpanel_matches,
        'scoped_mysql_readonly_transaction_ok': sql_ok,
        'non_innodb_base_table_count': non_innodb_count,
        'live_source_moj_commerce_module_present': (ROOT / 'Saeit/moj_commerce/models.py').is_file(),
        'staging_source_moj_commerce_module_present': (ROOT / 'Saeit-staging/moj_commerce/models.py').is_file(),
        'existing_staging_directory': (ROOT / 'Saeit-staging').is_dir(),
        'actual_Passenger_db_runtime_verified': False,
        'full_database_and_media_restore_verified': False,
        'wallet_or_chain_access': False,
        'production_db_writes': False,
        'release_permitted': False,
        'quota': _quota(),
        'limitations': 'A read-only config login is not Passenger runtime attestation or restore proof',
    }


if __name__ == '__main__':
    try:
        print(json.dumps(inspect(), sort_keys=True, separators=(',', ':')))
    except Exception:
        print(json.dumps({'classification': 'MOJ_COMMERCE_V12_AUDIT_UNVERIFIED',
                          'release_permitted': False, 'secrets_printed': False}))
        raise SystemExit(1)
