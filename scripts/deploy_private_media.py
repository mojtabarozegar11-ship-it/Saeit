#!/usr/bin/env python3
"""Isolated, owner-only PICM media-library installer for cPanel.

This does not touch public docroot assets or alter existing PICM views.
Run from a verified, pinned GitHub Actions -> VPS -> cPanel relay.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import tempfile
import sys

HOME = Path('/home/zomorod2')
APP = HOME / 'Saeit-staging'
DOCROOT = HOME / 'mojplaywin.com'
PRIVATE = HOME / '.private-media-library'
BACKUP_ROOT = HOME / '.mojplaywin-backups' / 'private-media-library'
ROUTE_FILE = APP / 'config' / 'urls.py'
VIEW_FILE = APP / 'core' / 'private_media_library.py'
HTML_FILE = PRIVATE / 'index.html'
MARK = '# MOJPLAYWIN_PRIVATE_MEDIA_OWNER_V1'
ROUTE = '''\n# MOJPLAYWIN_PRIVATE_MEDIA_OWNER_V1\nfrom core.private_media_library import private_media_library\nurlpatterns += [path("picm/media/", private_media_library, name="picm_media_private")]\n'''
VIEW_SOURCE = '''"""Owner-only local media library (no remote uploads or databases)."""
from pathlib import Path
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from core.picm_access import owner_allowed

@never_cache
@require_GET
def private_media_library(request):
    if not getattr(request.user, "is_authenticated", False):
        return redirect("/picm/login/")
    if not owner_allowed(request.user):
        return HttpResponse(status=403)
    path = Path("/home/zomorod2/.private-media-library/index.html")
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 100000:
        return HttpResponse(status=503)
    response = HttpResponse(path.read_bytes(), content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Frame-Options"] = "DENY"
    response["Referrer-Policy"] = "no-referrer"
    response["Cross-Origin-Resource-Policy"] = "same-origin"
    response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response
'''


def validate(run_id, expected_sha):
    if not re.fullmatch(r'[0-9]{1,20}', run_id):
        raise RuntimeError('INVALID_RUN_ID')
    if not re.fullmatch(r'[a-f0-9]{64}', expected_sha):
        raise RuntimeError('INVALID_EXPECTED_DIGEST')
    if pwd.getpwuid(os.getuid()).pw_name != 'zomorod2':
        raise RuntimeError('WRONG_USER')
    for directory in (APP, DOCROOT, PRIVATE, BACKUP_ROOT):
        if directory.is_symlink():
            raise RuntimeError('UNSAFE_ROOT: ' + str(directory))
    if 'Saeit-staging' not in (DOCROOT / 'passenger_wsgi.py').read_text(errors='replace'):
        raise RuntimeError('WRONG_PASSENGER_APP')
    if not (APP / 'core' / 'picm_access.py').is_file() or not (APP / 'core' / 'picm_auth.py').is_file():
        raise RuntimeError('MISSING_PICM_AUTH_MODULES')
    urls = ROUTE_FILE.read_text(encoding='utf-8')
    if 'path("picm/login/"' not in urls or 'SAEIT_PICM_PRIVATE_LOGIN_V1' not in urls:
        raise RuntimeError('PICM_LOGIN_NOT_INSTALLED')
    if 'path("picm/workspace/"' not in urls:
        raise RuntimeError('PICM_WORKSPACE_NOT_INSTALLED')
    if MARK in urls:
        if urls.count(MARK) != 1 or urls.count('path("picm/media/"') != 1:
            raise RuntimeError('PRIVATE_MEDIA_ROUTE_INTEGRITY')
    elif 'path("picm/media/"' in urls:
        raise RuntimeError('PRIVATE_MEDIA_ROUTE_COLLISION')
    ast.parse(VIEW_SOURCE)
    return urls


def atomic_write(path, data, mode):
    if path.is_symlink() or path.parent.is_symlink():
        raise RuntimeError('UNSAFE_FILE: ' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix='.private-media-', dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, 'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def restart():
    directory = APP / 'tmp'
    if directory.is_symlink():
        raise RuntimeError('UNSAFE_PASSENGER_RESTART')
    directory.mkdir(mode=0o700, exist_ok=True)
    (directory / 'restart.txt').touch()


def backup(run_id, paths):
    target = BACKUP_ROOT / run_id
    target.mkdir(mode=0o700, parents=True, exist_ok=False)
    manifest = {}
    for name, path in paths.items():
        if path.is_symlink():
            raise RuntimeError('UNSAFE_EXISTING_FILE: ' + name)
        present = path.is_file()
        manifest[name] = {'present': present, 'mode': path.stat().st_mode & 0o777 if present else 0o600}
        if present:
            atomic_write(target / (name + '.original'), path.read_bytes(), 0o600)
    atomic_write(target / 'manifest.json', json.dumps(manifest, sort_keys=True).encode(), 0o600)
    return target


def rollback(run_id):
    folder = BACKUP_ROOT / run_id
    if folder.is_symlink():
        raise RuntimeError('UNSAFE_BACKUP_DIRECTORY')
    manifest = json.loads((folder / 'manifest.json').read_text())
    paths = {'urls': ROUTE_FILE, 'view': VIEW_FILE, 'html': HTML_FILE}
    for name, path in paths.items():
        item = manifest[name]
        if path.is_symlink():
            raise RuntimeError('UNSAFE_ROLLBACK_FILE: ' + name)
        if item['present']:
            atomic_write(path, (folder / (name + '.original')).read_bytes(), item['mode'])
        elif path.is_file():
            path.unlink()
    restart()
    print('PRIVATE_MEDIA_ROLLBACK_OK')


def deploy(run_id, expected_sha):
    urls = validate(run_id, expected_sha)
    stage = HOME / ('.private-media-stage-' + run_id)
    if stage.is_symlink() or not stage.is_dir():
        raise RuntimeError('UNSAFE_OR_MISSING_STAGE')
    incoming = stage / 'private-media-library.html'
    if incoming.is_symlink() or not incoming.is_file():
        raise RuntimeError('MISSING_HTML')
    data = incoming.read_bytes()
    if not 10000 < len(data) < 100000 or hashlib.sha256(data).hexdigest() != expected_sha:
        raise RuntimeError('HTML_DIGEST_OR_SIZE_MISMATCH')
    for required in (b'<title>Private Media Library</title>', b'localStorage', b'crypto.subtle', b'noindex', b'connect-src \'none\''):
        if required not in data:
            raise RuntimeError('HTML_SAFETY_CHECK_FAILED')
    updated_urls = urls if MARK in urls else urls.rstrip() + '\n' + ROUTE
    ast.parse(updated_urls)
    paths = {'urls': ROUTE_FILE, 'view': VIEW_FILE, 'html': HTML_FILE}
    backup(run_id, paths)
    try:
        PRIVATE.mkdir(mode=0o700, exist_ok=True)
        PRIVATE.chmod(0o700)
        atomic_write(HTML_FILE, data, 0o600)
        atomic_write(VIEW_FILE, VIEW_SOURCE.encode(), 0o644)
        atomic_write(ROUTE_FILE, updated_urls.encode(), ROUTE_FILE.stat().st_mode & 0o777)
        restart()
    except Exception:
        rollback(run_id)
        raise
    print('PRIVATE_MEDIA_DEPLOY_OK sha256=' + expected_sha)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        raise SystemExit('usage: deploy_private_media.py deploy|rollback RUN_ID [DIGEST]')
    if sys.argv[1] == 'deploy' and len(sys.argv) == 4:
        deploy(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'rollback' and len(sys.argv) == 3:
        rollback(sys.argv[2])
    else:
        raise SystemExit('invalid command')
