#!/usr/bin/env python3
"""One exact Django AYAR route, checksum-backed, guarded and reversible.

Only adds a seven-file static tree, a new core/ayaar_views.py module and a
small URLconf block. Never alters payment, DB, games, .htaccess or app settings.
This one-time release may restart the EXISTING MojPlayWin Passenger process;
public smoke and an automatic exact-byte rollback are mandatory.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import pwd
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HOME = Path('/home/zomorod2')
DOCROOT = HOME / 'mojplaywin.com'
APP = HOME / 'Saeit-staging'
URLCONF = APP / 'config/urls.py'
VIEW = APP / 'core/ayaar_views.py'
ASSET_ROOT = APP / 'site_releases/mojplaywin/ayaar-20261027'
RESTART = DOCROOT / 'tmp/restart.txt'
VENV_PYTHON = HOME / 'virtualenv/Saeit-staging/3.11/bin/python'
ASSETS = {'index.html', 'methodology.html', 'styles.css', 'hero.css',
          'app.js', 'favicon.svg', 'hero-art.svg'}
MARKER = '# MPW_AYAAR_EXACT_DJANGO_ROUTE_BEGIN_20261027'
END = '# MPW_AYAAR_EXACT_DJANGO_ROUTE_END_20261027'
BLOCK = ('\n' + MARKER + '\n'
         'from django.urls import path as _mpw_ayaar_path\n'
         'from core.ayaar_views import ayaar as _mpw_ayaar_view\n'
         'urlpatterns.insert(0, _mpw_ayaar_path("ayaar/", _mpw_ayaar_view, name="ayaar"))\n'
         'urlpatterns.insert(1, _mpw_ayaar_path("ayaar/<str:asset>", _mpw_ayaar_view, name="ayaar_asset"))\n'
         + END + '\n').encode('utf-8')


def abort(code):
    raise RuntimeError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def inputs():
    if len(sys.argv) != 4:
        abort('mode_run_sha_required')
    mode, run, sha = sys.argv[1:]
    if mode not in ('preflight', 'deploy', 'rollback'):
        abort('unsupported_mode')
    if not re.fullmatch(r'[0-9]{5,25}_[0-9]{1,3}', run):
        abort('invalid_run')
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        abort('invalid_sha')
    return mode, run, sha


def locations(run):
    return (HOME / ('.mpw-ayaar-django-stage-' + run),
            HOME / ('.mpw-ayaar-django-backup-' + run),
            HOME / ('.mpw-ayaar-django-quarantine-' + run))


def safe_regular(path):
    if not path.is_file() or path.is_symlink():
        abort('missing_or_symlinked_required_file')


def check_root():
    if pwd.getpwuid(os.getuid()).pw_name != 'zomorod2':
        abort('wrong_cpanel_owner')
    if (not APP.is_dir() or APP.is_symlink() or APP.resolve() != APP
            or not DOCROOT.is_dir() or DOCROOT.is_symlink()):
        abort('active_app_or_docroot_contract_missing')
    for path in (URLCONF, DOCROOT / '.htaccess', DOCROOT / 'passenger_wsgi.py',
                 APP / 'core/__init__.py', APP / 'config/__init__.py'):
        safe_regular(path)
    if 'Saeit-staging' not in (DOCROOT / 'passenger_wsgi.py').read_text('utf-8', 'replace'):
        abort('main_wsgi_does_not_reference_pinned_app')
    if not VENV_PYTHON.is_file() or VENV_PYTHON.is_symlink():
        abort('pinned_venv_missing')
    if RESTART.parent.is_symlink() or not RESTART.parent.is_dir() or RESTART.is_symlink():
        abort('unsafe_restart_location')
    for target in (VIEW, ASSET_ROOT):
        if target.exists() or target.is_symlink():
            abort('existing_ayaar_source_collision')
    raw = URLCONF.read_bytes()
    if (MARKER.encode() in raw or END.encode() in raw
            or re.search(br'(?i)\bayaar\b', raw)):
        abort('existing_ayaar_urlconf_conflict')
    if b'urlpatterns' not in raw or b'from django.urls import' not in raw:
        abort('unknown_django_urlconf')
    if not 500 < len(raw) < 250000:
        abort('unexpected_live_urlconf_size')
    ast.parse(raw.decode('utf-8'), filename='config/urls.py')
    return raw


def validate_payload(stage, run, commit):
    if not stage.is_dir() or stage.is_symlink() or stage.resolve() != stage:
        abort('unsafe_stage')
    source_assets = stage / 'site_releases/mojplaywin/ayaar-20261027'
    if not source_assets.is_dir() or source_assets.is_symlink():
        abort('missing_staged_assets')
    view = stage / 'core/ayaar_views.py'
    members = {p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file()}
    expected = {('site_releases/mojplaywin/ayaar-20261027/' + name) for name in ASSETS}
    expected |= {'core/ayaar_views.py', 'manifest.sha256', 'deployment.json'}
    if members != expected:
        abort('unexpected_stage_members')
    for p in stage.rglob('*'):
        if p.is_symlink():
            abort('unsafe_stage_symlink')
        if p.is_file() and (not stat.S_ISREG(p.lstat().st_mode) or not 0 < p.stat().st_size < 350000):
            abort('invalid_stage_file')
    identity = json.loads((stage / 'deployment.json').read_text('utf-8'))
    if identity != {'identity': 'MPW_AYAAR_SCOPED_DJANGO_V1',
                    'run': run, 'sha': commit}:
        abort('unrecognized_staged_release')
    hashes = {}
    for line in (stage / 'manifest.sha256').read_text('ascii').splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  ([a-z0-9/_\.-]+)', line)
        if match is None:
            abort('invalid_manifest')
        value, name = match.groups()
        if name in hashes or name not in expected - {'manifest.sha256', 'deployment.json'}:
            abort('invalid_manifest_member')
        hashes[name] = value
    if set(hashes) != expected - {'manifest.sha256', 'deployment.json'}:
        abort('incomplete_manifest')
    if any(digest((stage / name).read_bytes()) != value for name, value in hashes.items()):
        abort('staged_asset_hash_failure')
    if b'AYAR-PREASSESSMENT-v1' not in (source_assets / 'app.js').read_bytes():
        abort('review_engine_marker_missing')
    if 'AYAR — Digital Product Review' not in (source_assets / 'index.html').read_text('utf-8'):
        abort('identity_marker_missing')
    ast.parse(view.read_text('utf-8'), filename='core/ayaar_views.py')
    return source_assets, view, hashes


def atomic(path, raw, mode):
    if path.is_symlink():
        abort('atomic_target_symlink')
    fd, temp = tempfile.mkstemp(prefix='.mpw-ayaar-safe-', dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def prepare_asset_parent():
    for directory in (APP / 'site_releases', APP / 'site_releases/mojplaywin'):
        if directory.is_symlink():
            abort('unsafe_asset_parent_symlink')
        if directory.exists() and not directory.is_dir():
            abort('asset_parent_not_directory')
        if not directory.exists():
            directory.mkdir(mode=0o755)


def reload_app():
    if RESTART.parent.is_symlink() or RESTART.is_symlink():
        abort('unsafe_passenger_restart_file')
    if RESTART.exists() and not RESTART.is_file():
        abort('unexpected_restart_file_type')
    RESTART.touch(exist_ok=True)


def python_route_proof():
    code = ("import runpy; runpy.run_path('/home/zomorod2/mojplaywin.com/passenger_wsgi.py');"
            "from django.urls import resolve; from django.test import RequestFactory;"
            "a=resolve('/ayaar/'); b=resolve('/ayaar/app.js');"
            "assert a.func.__module__=='core.ayaar_views' and b.func.__module__=='core.ayaar_views';"
            "assert resolve('/store/') is not None;"
            "r=a.func(RequestFactory().get('/ayaar/'));"
            "assert r.status_code==200; r.close()")
    process = subprocess.run([str(VENV_PYTHON), '-c', code], cwd=str(APP),
                             capture_output=True, timeout=55, check=False)
    if process.returncode != 0:
        abort('live_django_import_or_route_proof_failed')


def preflight(run):
    check_root()
    stage, backup, quarantine = locations(run)
    if any(x.exists() or x.is_symlink() for x in (stage, backup, quarantine)):
        abort('run_specific_directory_collision')
    print('AYAAR_SHARED_DJANGO_PATH_PREFLIGHT=PASS')
    print('AYAAR_PRIVATE_URLCONF_BYTES_EXPORTED=FALSE')


def deploy(run, commit):
    original = check_root()
    stage, backup, quarantine = locations(run)
    if backup.exists() or quarantine.exists():
        abort('backup_or_quarantine_collision')
    source_assets, source_view, hashes = validate_payload(stage, run, commit)
    proposed = original + BLOCK
    ast.parse(proposed.decode('utf-8'), filename='config/urls.py')
    mode = stat.S_IMODE(URLCONF.stat().st_mode)
    backup.mkdir(mode=0o700)
    (backup / 'original_urls.py').write_bytes(original)
    (backup / 'manifest.json').write_text(json.dumps({
        'identity': 'MPW_AYAAR_SCOPED_DJANGO_V1', 'run': run,
        'sha': commit, 'before': digest(original), 'after': digest(proposed),
        'url_mode': mode, 'files': hashes}, sort_keys=True), encoding='utf-8')
    if digest(URLCONF.read_bytes()) != digest(original):
        abort('concurrent_urlconf_change')
    prepare_asset_parent()
    source_assets.rename(ASSET_ROOT)
    try:
        atomic(VIEW, source_view.read_bytes(), 0o644)
        atomic(URLCONF, proposed, mode)
        python_route_proof()
        reload_app()
    except BaseException:
        rollback(run, commit, allow_no_restart=True)
        raise
    print('AYAAR_DJANGO_EXACT_ROUTE_INSTALLED=TRUE')
    print('AYAAR_SHARED_RESTART_REQUESTED_ONCE=TRUE')


def rollback(run, commit, allow_no_restart=False):
    if pwd.getpwuid(os.getuid()).pw_name != 'zomorod2':
        abort('wrong_rollback_user')
    _, backup, quarantine = locations(run)
    if not backup.is_dir() or backup.is_symlink():
        abort('missing_rollback_backup')
    manifest = json.loads((backup / 'manifest.json').read_text('utf-8'))
    if (manifest.get('identity') != 'MPW_AYAAR_SCOPED_DJANGO_V1'
            or manifest.get('run') != run or manifest.get('sha') != commit):
        abort('wrong_rollback_identity')
    original = (backup / 'original_urls.py').read_bytes()
    if digest(original) != manifest['before']:
        abort('corrupt_urlconf_rollback_source')
    actual = digest(URLCONF.read_bytes()) if URLCONF.is_file() and not URLCONF.is_symlink() else ''
    if actual == manifest['after']:
        atomic(URLCONF, original, manifest['url_mode'])
    elif actual != manifest['before']:
        abort('concurrent_urlconf_change_refuse_overwrite')
    if VIEW.is_file() and not VIEW.is_symlink():
        desired = manifest['files']['core/ayaar_views.py']
        if digest(VIEW.read_bytes()) != desired:
            abort('new_view_modified_since_install')
        VIEW.unlink()
    elif VIEW.exists() or VIEW.is_symlink():
        abort('unknown_view_state')
    if ASSET_ROOT.is_dir() and not ASSET_ROOT.is_symlink():
        if quarantine.exists() or quarantine.is_symlink():
            abort('quarantine_collision')
        if {p.name for p in ASSET_ROOT.iterdir()} != ASSETS:
            abort('unknown_asset_dir_changes')
        for name in ASSETS:
            if digest((ASSET_ROOT / name).read_bytes()) != manifest['files']['site_releases/mojplaywin/ayaar-20261027/' + name]:
                abort('asset_changed_since_deploy')
        ASSET_ROOT.rename(quarantine)
    if not allow_no_restart:
        reload_app()
    print('AYAAR_DJANGO_URLCONF_RESTORED=TRUE')
    print('AYAAR_NEW_OWNED_ASSETS_QUARANTINED=TRUE')


if __name__ == '__main__':
    try:
        mode, run, commit = inputs()
        if mode == 'preflight':
            preflight(run)
        elif mode == 'deploy':
            deploy(run, commit)
        else:
            rollback(run, commit)
    except Exception as exc:
        print('AYAAR_SCOPED_DJANGO_ABORT=' + str(exc), file=sys.stderr)
        sys.exit(1)
