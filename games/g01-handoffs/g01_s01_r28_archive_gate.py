#!/usr/bin/env python3
"""Read-only S-01 handoff: verify G-01 offline game ZIP before any staging.
This NEVER authorizes deployment or substitutes for independent backup/restore.
"""
import hashlib
import json
import stat
import sys
from pathlib import PurePosixPath
from zipfile import ZipFile, BadZipFile

REQUIRED = {'index.html', 'game.js', 'game.css', 'engine3d.js',
            'objective-navigation.mjs', 'moj1-commerce-policy.mjs',
            'ASSET-CREDITS.md', 'RELEASE-NOTES-R28.md'}
MAX_TOTAL = 24 * 1024 * 1024
MAX_FILE = 6 * 1024 * 1024

def verify(path):
    with ZipFile(path) as archive:
        files = archive.infolist()
        if len(files) > 100 or not files:
            raise ValueError('unsafe entry count')
        names = [f.filename for f in files]
        if len(names) != len(set(names)):
            raise ValueError('duplicate ZIP members')
        if sum(f.file_size for f in files) > MAX_TOTAL:
            raise ValueError('archive exceeds size budget')
        for f in files:
            p = PurePosixPath(f.filename)
            if f.is_dir() or f.file_size > MAX_FILE or f.filename.startswith('/') or '\\' in f.filename or '..' in p.parts or not f.filename.startswith('ramadan-war/'):
                raise ValueError('unsafe archive path or size: ' + f.filename)
            if stat.S_IFMT(f.external_attr >> 16) == stat.S_IFLNK:
                raise ValueError('symbolic links forbidden')
        manifest = json.loads(archive.read('ramadan-war/preview-manifest.json'))
        if manifest.get('version') != 'G01-R28-20261030' or manifest.get('payment_status') != 'disabled' or manifest.get('source_pr') != 1532:
            raise ValueError('unexpected release identity or payment state')
        expected = manifest.get('files')
        if not isinstance(expected, dict) or not REQUIRED.issubset(expected):
            raise ValueError('missing required release files')
        actual = {n.removeprefix('ramadan-war/') for n in names} - {'preview-manifest.json'}
        if actual != set(expected):
            raise ValueError('undeclared or missing ZIP member')
        for rel, meta in expected.items():
            p = PurePosixPath(rel)
            if p.is_absolute() or '..' in p.parts or str(p) != rel:
                raise ValueError('unsafe manifest path')
            data = archive.read('ramadan-war/' + rel)
            if len(data) != meta['bytes'] or hashlib.sha256(data).hexdigest() != meta['sha256']:
                raise ValueError('SHA-256/size mismatch: ' + rel)
        policy = archive.read('ramadan-war/moj1-commerce-policy.mjs').decode('utf-8')
        if not all(x in policy for x in ('ownerApproved:false', 'checkoutEnabled:false', 'verifiedBackend:false')):
            raise ValueError('MOJ1 policy is not fail-closed')
        html = archive.read('ramadan-war/index.html').decode('utf-8')
        if '<script type="module" src="./game.js"></script>' not in html:
            raise ValueError('game entry point missing')
        return {'stage': 'READY_FOR_REVIEW', 'archive_integrity': 'PASS',
                'files': len(names), 'release': manifest['version'],
                'sha256': hashlib.sha256(open(path, 'rb').read()).hexdigest(),
                'live_verified': False, 'deployment_authorized': False}

if __name__ == '__main__':
    try:
        if len(sys.argv) != 2:
            raise ValueError('usage: python g01_s01_r28_archive_gate.py <offline.zip>')
        print(json.dumps(verify(sys.argv[1]), sort_keys=True))
    except (ValueError, BadZipFile, KeyError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(json.dumps({'stage': 'BLOCKED', 'archive_integrity': 'FAIL', 'reason': str(exc), 'deployment_authorized': False}))
        sys.exit(2)
