#!/usr/bin/env python3
"""C171: owner-only cPanel Passenger application registry metadata. NO DATA/SQL.

Runs locally under the pinned cPanel owner via the existing SSH relay.
Never prints raw cPanel JSON; may contain app envvars or private paths.
No login, network, source application imports, database connections or changes.
Registered metadata is NOT proof of a currently active Passenger worker.
"""
from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath
import pwd
import select
import stat
import subprocess
import time

OWNER = 'zomorod2'
HOME = PurePosixPath('/home/zomorod2')
STAGING = HOME / 'Saeit-staging'
WEBROOT = HOME / 'mojplaywin.com'
MAX_JSON_BYTES = 512 * 1024
MAX_APPS = 256
PREFIX = 'FACTORY_C171_PASSENGER_UAPI_READONLY='
UAPI = '/usr/bin/uapi'
UAPI_ARGS = [UAPI, '--output=json', 'PassengerApps', 'list_applications']
TARGETS = {'mojplaywin.com','www.mojplaywin.com',
           'zomorodmelal.ir','www.zomorodmelal.ir'}


def _base():
    return {
        'schema': 'factory.cpanel.passenger-uapi.readonly.c171.v1',
        'read_only': True, 'owner_verified': False,
        'uapi_query_completed': False, 'registry_status': 'not_attempted',
        'registered_apps': 0, 'enabled_apps': 0,
        'staging_app_roots': 0, 'webroot_app_roots': 0,
        'other_owner_app_roots': 0, 'outside_owner_app_roots': 0,
        'unverified_app_roots': 0, 'target_domain_registrations': 0,
        'target_domain_staging_paths': 0,
        'target_domain_webroot_paths': 0,
        'target_domain_other_paths': 0,
        'uapi_response_size_exceeded': False,
        'uapi_timeout': False,
        'registered_metadata_not_runtime_attestation': True,
        'live_passenger_worker_identity_proven': False,
        'live_database_identity_proven': False,
        'complete_media_scope_proven': False,
        'registered_root_census_attempted': False,
        'registered_root_secure_dirs': 0,
        'registered_root_unverified_dirs': 0,
        'registered_root_wsgi_metadata': 0,
        'registered_root_manage_metadata': 0,
        'registered_root_media_metadata': 0,
        'registered_root_uploads_metadata': 0,
        'envvars_output': False, 'file_contents_read': False,
        'mysql_connected': False, 'current_backup_created': False,
        'production_modified': False,
    }


def _pairs_no_dup(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError('DUPLICATE_JSON_KEY')
        out[key] = value
    return out


def _bucket_root(raw):
    if type(raw) is not str or not raw or len(raw) > 2048:
        return 'unverified'
    if raw.startswith('~/'):
        raw = str(HOME) + raw[1:]
    elif not raw.startswith('/'):
        raw = str(HOME) + '/' + raw
    p = PurePosixPath(raw)
    if '..' in p.parts or '\\' in raw or any(ord(c)<32 for c in raw):
        return 'unverified'
    if p == STAGING or STAGING in p.parents:
        return 'staging'
    if p == WEBROOT or WEBROOT in p.parents:
        return 'webroot'
    if p == HOME or HOME in p.parents:
        return 'other_owner'
    return 'outside_owner'


def _app_list(data):
    if type(data) is list:
        return data
    if type(data) is dict:
        return list(data.values())
    return None


def classify_uapi_json(raw: bytes) -> dict:
    """No raw fields escape. Fail closed on malformed/oversized provider output."""
    out = _base()
    if type(raw) is not bytes or not 1 <= len(raw) <= MAX_JSON_BYTES:
        out['registry_status'] = 'response_missing_or_oversize'
        out['uapi_response_size_exceeded'] = type(raw) is bytes and len(raw) > MAX_JSON_BYTES
        return out
    try:
        obj = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs_no_dup)
        if type(obj) is not dict or type(obj.get('result')) is not dict:
            raise ValueError()
        result = obj['result']
        if type(result.get('status')) is not int or result['status'] != 1:
            out['registry_status'] = 'api_unavailable_or_failed'
            return out
        apps = _app_list(result.get('data'))
        if apps is None or len(apps) > MAX_APPS or any(type(x) is not dict for x in apps):
            out['registry_status'] = 'app_list_invalid_or_over_limit'
            return out
        for item in apps:
            domain = item.get('domain')
            path = item.get('path')
            if path is None:
                path = item.get('app_root')
            bucket = _bucket_root(path)
            out['registered_apps'] += 1
            if item.get('enabled') in (1, '1', True):
                out['enabled_apps'] += 1
            out[bucket + '_app_roots'] += 1
            if (type(domain) is str and domain.lower().rstrip('.') in TARGETS):
                out['target_domain_registrations'] += 1
                target_key = ('target_domain_staging_paths' if bucket=='staging'
                              else 'target_domain_webroot_paths' if bucket=='webroot'
                              else 'target_domain_other_paths')
                out[target_key] += 1
        out['uapi_query_completed'] = True
        out['registry_status'] = 'registered_metadata_only'
    except (UnicodeDecodeError, ValueError, TypeError, KeyError, RecursionError):
        out['registry_status'] = 'invalid_provider_response'
    return out


def _safe_owner_root(raw, uid):
    """Resolve only owner-relative registry roots and reject symlink ancestors."""
    if _bucket_root(raw) not in ('staging','webroot','other_owner'):
        return None
    if raw.startswith('~/'):
        absolute = str(HOME) + raw[1:]
    elif raw.startswith('/'):
        absolute = raw
    else:
        absolute = str(HOME) + '/' + raw
    root = Path(absolute)
    if len(root.parts) > 18:
        return None
    home = Path(HOME)
    if root != home and home not in root.parents:
        return None
    current = root
    try:
        while True:
            fs = current.lstat()
            if (not stat.S_ISDIR(fs.st_mode) or fs.st_uid != uid or
                    fs.st_mode & 0o022):
                return None
            if current == home:
                break
            current = current.parent
        return root
    except OSError:
        return None


def _safe_child(root, name, uid, *, directory):
    """Single nonrecursive lstat only; no customer contents opened."""
    try:
        fs = (root / name).lstat()
        if fs.st_uid != uid or fs.st_mode & 0o022:
            return False
        if directory:
            return stat.S_ISDIR(fs.st_mode)
        return stat.S_ISREG(fs.st_mode) and fs.st_nlink == 1
    except OSError:
        return False


def _registered_root_metadata_census(raw, uid):
    """Private cPanel filesystem metadata only; no paths or names returned."""
    result = {
        'registered_root_census_attempted': False,
        'registered_root_secure_dirs': 0,
        'registered_root_unverified_dirs': 0,
        'registered_root_wsgi_metadata': 0,
        'registered_root_manage_metadata': 0,
        'registered_root_media_metadata': 0,
        'registered_root_uploads_metadata': 0,
    }
    try:
        payload = json.loads(raw.decode('utf-8'),object_pairs_hook=_pairs_no_dup)
        obj = payload['result']
        if type(obj) is not dict or type(obj.get('status')) is not int or obj['status'] != 1:
            return result
        apps = _app_list(obj.get('data'))
        if apps is None or len(apps) > MAX_APPS or any(type(x) is not dict for x in apps):
            return result
        result['registered_root_census_attempted'] = True
        for app in apps:
            path = app.get('path')
            if path is None:
                path = app.get('app_root')
            root = _safe_owner_root(path,uid)
            if root is None:
                result['registered_root_unverified_dirs'] += 1
                continue
            result['registered_root_secure_dirs'] += 1
            result['registered_root_wsgi_metadata'] += int(
                _safe_child(root,'passenger_wsgi.py',uid,directory=False))
            result['registered_root_manage_metadata'] += int(
                _safe_child(root,'manage.py',uid,directory=False))
            result['registered_root_media_metadata'] += int(
                _safe_child(root,'media',uid,directory=True))
            result['registered_root_uploads_metadata'] += int(
                _safe_child(root,'uploads',uid,directory=True))
    except (UnicodeDecodeError,ValueError,KeyError,TypeError,RecursionError,OSError):
        result['registered_root_census_attempted'] = False
    return result


def _bounded_run(argv=UAPI_ARGS, *, timeout=25) -> bytes:
    """Only the exact read-only UAPI allowlist; stderr discarded at source."""
    if argv != UAPI_ARGS:
        raise ValueError('UAPI_COMMAND_NOT_ALLOWLISTED')
    if type(timeout) is not int or not 1 <= timeout <= 60:
        raise ValueError('INVALID_TIMEOUT')
    proc = None
    try:
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, close_fds=True)
        end = time.monotonic() + timeout
        parts, seen = [], 0
        while True:
            left = end - time.monotonic()
            if left <= 0:
                raise TimeoutError()
            rd, _, _ = select.select([proc.stdout], [], [], left)
            if not rd:
                raise TimeoutError()
            chunk = os.read(proc.stdout.fileno(),
                            min(65536, MAX_JSON_BYTES + 1 - seen))
            if not chunk:
                if proc.wait(timeout=max(0.001, end - time.monotonic())) != 0:
                    raise OSError('UAPI_FAILED_REDACTED')
                return b''.join(parts)
            seen += len(chunk)
            if seen > MAX_JSON_BYTES:
                raise OverflowError('UAPI_OUTPUT_TOO_LARGE_REDACTED')
            parts.append(chunk)
    finally:
        if proc is not None:
            try:
                if proc.poll() is None:
                    proc.kill()
                proc.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass
            if proc.stdout is not None:
                proc.stdout.close()


def report() -> dict:
    out = _base()
    try:
        uid = os.geteuid()
        if pwd.getpwuid(uid).pw_name != OWNER:
            return out
        out['owner_verified'] = True
        # No root privilege, no customer queries and no provider metadata leak.
        raw = _bounded_run()
        classified = classify_uapi_json(raw)
        classified['owner_verified'] = True
        if classified['uapi_query_completed']:
            classified.update(_registered_root_metadata_census(raw,uid))
        return classified
    except TimeoutError:
        out['owner_verified'] = True
        out['registry_status'] = 'uapi_timeout'
        out['uapi_timeout'] = True
    except OverflowError:
        out['owner_verified'] = True
        out['registry_status'] = 'uapi_output_bounded'
        out['uapi_response_size_exceeded'] = True
    except (OSError, ValueError, subprocess.SubprocessError):
        out['owner_verified'] = True
        out['registry_status'] = 'uapi_unavailable_or_failed'
    return out


if __name__ == '__main__':
    print(PREFIX + json.dumps(report(), sort_keys=True, separators=(',', ':')))
