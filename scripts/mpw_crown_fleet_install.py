#!/usr/bin/env python3
"""Install only the Crown read-only API. No payment settings or database writes.
All backups stay private. No server source, account data or secrets are printed.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

HOME = Path('/home/zomorod2')
APP = HOME / 'Saeit-staging'
TARGET = APP / 'core/crown_fleet.py'
URLS = APP / 'config/urls.py'
BACKUPS = HOME / '.mpw-crown-fleet-backups'
ROUTE = b'\n# Crown Defender V120 read-only account fleet.\nfrom core.crown_fleet import fleet as crown_fleet_v120\nurlpatterns += [path("api/crown-defender/fleet/", crown_fleet_v120, name="crown_fleet_v120")]\n'
PYTHON = HOME / 'virtualenv/Saeit-staging/3.11/bin/python'


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def atomic(path, data, mode=0o644):
    if path.is_symlink():
        raise RuntimeError('Unsafe path')
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix='.crown-fleet-')
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)


def restart():
    tmp = HOME / 'mojplaywin.com/tmp'
    if not tmp.is_dir() or tmp.is_symlink():
        raise RuntimeError('Missing Passenger restart directory')
    (tmp / 'restart.txt').touch()


def rollback(run):
    folder = BACKUPS / run
    manifest = json.loads((folder / 'manifest.json').read_text())
    for key, path in [('module', TARGET), ('urls', URLS)]:
        data = manifest[key]
        current = sha(path.read_bytes()) if path.exists() else None
        if current not in (data['after'], data['before']):
            raise RuntimeError('Concurrent change; refusing rollback')
        if current == data['after']:
            if data['before'] is None:
                path.unlink()
            else:
                raw = (folder / key).read_bytes()
                if sha(raw) != data['before']: raise RuntimeError('Backup hash mismatch')
                atomic(path, raw, data['mode'])
    restart()
    print('CROWN_FLEET_ROLLBACK=PASS')


def install(run, expected):
    stage = HOME / ('.mpw-crown-fleet-stage-' + run + '.py')
    if not re.fullmatch('[a-f0-9]{64}', expected): raise RuntimeError('Bad digest')
    for path in (APP, APP/'core', APP/'config', URLS, stage):
        if not path.exists() or path.is_symlink(): raise RuntimeError('Unsafe application path')
    if not PYTHON.is_file() or not os.access(PYTHON, os.X_OK): raise RuntimeError('Missing application runtime')
    if not (HOME / 'mojplaywin.com/tmp').is_dir(): raise RuntimeError('Missing restart directory')
    if TARGET.exists(): raise RuntimeError('Existing fleet module; review required')
    new = stage.read_bytes()
    if sha(new) != expected: raise RuntimeError('Stage hash mismatch')
    ast.parse(new)
    old_urls = URLS.read_bytes()
    if b'crown-defender/fleet/' in old_urls: raise RuntimeError('Route collision')
    if b'urlpatterns' not in old_urls or b'path' not in old_urls: raise RuntimeError('Unknown URL configuration')
    updated = old_urls + ROUTE
    ast.parse(updated)
    if BACKUPS.is_symlink(): raise RuntimeError('Unsafe backup path')
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    folder = BACKUPS / run
    folder.mkdir(mode=0o700)
    atomic(folder / 'urls', old_urls, 0o600)
    mode = URLS.stat().st_mode & 0o777
    manifest = {'module': {'before': None, 'after': expected, 'mode': 0o644},
                'urls': {'before': sha(old_urls), 'after': sha(updated), 'mode': mode}}
    atomic(folder / 'manifest.json', json.dumps(manifest).encode(), 0o600)
    try:
        atomic(TARGET, new)
        # Verify model compatibility and anonymous response in a fresh Django process.
        # Output is suppressed to avoid exposing any runtime data to public logs.
        check = '''import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django;django.setup()
from core.crown_fleet import catalogue,owned_skus
from django.contrib.auth.models import AnonymousUser
assert owned_skus(AnonymousUser())==[]
assert len(catalogue())==5
'''
        result = subprocess.run([str(PYTHON), '-c', check], cwd=APP, capture_output=True, timeout=45)
        if result.returncode: raise RuntimeError('Fleet compatibility check failed; details kept private')
        if sha(URLS.read_bytes()) != sha(old_urls): raise RuntimeError('Concurrent URL configuration change')
        atomic(URLS, updated, mode)
        restart()
    except BaseException:
        rollback(run)
        raise
    print('CROWN_FLEET_READONLY_API_INSTALLED=PASS')
    print('CROWN_FLEET_DATABASE_WRITES=NONE')
    print('CROWN_FLEET_PAYMENT_ACTIVATION=UNCHANGED')


if __name__ == '__main__':
    action, run = sys.argv[1:3]
    if not re.fullmatch('[0-9]{8,20}', run): raise RuntimeError('Invalid release ID')
    if action == 'install': install(run, sys.argv[3])
    elif action == 'rollback': rollback(run)
    else: raise RuntimeError('Unsupported command')
