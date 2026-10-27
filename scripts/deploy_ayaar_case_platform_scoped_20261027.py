#!/usr/bin/env python3
"""One-time, bounded AYAR case-platform deploy; guarded exact-file rollback.

This deployment is restricted to the pre-existing /ayaar/ Django route, its
view, one new case module and ten AYAR static assets. It cannot edit URLconf,
site settings, accounts, orders, other domains, or the primary application DB.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import pwd
import re
import stat
import sys
import tempfile
from pathlib import Path

HOME = Path('/home/zomorod2')
APP = HOME / 'Saeit-staging'
DOCROOT = HOME / 'mojplaywin.com'
RELEASE = APP / 'site_releases/mojplaywin/ayaar-20261027'
VIEW = APP / 'core/ayaar_views.py'
SERVICE = APP / 'core/ayaar_case_service.py'
RESTART = DOCROOT / 'tmp/restart.txt'
URLCONF = APP / 'config/urls.py'
ROUTE_MARKER = '# MPW_AYAAR_EXACT_DJANGO_ROUTE_BEGIN_20261027'
EXISTING_ASSETS = {'index.html','methodology.html','styles.css','hero.css',
                   'app.js','favicon.svg','hero-art.svg'}
NEW_ASSETS = {'services.html','submit.html','track.html','reviewer.html',
              'registry.html','privacy.html','platform.css','platform.js'}
BEFORE = {'ayaar_views.py': VIEW, 'index.html': RELEASE/'index.html',
          'methodology.html': RELEASE/'methodology.html'}
ADD = {'ayaar_case_service.py': SERVICE}
ADD.update({name: RELEASE/name for name in sorted(NEW_ASSETS)})
FILES = {**BEFORE, **ADD}
IDENTITY = 'MPW_AYAAR_CASE_PLATFORM_V1'


def fail(msg):
    raise RuntimeError(msg)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify_file(path):
    if not path.is_file() or path.is_symlink():
        fail('missing_or_unsafe_file_' + path.name)


def args():
    if len(sys.argv) != 4:
        fail('mode_run_commit_required')
    mode, rid, commit = sys.argv[1:]
    if mode not in ('preflight','deploy','rollback'):
        fail('bad_mode')
    if not re.fullmatch(r'[0-9]{5,25}_[0-9]{1,3}', rid):
        fail('bad_run_id')
    if not re.fullmatch(r'[0-9a-f]{40}', commit):
        fail('bad_commit_sha')
    return mode,rid,commit


def workpaths(rid):
    return HOME/('.mpw-ayaar-case-stage-'+rid), HOME/('.mpw-ayaar-case-backup-'+rid)


def environment():
    if pwd.getpwuid(os.getuid()).pw_name != 'zomorod2':
        fail('wrong_cpanel_account')
    for path in (APP, DOCROOT, RELEASE, APP/'core'):
        if not path.is_dir() or path.is_symlink() or path.resolve()!=path:
            fail('unsafe_target_root_'+path.name)
    verify_file(URLCONF)
    verify_file(VIEW)
    verify_file(DOCROOT/'passenger_wsgi.py')
    if ROUTE_MARKER not in URLCONF.read_text('utf-8'):
        fail('ayaar_route_missing')
    if 'Saeit-staging' not in (DOCROOT/'passenger_wsgi.py').read_text('utf-8','replace'):
        fail('unexpected_wsgi_app')
    if RESTART.parent.is_symlink() or not RESTART.parent.is_dir() or RESTART.is_symlink():
        fail('unsafe_restart_target')
    if RESTART.exists() and not RESTART.is_file():
        fail('restart_target_not_file')


def stage_manifest(stage,rid,commit):
    if not stage.is_dir() or stage.is_symlink() or stage.resolve()!=stage:
        fail('unsafe_stage')
    if {p.name for p in stage.iterdir()} != set(FILES)|{'release.json'}:
        fail('unexpected_staged_members')
    meta=json.loads((stage/'release.json').read_text('utf-8'))
    if any((meta.get('identity')!=IDENTITY,meta.get('run')!=rid,meta.get('sha')!=commit)):
        fail('stage_identity_mismatch')
    if set(meta.get('before') or {})!=set(BEFORE) or set(meta.get('after') or {})!=set(FILES):
        fail('stage_hash_set_mismatch')
    for name in FILES:
        item=stage/name
        verify_file(item)
        if not 0<item.stat().st_size<400000:
            fail('staged_file_size_invalid_'+name)
        if digest(item.read_bytes())!=meta['after'][name]:
            fail('staged_checksum_mismatch_'+name)
    for name in BEFORE:
        if not re.fullmatch(r'[a-f0-9]{64}',meta['before'][name]):
            fail('invalid_baseline_hash')
    for filename in ('ayaar_views.py','ayaar_case_service.py'):
        ast.parse((stage/filename).read_text('utf-8'),filename=filename)
    for filename in ('index.html','methodology.html','services.html','submit.html',
                     'track.html','reviewer.html','registry.html','privacy.html'):
        if '<html lang="en" dir="ltr">' not in (stage/filename).read_text('utf-8'):
            fail('english_primary_language_required_'+filename)
    if 'def create_case(' not in (stage/'ayaar_case_service.py').read_text('utf-8'):
        fail('case_engine_missing')
    if 'asset == "api"' not in (stage/'ayaar_views.py').read_text('utf-8'):
        fail('case_api_route_missing')
    return meta


def atomic(path,data,mode=0o644):
    if path.is_symlink():
        fail('symlink_write_refused_'+path.name)
    fd,tmp=tempfile.mkstemp(prefix='.ayaar-case-atomic-',dir=str(path.parent))
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def verify_originals(meta):
    if {p.name for p in RELEASE.iterdir()}!=EXISTING_ASSETS:
        fail('unexpected_existing_ayaar_asset_set')
    for name in EXISTING_ASSETS:
        verify_file(RELEASE/name)
    for name,path in BEFORE.items():
        verify_file(path)
        if digest(path.read_bytes())!=meta['before'][name]:
            fail('live_baseline_changed_'+name)
    for name,path in ADD.items():
        if path.exists() or path.is_symlink():
            fail('new_platform_file_collides_'+name)


def restart():
    if RESTART.is_symlink():
        fail('symlink_restart_refused')
    RESTART.touch(exist_ok=True)


def preflight(rid,commit):
    environment()
    stage,backup=workpaths(rid)
    if any(p.exists() or p.is_symlink() for p in (stage,backup)):
        fail('run_specific_stage_or_backup_collision')
    print('AYAR_CASE_PLATFORM_EXACT_TARGET_PREFLIGHT=PASS')


def deploy(rid,commit):
    environment()
    stage,backup=workpaths(rid)
    meta=stage_manifest(stage,rid,commit)
    verify_originals(meta)
    if backup.exists() or backup.is_symlink():
        fail('backup_collision')
    backup.mkdir(mode=0o700)
    modes={}
    for name,path in BEFORE.items():
        modes[name]=stat.S_IMODE(path.stat().st_mode)
        (backup/name).write_bytes(path.read_bytes())
        os.chmod(backup/name,0o600)
    (backup/'release.json').write_text(json.dumps({**meta,'modes':modes},sort_keys=True),'utf-8')
    os.chmod(backup/'release.json',0o600)
    try:
        verify_originals(meta)
        # Add the private case module and pages before switching the view/API.
        for name,path in ADD.items():
            atomic(path,(stage/name).read_bytes(),0o644)
        for name in ('index.html','methodology.html'):
            atomic(BEFORE[name],(stage/name).read_bytes(),modes[name])
        atomic(VIEW,(stage/'ayaar_views.py').read_bytes(),modes['ayaar_views.py'])
        for name,path in FILES.items():
            if digest(path.read_bytes())!=meta['after'][name]:
                fail('postdeploy_checksum_mismatch_'+name)
        if {p.name for p in RELEASE.iterdir()}!=EXISTING_ASSETS|NEW_ASSETS:
            fail('postdeploy_asset_set_wrong')
        restart()
    except BaseException:
        rollback(rid,commit)
        raise
    print('AYAR_CASE_API_AND_PAGES_DEPLOYED=TRUE')
    print('AYAR_SHARED_PASSENGER_RESTART_REQUESTED=TRUE')


def rollback(rid,commit):
    environment()
    _,backup=workpaths(rid)
    if not backup.is_dir() or backup.is_symlink():
        fail('missing_rollback_backup')
    meta=json.loads((backup/'release.json').read_text('utf-8'))
    if meta.get('identity')!=IDENTITY or meta.get('run')!=rid or meta.get('sha')!=commit:
        fail('rollback_identity_mismatch')
    for name,path in BEFORE.items():
        verify_file(backup/name)
        if digest((backup/name).read_bytes())!=meta['before'][name]:
            fail('corrupted_rollback_backup_'+name)
        verify_file(path)
        if digest(path.read_bytes()) not in {meta['before'][name],meta['after'][name]}:
            fail('concurrent_mutation_refuse_rollback_'+name)
    for name,path in ADD.items():
        if path.exists() or path.is_symlink():
            verify_file(path)
            if digest(path.read_bytes())!=meta['after'][name]:
                fail('concurrent_new_file_refuse_rollback_'+name)
    for name,path in BEFORE.items():
        atomic(path,(backup/name).read_bytes(),int(meta['modes'][name]))
    for name,path in ADD.items():
        if path.is_file():
            path.unlink()
    if {p.name for p in RELEASE.iterdir()}!=EXISTING_ASSETS:
        fail('rollback_asset_set_not_restored')
    restart()
    print('AYAR_CASE_PLATFORM_EXACT_FILES_ROLLED_BACK=TRUE')


if __name__=='__main__':
    try:
        mode,rid,commit=args()
        {'preflight':preflight,'deploy':deploy,'rollback':rollback}[mode](rid,commit)
    except Exception as exc:
        print('AYAR_CASE_SCOPED_ABORT='+str(exc),file=sys.stderr)
        sys.exit(1)
