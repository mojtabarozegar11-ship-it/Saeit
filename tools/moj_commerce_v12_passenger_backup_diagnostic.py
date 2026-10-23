#!/usr/bin/env python3
"""Privacy-preserving, read-only preflight of MojPlayWin Passenger/backup metadata.

passenger: inspect fixed, approved deployment-source and cPanel metadata only.
archive: consume an independently authenticated backup TAR from stdin and
         classify entries/links WITHOUT extraction, writes, filenames or PII.
Never output full paths, symlink destinations, env vars, URLs or SQL content.
This diagnostic does not replace an isolated restoration.
"""
from __future__ import annotations
import json
import os
import posixpath
import re
import sys
import tarfile
from pathlib import Path, PurePosixPath

ROOT = Path('/home/zomorod2')
APP = ROOT / 'Saeit-staging'
LIVE = ROOT / 'Saeit'
DOC = ROOT / 'mojplaywin.com'
ALLOWED = {'Saeit-staging', 'mojplaywin.com'}
MAX_ENTRIES = 150000
MAX_BYTES = 10 * 1024**3


def passenger():
    report = {
        'classification': 'MOJ_COMMERCE_V12_PASSENGER_SOURCE_READ_ONLY',
        'public_docroot_exists': DOC.is_dir() and not DOC.is_symlink(),
        'expected_staging_root_exists': APP.is_dir() and not APP.is_symlink(),
        'expected_live_root_exists': LIVE.is_dir() and not LIVE.is_symlink(),
        'passenger_htaccess_present': False,
        'passenger_wsgi_entrypoint_present': False,
        'htaccess_passenger_directives': False,
        'entrypoint_staging_reference': False,
        'entrypoint_live_reference': False,
        'public_route_moj_commerce_mount_found': False,
        'passenger_worker_environment_proven': False,
        'passenger_runtime_database_proven': False,
        'production_writes': False,
        'release_permitted': False,
    }
    ht = DOC / '.htaccess'
    try:
        if ht.is_file() and not ht.is_symlink() and ht.stat().st_size < 150000:
            text = ht.read_text('utf8', errors='replace')
            report['passenger_htaccess_present'] = True
            report['htaccess_passenger_directives'] = bool(re.search(
                r'(?im)^\s*Passenger(?:Enabled|AppRoot|Python|StartupFile|BaseURI)\b', text))
    except OSError:
        pass
    candidates = [DOC / 'passenger_wsgi.py', APP / 'passenger_wsgi.py',
                  LIVE / 'passenger_wsgi.py']
    for p in candidates:
        try:
            if not p.is_file() or p.is_symlink() or p.stat().st_size > 100000:
                continue
            t = p.read_text('utf8', errors='replace')
            report['passenger_wsgi_entrypoint_present'] = True
            report['entrypoint_staging_reference'] |= 'Saeit-staging' in t
            report['entrypoint_live_reference'] |= bool(
                re.search(r'Saeit(?!-staging)', t))
        except OSError:
            continue
    # Look at root URL config source only; no Django initialization.
    for u in (APP / 'config/urls.py', LIVE / 'config/urls.py'):
        try:
            if not u.is_file() or u.is_symlink() or u.stat().st_size > 300000:
                continue
            t = u.read_text('utf8', errors='replace')
            report['public_route_moj_commerce_mount_found'] |= (
                'moj_commerce.urls' in t)
        except OSError:
            continue
    return report


def _parts(name):
    if not isinstance(name, str) or not name or name.startswith('/') or name.startswith('./'):
        return None
    parts = PurePosixPath(name).parts
    if not parts or parts[0] not in ALLOWED or any(x in ('..', '') for x in parts):
        return None
    return parts


def classify_absolute_link_target(target):
    """Return an opaque safety class; do not print, follow or resolve target."""
    if not isinstance(target, str) or not target.startswith('/'):
        raise ValueError('not_an_absolute_target')
    prefix = '/home/zomorod2/'
    if target.startswith(prefix):
        within = target[len(prefix):]
        if _parts(within) is not None:
            return 'within_archive_roots'
    # Owned-but-unbacked paths must stay quarantined until separately recovered.
    if target.startswith('/home/zomorod2/'):
        return 'tenant_unbacked'
    if target.startswith('/home/'):
        return 'other_account_home'
    # Deployment interpreter / system environment is NOT part of the archive.
    if target.startswith(('/opt/alt/', '/usr/', '/bin/', '/lib/', '/lib64/')):
        return 'runtime_dependency'
    return 'external_other'


def classify_tenant_link_family(target):
    """Opaque category only, never raw target path."""
    if target == '/home/zomorod2/Saeit' or target.startswith('/home/zomorod2/Saeit/'):
        return 'production_source'
    if target.startswith(('/home/zomorod2/virtualenv/',
                          '/home/zomorod2/nodevenv/',
                          '/home/zomorod2/.local/')):
        return 'private_runtime'
    if target.startswith(('/home/zomorod2/public_html/',
                          '/home/zomorod2/www/')):
        return 'public_assets'
    return 'other_tenant'


def classify_archive(stream):
    count = {'directories': 0, 'regular_files': 0, 'symlinks': 0,
             'hardlinks': 0, 'unsafe_member_paths': 0, 'duplicate_paths': 0,
             'absolute_link_targets': 0, 'absolute_within_archive_roots': 0,
             'absolute_runtime_dependency': 0, 'absolute_external_other': 0,
             'absolute_tenant_unbacked': 0, 'absolute_other_account_home': 0,
             'tenant_production_source': 0, 'tenant_private_runtime': 0,
             'tenant_public_assets': 0, 'tenant_other_tenant': 0,
             'relative_link_escape': 0,
             'missing_hardlink_targets': 0, 'nested_link_targets': 0,
             'special_members': 0, 'file_bytes_total': 0,
             'too_many_entries': False, 'too_many_file_bytes': False}
    members = set()
    links = []
    roots = set()
    symlink_names = set()
    files = set()
    dirs = set()
    with tarfile.open(fileobj=stream, mode='r|') as tar:
        for member in tar:
            if len(members) >= MAX_ENTRIES:
                count['too_many_entries'] = True
                break
            p = _parts(member.name)
            if p is None:
                count['unsafe_member_paths'] += 1
                continue
            roots.add(p[0])
            normalized = '/'.join(p)
            if normalized in members:
                count['duplicate_paths'] += 1
            members.add(normalized)
            if member.isdir():
                dirs.add(normalized)
                count['directories'] += 1
            elif member.isfile():
                files.add(normalized)
                count['regular_files'] += 1
                count['file_bytes_total'] += member.size
                if count['file_bytes_total'] > MAX_BYTES:
                    count['too_many_file_bytes'] = True
            elif member.issym():
                count['symlinks'] += 1
                symlink_names.add(normalized)
                links.append((normalized, p, member.linkname, True))
            elif member.islnk():
                count['hardlinks'] += 1
                links.append((normalized, p, member.linkname, False))
            else:
                count['special_members'] += 1
    # A TAR file's final source-authentication footer is not an archive member.
    while stream.read(131072):
        pass
    for _, parts, target, sym in links:
        if not isinstance(target, str) or target.startswith('/'):
            count['absolute_link_targets'] += 1
            bucket = (classify_absolute_link_target(target) if isinstance(target, str)
                      and target.startswith('/') else 'external_other')
            count['absolute_' + bucket] += 1
            if bucket == 'tenant_unbacked':
                count['tenant_' + classify_tenant_link_family(target)] += 1
            continue
        candidate = (posixpath.normpath(posixpath.join(*parts[:-1], target))
                     if sym else posixpath.normpath(target))
        if _parts(candidate) is None:
            count['relative_link_escape'] += 1
        elif candidate in symlink_names:
            count['nested_link_targets'] += 1
        elif not sym and candidate not in files:
            count['missing_hardlink_targets'] += 1
    return {
        'classification': 'MOJ_COMMERCE_V12_BACKUP_TAR_METADATA_ONLY',
        'stream_consumed_without_extraction': True,
        'source_roots_present': sorted(roots) == sorted(ALLOWED),
        'archive_contains_regular_files': count['regular_files'] > 0,
        'counters': count,
        'archive_restored': False,
        'full_backup_recovery_verified': False,
        'production_writes': False,
        'release_permitted': False,
    }


if __name__ == '__main__':
    try:
        mode = sys.argv[1] if len(sys.argv) == 2 else ''
        if mode == 'passenger':
            result = passenger()
        elif mode == 'archive':
            result = classify_archive(sys.stdin.buffer)
        else:
            raise ValueError('mode')
        print(json.dumps(result, sort_keys=True))
    except Exception:
        print(json.dumps({'classification': 'MOJ_COMMERCE_V12_DIAGNOSTIC_UNVERIFIED',
                          'release_permitted': False, 'error': 'SANITIZED_FAILURE'}))
        raise SystemExit(1)
