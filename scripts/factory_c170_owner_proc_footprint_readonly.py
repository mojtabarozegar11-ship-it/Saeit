#!/usr/bin/env python3
"""Bounded /proc owner-only Passenger/Python footprint. No cmdline/environ/SQL/data reads.

A process cwd is only a clue; it does NOT establish live DB identity, uptime,
executed WSGI code, successful application startup, or media completeness.
"""
from __future__ import annotations
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import stat

OWNER = 'zomorod2'
HOME = PurePosixPath('/home/zomorod2')
STAGING = HOME / 'Saeit-staging'
WEBROOT = HOME / 'mojplaywin.com'
MAX_PROC_ENTRIES = 16384
MAX_OWNER_PROCS = 512
MAX_COMM = 64
PREFIX = 'FACTORY_C170_PROC_FOOTPRINT_READONLY='


def _in_path(p, base):
    return p == base or base in p.parents


def _process_type(raw):
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_COMM:
        return 'unknown'
    try:
        name = raw.decode('utf-8').strip().casefold()
    except UnicodeError:
        return 'unknown'
    if name.startswith('passenger') or name.startswith('app:'):
        return 'passenger_like'
    if name in ('python', 'python3', 'python3.8', 'python3.9', 'python3.10', 'python3.11'):
        return 'python_like'
    return 'other'


def _cwd_class(link):
    if type(link) is not str or not link.startswith('/') or len(link) > 2048:
        return 'unverified'
    # Do not resolve any filesystem path or follow symlinks.
    pure = PurePosixPath(link)
    if '..' in pure.parts:
        return 'unverified'
    if _in_path(pure, STAGING):
        return 'staging_cwd_hint'
    if _in_path(pure, WEBROOT):
        return 'webroot_cwd_hint'
    if _in_path(pure, HOME):
        return 'other_owner_cwd_hint'
    return 'outside_owner_home_cwd_hint'


def _report_stub():
    return {
        'schema': 'factory.cpanel.owner-proc-footprint.readonly.c170.v1',
        'read_only': True,
        'owner_verified': False,
        'scan_completed': False,
        'candidate_processes_observed': 0,
        'candidate_staging_cwd_hints': 0,
        'candidate_webroot_cwd_hints': 0,
        'candidate_other_cwd_hints': 0,
        'candidate_cwd_unverified': 0,
        'process_limit_exceeded': False,
        'proc_scan_limit_exceeded': False,
        'proc_error_occurred': False,
        'customer_contents_read': False,
        'cmdline_read': False,
        'environ_read': False,
        'mysql_connected': False,
        'passenger_live_db_identity_proven': False,
        'worker_code_identity_proven': False,
        'complete_media_scope_proven': False,
        'backup_created': False,
        'production_modified': False,
    }


def scan(proc_root=Path('/proc'), uid=None):
    out = _report_stub()
    if uid is None:
        try:
            uid = os.geteuid()
            if pwd.getpwuid(uid).pw_name != OWNER:
                return out
        except (KeyError, OSError):
            return out
    out['owner_verified'] = True
    try:
        seen = 0
        owned = 0
        with os.scandir(str(proc_root)) as entries:
            for de in entries:
                seen += 1
                if seen > MAX_PROC_ENTRIES:
                    out['proc_scan_limit_exceeded'] = True
                    return out
                if not de.name.isdecimal() or len(de.name) > 12:
                    continue
                base = proc_root / de.name
                try:
                    st = base.stat(follow_symlinks=False)
                    if not stat.S_ISDIR(st.st_mode) or st.st_uid != uid:
                        continue
                    owned += 1
                    if owned > MAX_OWNER_PROCS:
                        out['process_limit_exceeded'] = True
                        return out
                    with (base / 'comm').open('rb') as fh:
                        raw = fh.read(MAX_COMM + 1)
                    kind = _process_type(raw)
                    if kind not in ('passenger_like', 'python_like'):
                        continue
                    out['candidate_processes_observed'] += 1
                    cwd_kind = _cwd_class(os.readlink(str(base / 'cwd')))
                    if cwd_kind == 'staging_cwd_hint':
                        out['candidate_staging_cwd_hints'] += 1
                    elif cwd_kind == 'webroot_cwd_hint':
                        out['candidate_webroot_cwd_hints'] += 1
                    elif cwd_kind == 'unverified':
                        out['candidate_cwd_unverified'] += 1
                    else:
                        out['candidate_other_cwd_hints'] += 1
                except (FileNotFoundError, PermissionError, ProcessLookupError):
                    # Process exited while being observed: never infer identity.
                    continue
                except OSError:
                    out['proc_error_occurred'] = True
        out['scan_completed'] = True
    except OSError:
        out['proc_error_occurred'] = True
    return out


if __name__ == '__main__':
    print(PREFIX + json.dumps(scan(), sort_keys=True, separators=(',', ':')))
