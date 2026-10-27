#!/usr/bin/env python3
"""Install/remove only a new standalone AYAR Passenger application.

Never alters root .htaccess, Saeit-staging, shared Django, Passenger restarts,
commerce, databases or any existing registered application. cPanel UAPI
responses are validated in-place; no private account inventory is emitted.
"""
from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import stat
import subprocess
import sys
from pathlib import Path

HOME = Path('/home/zomorod2')
DOCROOT = HOME / 'mojplaywin.com'
APP_NAME = 'ayaar-scientific-review-20261027'
APP_DOMAIN = 'mojplaywin.com'
BASE_URI = '/ayaar'
REL_PATH = '/ayaar-independent-20261027'
TARGET = HOME / REL_PATH.lstrip('/')
ASSETS = {'index.html', 'methodology.html', 'styles.css', 'hero.css',
          'app.js', 'favicon.svg', 'hero-art.svg', 'passenger_wsgi.py'}
METADATA = {'manifest.sha256', 'deployment.json'}


def abort(reason):
    raise RuntimeError(reason)


def digest(content):
    return hashlib.sha256(content).hexdigest()


def args():
    if len(sys.argv) != 4:
        abort('required_MODE_RUN_SHA')
    mode, runid, sha = sys.argv[1:]
    if mode not in ('preflight', 'install', 'rollback'):
        abort('unsupported_mode')
    if re.fullmatch(r'[0-9]{5,25}_[0-9]{1,3}', runid) is None:
        abort('invalid_runid')
    if re.fullmatch(r'[0-9a-f]{40}', sha) is None:
        abort('invalid_source_sha')
    return mode, runid, sha


def directories(runid):
    return (HOME / ('.mpw-ayaar-app-stage-' + runid),
            HOME / ('.mpw-ayaar-app-quarantine-' + runid))


def contract():
    if pwd.getpwuid(os.getuid()).pw_name != 'zomorod2':
        abort('unexpected_cpanel_identity')
    if not HOME.is_dir() or not DOCROOT.is_dir() or DOCROOT.is_symlink():
        abort('unknown_document_root')
    if not (DOCROOT / 'passenger_wsgi.py').is_file():
        abort('missing_existing_main_app')
    if TARGET.is_symlink():
        abort('target_symlink_collision')


def uapi(operation, **params):
    command = ['uapi', '--output=json', 'PassengerApps', operation]
    command.extend(k + '=' + str(v) for k, v in params.items())
    proc = subprocess.run(command, capture_output=True, text=True, timeout=42,
                          check=False)
    if proc.returncode != 0:
        abort('passenger_api_nonzero_' + operation)
    try:
        response = json.loads(proc.stdout)
        result = response['result']
    except (KeyError, TypeError, ValueError):
        abort('passenger_api_unrecognized_' + operation)
    if str(result.get('status')) not in ('1', 'True') or result.get('errors'):
        abort('passenger_api_rejected_' + operation)
    return result.get('data')


def walk(value):
    if isinstance(value, dict):
        if ('name' in value or 'app_name' in value) and (
                'domain' in value or 'base_uri' in value or 'path' in value):
            yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def registered_apps():
    data = uapi('list_applications')
    if not isinstance(data, (dict, list)):
        abort('unexpected_passenger_list_shape')
    return list(walk(data))


def app_is_ours(app):
    name = str(app.get('name', app.get('app_name', '')))
    path = str(app.get('path', app.get('app_path', '')))
    uri = str(app.get('base_uri', app.get('base_url', '')))
    domain = str(app.get('domain', ''))
    return (name == APP_NAME and path.rstrip('/') in (
                REL_PATH, REL_PATH.lstrip('/'), str(TARGET))
            and domain.lower() == APP_DOMAIN and uri.rstrip('/') == BASE_URI)


def safe_app_scope(apps, require_ours):
    claimed = [a for a in apps if (
        str(a.get('name', a.get('app_name', ''))) == APP_NAME
        or str(a.get('base_uri', a.get('base_url', ''))).rstrip('/') == BASE_URI
        and str(a.get('domain', '')).lower() == APP_DOMAIN
        or str(a.get('path', a.get('app_path', ''))).rstrip('/') in (
            REL_PATH, REL_PATH.lstrip('/'), str(TARGET)))]
    if require_ours:
        if len(claimed) != 1 or not app_is_ours(claimed[0]):
            abort('registered_app_identity_mismatch')
    elif claimed:
        abort('existing_app_base_name_or_path_collision')


def payload(folder, runid, sha, installed=False):
    if not folder.is_dir() or folder.is_symlink() or folder.resolve() != folder:
        abort('missing_or_unsafe_ayaar_package')
    if {p.name for p in folder.iterdir()} != ASSETS | METADATA:
        abort('ayaar_package_members_invalid')
    for p in folder.iterdir():
        mode = p.lstat().st_mode
        if p.is_symlink() or not stat.S_ISREG(mode) or not 0 < p.stat().st_size < 350000:
            abort('unsafe_ayaar_package_member')
    record = json.loads((folder / 'deployment.json').read_text('utf-8'))
    if record != {'identity': 'MPW_AYAAR_STANDALONE_PASSENGER_V1',
                  'run_id': runid, 'source_sha': sha}:
        abort('unexpected_deployment_identity')
    expected = {}
    for line in (folder / 'manifest.sha256').read_text('ascii').splitlines():
        match = re.fullmatch(r'([a-f0-9]{64})  ([a-z0-9._-]+)', line)
        if not match:
            abort('invalid_manifest_line')
        hash_value, name = match.groups()
        if name in expected or name not in ASSETS:
            abort('invalid_manifest_members')
        expected[name] = hash_value
    if set(expected) != ASSETS:
        abort('incomplete_manifest')
    if any(digest((folder / name).read_bytes()) != d for name, d in expected.items()):
        abort('payload_integrity_failure')
    if b'AYAR-PREASSESSMENT-v1' not in (folder / 'app.js').read_bytes():
        abort('assessment_engine_missing')
    if 'AYAR — Digital Product Review' not in (folder / 'index.html').read_text('utf-8'):
        abort('ayaar_brand_missing')
    if b'def application(environ, start_response)' not in (folder / 'passenger_wsgi.py').read_bytes():
        abort('wsgi_entrypoint_missing')


def preflight(runid):
    contract()
    stage, quarantine = directories(runid)
    if any(p.exists() or p.is_symlink() for p in (stage, quarantine, TARGET)):
        abort('new_app_path_collision')
    safe_app_scope(registered_apps(), False)
    print('AYAAR_STANDALONE_URI_AVAILABLE=PASS')
    print('AYAAR_SHARED_MAIN_APP_UNTOUCHED=TRUE')


def install(runid, sha):
    contract()
    stage, quarantine = directories(runid)
    if TARGET.exists() or TARGET.is_symlink() or quarantine.exists():
        abort('target_existing')
    safe_app_scope(registered_apps(), False)
    payload(stage, runid, sha)
    stage.rename(TARGET)
    try:
        uapi('register_application', name=APP_NAME, path=REL_PATH,
             domain=APP_DOMAIN, base_uri=BASE_URI,
             deployment_mode='production', enabled='1')
        safe_app_scope(registered_apps(), True)
    except BaseException:
        # Registration can partially succeed; never remove an unknown app here.
        print('AYAAR_REGISTRATION_NEEDS_RECONCILIATION', file=sys.stderr)
        raise
    print('AYAAR_STANDALONE_REGISTERED=TRUE')
    print('AYAAR_SHARED_PASSENGER_RESTART=FALSE')


def rollback(runid, sha):
    contract()
    _, quarantine = directories(runid)
    if quarantine.exists() or quarantine.is_symlink():
        abort('quarantine_already_exists')
    payload(TARGET, runid, sha)
    safe_app_scope(registered_apps(), True)
    uapi('unregister_application', name=APP_NAME)
    safe_app_scope(registered_apps(), False)
    TARGET.rename(quarantine)
    print('AYAAR_ONLY_NEW_PASSENGER_APP_UNREGISTERED=TRUE')
    print('AYAAR_ONLY_NEW_APP_FILES_QUARANTINED=TRUE')


if __name__ == '__main__':
    try:
        mode, run, source_sha = args()
        if mode == 'preflight':
            preflight(run)
        elif mode == 'install':
            install(run, source_sha)
        else:
            rollback(run, source_sha)
    except Exception as exc:
        print('AYAAR_ISOLATED_DEPLOY_ABORTED=' + str(exc), file=sys.stderr)
        sys.exit(1)
