#!/usr/bin/env python3
"""Checksum-guarded AYAR manual AI-assisted reviewer workflow release.

Only existing AYAR-specific view/service modules and ten existing AYAR
assets are modified. No database, URLconf, store, payments or other sites.
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
RESTART = DOCROOT / 'tmp/restart.txt'
ROUTE_MARKER = '# MPW_AYAAR_EXACT_DJANGO_ROUTE_BEGIN_20261027'
ALL_ASSETS = {'index.html','methodology.html','styles.css','hero.css','app.js',
              'favicon.svg','hero-art.svg','services.html','submit.html',
              'track.html','reviewer.html','registry.html','privacy.html',
              'platform.css','platform.js'}
FILES = {'ayaar_case_service.py':APP/'core/ayaar_case_service.py',
         'ayaar_views.py':APP/'core/ayaar_views.py'}
FILES.update({name:RELEASE/name for name in (
    'services.html','submit.html','track.html','reviewer.html','registry.html',
    'privacy.html','platform.css','platform.js','index.html','methodology.html')})
IDENTITY = 'MPW_AYAAR_EXPERT_ENGINE_MANUAL_V1'


def fail(message):
    raise RuntimeError(message)


def hash_bytes(data):
    return hashlib.sha256(data).hexdigest()


def file_guard(path):
    if not path.is_file() or path.is_symlink():
        fail('missing_or_unsafe_file_'+path.name)


def args():
    if len(sys.argv)!=4:
        fail('expected_mode_run_sha')
    mode,rid,commit=sys.argv[1:]
    if mode not in ('preflight','deploy','rollback'):
        fail('invalid_mode')
    if not re.fullmatch(r'[0-9]{5,25}_[0-9]{1,3}',rid):
        fail('invalid_run')
    if not re.fullmatch(r'[a-f0-9]{40}',commit):
        fail('invalid_sha')
    return mode,rid,commit


def workpaths(rid):
    return HOME/('.mpw-ayaar-expert-stage-'+rid),HOME/('.mpw-ayaar-expert-backup-'+rid)


def environment():
    if pwd.getpwuid(os.getuid()).pw_name!='zomorod2':
        fail('wrong_host_account')
    for directory in (APP,APP/'core',DOCROOT,RELEASE):
        if not directory.is_dir() or directory.is_symlink() or directory.resolve()!=directory:
            fail('unexpected_path_'+directory.name)
    if {p.name for p in RELEASE.iterdir()}!=ALL_ASSETS:
        fail('unexpected_release_asset_members')
    for name,path in FILES.items():
        file_guard(path)
    urlconf=APP/'config/urls.py'
    wsgi=DOCROOT/'passenger_wsgi.py'
    file_guard(urlconf)
    file_guard(wsgi)
    if ROUTE_MARKER not in urlconf.read_text('utf-8'):
        fail('original_scoped_route_missing')
    if 'Saeit-staging' not in wsgi.read_text('utf-8','replace'):
        fail('unexpected_wsgi')
    if RESTART.parent.is_symlink() or not RESTART.parent.is_dir() or RESTART.is_symlink():
        fail('unsafe_restart')


def manifest(stage,rid,commit):
    if not stage.is_dir() or stage.is_symlink() or stage.resolve()!=stage:
        fail('invalid_stage')
    if {x.name for x in stage.iterdir()}!=set(FILES)|{'release.json'}:
        fail('unapproved_stage_members')
    meta=json.loads((stage/'release.json').read_text('utf-8'))
    if meta.get('identity')!=IDENTITY or meta.get('run')!=rid or meta.get('sha')!=commit:
        fail('wrong_release_manifest_identity')
    if set(meta.get('before') or {})!=set(FILES) or set(meta.get('after') or {})!=set(FILES):
        fail('manifest_file_set_mismatch')
    for name in FILES:
        source=stage/name
        file_guard(source)
        if not 0<source.stat().st_size<400000:
            fail('invalid_staged_file_size_'+name)
        if hash_bytes(source.read_bytes())!=meta['after'][name]:
            fail('payload_hash_mismatch_'+name)
        if not re.fullmatch(r'[a-f0-9]{64}',meta['before'][name]):
            fail('bad_previous_hash_'+name)
    for name in ('ayaar_case_service.py','ayaar_views.py'):
        ast.parse((stage/name).read_text('utf-8'),name)
    source=(stage/'ayaar_case_service.py').read_text('utf-8')
    if 'def grant_ai_consent(' not in source or 'ai_processing_consent' not in source:
        fail('missing_applicant_ai_authorization')
    view=(stage/'ayaar_views.py').read_text('utf-8')
    if '"manual_ai_review": True' not in view or '"model_api_enabled": False' not in view:
        fail('missing_manual_ai_review_api_mode')
    for name in ('services.html','submit.html','track.html','reviewer.html','registry.html','privacy.html'):
        html=(stage/name).read_text('utf-8')
        if '<html lang="en" dir="ltr">' not in html or 'platform.js?v=platform-5' not in html or 'platform.css?v=platform-2' not in html:
            fail('stale_or_nonenglish_platform_page_'+name)
    javascript=(stage/'platform.js').read_text('utf-8')
    if 'downloadReviewPacket' not in javascript or 'Import analyzed findings' not in javascript:
        fail('missing_manual_ai_handoff_interface')
    return meta


def atomic(path,raw,mode):
    if path.is_symlink():
        fail('unsafe_atomic_target_'+path.name)
    fd,temp=tempfile.mkstemp(prefix='.ayaar-upgrade-',dir=str(path.parent))
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as f:
            f.write(raw)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def baseline_check(meta):
    for name,path in FILES.items():
        file_guard(path)
        if hash_bytes(path.read_bytes())!=meta['before'][name]:
            fail('live_source_changed_'+name)


def restart():
    if RESTART.is_symlink() or (RESTART.exists() and not RESTART.is_file()):
        fail('unsafe_restart_file')
    RESTART.touch(exist_ok=True)


def preflight(rid,commit):
    environment()
    stage,backup=workpaths(rid)
    if any(p.exists() or p.is_symlink() for p in (stage,backup)):
        fail('stage_or_backup_collision')
    print('AYAR_EXPERT_ENGINE_EXACT_EXISTING_FILES_PREFLIGHT=PASS')


def deploy(rid,commit):
    environment()
    stage,backup=workpaths(rid)
    meta=manifest(stage,rid,commit)
    baseline_check(meta)
    if backup.exists() or backup.is_symlink():
        fail('backup_collision')
    backup.mkdir(mode=0o700)
    modes={}
    for name,path in FILES.items():
        modes[name]=stat.S_IMODE(path.stat().st_mode)
        (backup/name).write_bytes(path.read_bytes())
        os.chmod(backup/name,0o600)
    (backup/'release.json').write_text(json.dumps({**meta,'modes':modes},sort_keys=True),'utf-8')
    os.chmod(backup/'release.json',0o600)
    try:
        baseline_check(meta)
        # Keep the original route active; replace its target view only last.
        for name,path in FILES.items():
            if name!='ayaar_views.py':
                atomic(path,(stage/name).read_bytes(),modes[name])
        atomic(FILES['ayaar_views.py'],(stage/'ayaar_views.py').read_bytes(),modes['ayaar_views.py'])
        for name,path in FILES.items():
            if hash_bytes(path.read_bytes())!=meta['after'][name]:
                fail('postwrite_mismatch_'+name)
        restart()
    except BaseException:
        rollback(rid,commit)
        raise
    print('AYAR_EXPERT_ENGINE_WORKFLOW_UPGRADED=TRUE')
    print('AYAR_PRIVATE_CASES_PRESERVED=TRUE')


def rollback(rid,commit):
    environment()
    _,backup=workpaths(rid)
    if not backup.is_dir() or backup.is_symlink():
        fail('missing_backup')
    meta=json.loads((backup/'release.json').read_text('utf-8'))
    if meta.get('identity')!=IDENTITY or meta.get('run')!=rid or meta.get('sha')!=commit:
        fail('rollback_identity_mismatch')
    for name,path in FILES.items():
        file_guard(backup/name)
        file_guard(path)
        if hash_bytes((backup/name).read_bytes())!=meta['before'][name]:
            fail('backup_corruption_'+name)
        if hash_bytes(path.read_bytes()) not in (meta['before'][name],meta['after'][name]):
            fail('concurrent_change_refuse_rollback_'+name)
    for name,path in FILES.items():
        atomic(path,(backup/name).read_bytes(),int(meta['modes'][name]))
    restart()
    print('AYAR_EXPERT_ENGINE_UPGRADE_EXACT_BYTES_ROLLED_BACK=TRUE')


if __name__=='__main__':
    try:
        mode,rid,commit=args()
        {'preflight':preflight,'deploy':deploy,'rollback':rollback}[mode](rid,commit)
    except Exception as exc:
        print('AYAR_EXPERT_ENGINE_SCOPED_ABORT='+str(exc),file=sys.stderr)
        sys.exit(1)
