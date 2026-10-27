#!/usr/bin/env python3
"""Bounded AYAR static release with exact-route Apache patch and rollback.

The host account, document root, file set, original .htaccess digest,
route patterns and deployment identity are all pinned. No shared restart.
"""
from __future__ import annotations

import hashlib
import json
import os
import pwd
import re
import stat
import sys
import tempfile
from pathlib import Path

ROOT = Path('/home/zomorod2/mojplaywin.com')
HOME = ROOT.parent
TARGET = ROOT / 'ayaar'
ORIGINAL_ROOT_SHA = '39582fae1951301bbc2baf6b3bd033308f580369a0744239f0165d7e72f1c1ad'
MARKER = '# MPW_AYAAR_EXACT_STATIC_ROUTE_20261027'
ASSETS = {'index.html', 'methodology.html', 'styles.css', 'hero.css',
          'app.js', 'favicon.svg', 'hero-art.svg'}
META = {'manifest.sha256', 'deployment.json'}
CHILD_HT = b'PassengerEnabled off\nOptions -Indexes\nDirectoryIndex index.html\n'
RULE = (MARKER + '\n'
        'RewriteCond %{REQUEST_METHOD} ^(GET|HEAD)$\n'
        'RewriteCond %{REQUEST_URI} ^/ayaar/$\n'
        'RewriteRule ^ayaar/$ /ayaar/index.html [END,QSD]\n'
        'RewriteCond %{REQUEST_METHOD} ^(GET|HEAD)$\n'
        'RewriteRule ^ayaar/(index\\.html|methodology\\.html|styles\\.css|hero\\.css|app\\.js|favicon\\.svg|hero-art\\.svg)$ - [END]\n')


def abort(message):
    raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def args():
    if len(sys.argv) != 4:
        abort('required MODE RUN_ID SOURCE_SHA')
    mode, run_id, commit = sys.argv[1:]
    if mode not in ('preflight', 'install', 'rollback'):
        abort('invalid_mode')
    if not re.fullmatch(r'[0-9]{5,25}_[0-9]{1,3}', run_id):
        abort('invalid_run_id')
    if not re.fullmatch(r'[a-f0-9]{40}', commit):
        abort('invalid_commit')
    return mode, run_id, commit


def locations(run_id):
    return (HOME / ('.mpw-ayaar-route-stage-' + run_id),
            HOME / ('.mpw-ayaar-route-backup-' + run_id),
            HOME / ('.mpw-ayaar-route-quarantine-' + run_id))


def contract():
    if pwd.getpwuid(os.getuid()).pw_name != 'zomorod2':
        abort('wrong_cpanel_user')
    if not ROOT.is_dir() or ROOT.is_symlink() or ROOT.resolve() != ROOT:
        abort('wrong_document_root')
    for name in ('.htaccess', 'passenger_wsgi.py'):
        path = ROOT / name
        if not path.is_file() or path.is_symlink():
            abort('missing_shared_site_contract')
    return ROOT / '.htaccess'


def check_original():
    ht = contract()
    original = ht.read_bytes()
    if sha(original) != ORIGINAL_ROOT_SHA:
        abort('root_route_drift_abort')
    if MARKER.encode() in original or re.search(br'ayaar', original, re.I):
        abort('existing_ayaar_route_conflict')
    if TARGET.exists() or TARGET.is_symlink():
        abort('nonempty_ayaar_target_collision')
    if not re.search(br'^RewriteEngine[ \t]+On[ \t]*$', original, re.I | re.M):
        abort('missing_rewrite_engine')
    return ht, original


def inspect_stage(stage, run_id, commit):
    if not stage.is_dir() or stage.is_symlink() or stage.resolve() != stage:
        abort('missing_stage')
    if {p.name for p in stage.iterdir()} != ASSETS | META:
        abort('unexpected_stage_files')
    for item in stage.iterdir():
        if item.is_symlink() or not stat.S_ISREG(item.lstat().st_mode):
            abort('unsafe_stage_entry')
        if not 0 < item.stat().st_size < 350_000:
            abort('oversized_or_empty_stage_file')
    identity = json.loads((stage / 'deployment.json').read_text('utf-8'))
    if identity != {'run_id': run_id, 'source_sha': commit,
                    'identity': 'MPW_AYAAR_BOUNDED_ROUTE_V2'}:
        abort('bad_stage_identity')
    expected = {}
    for line in (stage / 'manifest.sha256').read_text('utf-8').splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  ([a-z0-9.-]+)', line)
        if not match:
            abort('bad_manifest_line')
        digest, name = match.groups()
        if name not in ASSETS or name in expected:
            abort('bad_manifest_members')
        expected[name] = digest
    if set(expected) != ASSETS:
        abort('incomplete_manifest')
    for name in ASSETS:
        if sha((stage / name).read_bytes()) != expected[name]:
            abort('asset_digest_mismatch')
    if b'AYAR-PREASSESSMENT-v1' not in (stage / 'app.js').read_bytes():
        abort('review_engine_missing')
    if 'AYAR — Digital Product Review' not in (stage / 'index.html').read_text('utf-8'):
        abort('brand_marker_missing')


def patch(original):
    pattern = re.compile(br'^RewriteEngine[ \t]+On[ \t]*$', re.I | re.M)
    transformed, changes = pattern.subn(lambda m: m.group(0) + b'\n' + RULE.encode(), original, count=1)
    if changes != 1 or transformed.count(MARKER.encode()) != 1:
        abort('rewrite_patch_not_exact')
    if transformed.replace(b'\n' + RULE.encode(), b'', 1) != original:
        abort('rewrite_patch_not_reversible')
    return transformed


def atomic(path, data):
    if path.is_symlink():
        abort('unsafe_symlink_write')
    mode = stat.S_IMODE(path.stat().st_mode)
    fd, tmp = tempfile.mkstemp(prefix='.mpw-ayaar-ht-', dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def preflight(run_id):
    check_original()
    stage, backup, quarantine = locations(run_id)
    for path in (stage, backup, quarantine):
        if path.exists() or path.is_symlink():
            abort('run_specific_target_collision')
    print('AYAAR_ROOT_SHA_PREFLIGHT=PASS')
    print('AYAAR_MUTATION_SCOPE=ONLY_AYAAR_DIR_AND_ONE_EXACT_ROOT_ROUTE')


def install(run_id, commit):
    ht, original = check_original()
    stage, backup, quarantine = locations(run_id)
    if backup.exists() or quarantine.exists():
        abort('existing_run_backup')
    inspect_stage(stage, run_id, commit)
    transformed = patch(original)
    assert re.fullmatch(r'/ayaar/', '/ayaar/')
    for protected in ('/store/', '/checkout/', '/saman/', '/taniya/',
                      '/mojtaba.roozegar/', '/farnaz/', '/picm/'):
        if protected.startswith('/ayaar/'):
            abort('protected_prefix_overlap')
    backup.mkdir(mode=0o700)
    (backup / 'original.htaccess').write_bytes(original)
    (backup / 'manifest.json').write_text(json.dumps({
        'run_id': run_id, 'source_sha': commit, 'before': sha(original),
        'after': sha(transformed), 'child_ht_sha': sha(CHILD_HT),
        'marker': MARKER}, sort_keys=True), encoding='utf-8')
    (stage / '.htaccess').write_bytes(CHILD_HT)
    try:
        stage.rename(TARGET)
        atomic(ht, transformed)
        if sha(ht.read_bytes()) != sha(transformed):
            abort('write_verification_failed')
    except BaseException:
        if ht.is_file() and sha(ht.read_bytes()) == sha(transformed):
            atomic(ht, original)
        if TARGET.is_dir() and not TARGET.is_symlink() and not quarantine.exists():
            TARGET.rename(quarantine)
        (backup / 'FAILED').write_text('true\n', encoding='ascii')
        raise
    print('AYAAR_BOUNDED_ROUTE_INSTALLED=TRUE')
    print('AYAAR_SHARED_PASSENGER_RESTART=FALSE')


def rollback(run_id, commit):
    ht = contract()
    _, backup, quarantine = locations(run_id)
    if not backup.is_dir() or backup.is_symlink():
        abort('missing_backup')
    metadata = json.loads((backup / 'manifest.json').read_text('utf-8'))
    original = (backup / 'original.htaccess').read_bytes()
    if (metadata['run_id'] != run_id or metadata['source_sha'] != commit
            or sha(original) != metadata['before'] or sha(original) != ORIGINAL_ROOT_SHA):
        abort('invalid_rollback_identity')
    actual = sha(ht.read_bytes())
    if actual == metadata['after']:
        atomic(ht, original)
    elif actual != metadata['before']:
        abort('concurrent_root_edit_refuse_rollback')
    if TARGET.is_dir() and not TARGET.is_symlink():
        if quarantine.exists() or quarantine.is_symlink():
            abort('quarantine_collision')
        if sha((TARGET / '.htaccess').read_bytes()) != metadata['child_ht_sha']:
            abort('unexpected_child_config_change')
        inspect_stage_assets_rollback(TARGET, run_id, commit)
        TARGET.rename(quarantine)
    print('AYAAR_EXACT_ROUTE_ROOT_RESTORED=TRUE')
    print('AYAAR_NEW_STATIC_DIRECTORY_QUARANTINED=TRUE')


def inspect_stage_assets_rollback(folder, run_id, commit):
    if {p.name for p in folder.iterdir()} != ASSETS | META | {'.htaccess'}:
        abort('unrecognized_new_directory_contents')
    metadata = json.loads((folder / 'deployment.json').read_text('utf-8'))
    if metadata != {'run_id': run_id, 'source_sha': commit,
                    'identity': 'MPW_AYAAR_BOUNDED_ROUTE_V2'}:
        abort('unknown_new_directory_owner')
    hashes = {}
    for line in (folder / 'manifest.sha256').read_text('ascii').splitlines():
        digest, name = line.split('  ', 1)
        hashes[name] = digest
    if set(hashes) != ASSETS or any(sha((folder / n).read_bytes()) != d for n, d in hashes.items()):
        abort('new_directory_changed_since_deployment')


if __name__ == '__main__':
    try:
        mode, run, commit = args()
        if mode == 'preflight':
            preflight(run)
        elif mode == 'install':
            install(run, commit)
        else:
            rollback(run, commit)
    except Exception as exc:
        print('AYAAR_BOUNDED_DEPLOY_ABORTED=' + str(exc), file=sys.stderr)
        sys.exit(1)
