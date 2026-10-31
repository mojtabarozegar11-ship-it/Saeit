#!/usr/bin/env python3
"""G-01 -> S-01 R57 read-only ZIP integrity gate; never deploys or contacts hosts."""
import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

PREFIX = 'ramadan-war/'
REQUIRED = {'index.html', 'game.js', 'graphics-recovery.mjs',
            'preview-manifest.json', 'R57-MANIFEST-SHA256.json',
            'moj1-commerce-policy.mjs'}

def verify(path, expected_sha=None):
    path = Path(path)
    if not path.is_file():
        return ['MISSING_ARCHIVE']
    if path.stat().st_size > 30_000_000:
        return ['ARCHIVE_TOO_LARGE']
    if expected_sha and hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha:
        return ['ZIP_HASH_MISMATCH']
    issues = []
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) != len({info.filename for info in infos}):
                issues.append('DUPLICATE_ENTRY')
            if sum(info.file_size for info in infos) > 90_000_000:
                issues.append('UNCOMPRESSED_TOO_LARGE')
            for info in infos:
                name = info.filename
                if (not name.startswith(PREFIX) or name.startswith('/')
                        or '..' in PurePosixPath(name).parts or '\\' in name):
                    issues.append('UNSAFE_PATH')
                if stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK:
                    issues.append('SYMLINK_ENTRY')
            if issues:
                return sorted(set(issues))
            if archive.testzip() is not None:
                return ['ZIP_CRC_FAIL']
            files = {info.filename[len(PREFIX):]: archive.read(info)
                     for info in infos if not info.is_dir()}
    except (OSError, ValueError, zipfile.BadZipFile, RuntimeError, KeyError):
        return ['INVALID_ZIP']
    issues.extend('MISSING:' + item for item in sorted(REQUIRED - set(files)))
    if issues:
        return sorted(set(issues))
    try:
        runtime = json.loads(files['preview-manifest.json'])
        full = json.loads(files['R57-MANIFEST-SHA256.json'])
        if runtime.get('release') != 'R57' or full.get('release') != 'R57':
            issues.append('STALE_RELEASE_LABEL')
        if runtime.get('payment_status') != 'disabled' or full.get('moj1_live_payments') is not False:
            issues.append('PAYMENT_POLICY_MISMATCH')
        if full.get('factory_hold') is not True:
            issues.append('FACTORY_HOLD_MISMATCH')
        for manifest, kind in ((runtime, 'RUNTIME'), (full, 'FULL')):
            for name, record in manifest['files'].items():
                if name not in files:
                    issues.append('MISSING_' + kind + ':' + name)
                elif (len(files[name]) != record['bytes'] or
                      hashlib.sha256(files[name]).hexdigest() != record['sha256']):
                    issues.append(kind + '_HASH_MISMATCH:' + name)
        if set(files) - {'R57-MANIFEST-SHA256.json'} != set(full['files']):
            issues.append('UNTRACKED_FILE')
        for name in runtime['files']:
            if not name.endswith(('.js', '.mjs')) or name not in files:
                continue
            source = files[name].decode('utf-8')
            for ref in re.findall(r"""(?:from\s*|import\s*)['"](\.[^'"]+)['"]""", source):
                parts = []
                for part in (PurePosixPath(name).parent / ref).parts:
                    if part == '..':
                        if not parts:
                            issues.append('IMPORT_ESCAPE:' + name)
                            break
                        parts.pop()
                    elif part != '.':
                        parts.append(part)
                else:
                    dependency = '/'.join(parts)
                    if dependency not in runtime['files']:
                        issues.append('UNTRACKED_IMPORT:' + name + ':' + dependency)
    except (KeyError, TypeError, ValueError, UnicodeDecodeError):
        issues.append('INVALID_MANIFEST')
    policy = files['moj1-commerce-policy.mjs'].decode('utf-8', 'replace')
    for token in ('contractAddress:null', 'ownerApproved:false',
                  'checkoutEnabled:false', 'verifiedBackend:false'):
        if token not in policy:
            issues.append('MOJ1_NOT_PROVEN_DISABLED:' + token)
    return sorted(set(issues))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    parser.add_argument('--sha256')
    args = parser.parse_args()
    errors = verify(args.archive, args.sha256)
    if errors:
        print('BLOCKED', errors)
        raise SystemExit(2)
    print('PASS R57 offline integrity; browser/rights/backup/rollback NOT certified')
