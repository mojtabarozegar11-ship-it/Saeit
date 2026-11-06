#!/usr/bin/env python3
"""Guarded live service-intent preselection, no synthetic customer requests.

Four precise edits: the existing PHP form option uses a whitelisted GET hint,
and three already-live specialist landing routes pass that hint. Generic form
links remain unchanged. All originals are backed up before any replacement.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HOME = Path('/home/zomorod2')
WEB = HOME / 'public_html'
BACKUPS = HOME / '.private/zomorod-service-intent-backups'
FILES = {
    'form': WEB / 'ask-master/index.php',
    'home': WEB / 'index.html',
    'agriculture': WEB / 'agriculture/index.html',
    'services': WEB / 'services/index.html',
}
EXPECTED = {
    'form': '006f1d640138f8f168f9140eb6c58915ccef4b8528c641295b7a6074cf8d12e3',
    'home': 'a50a8dbbda84b9fdda62b9a8a5a04f00a99a331242247aa3a94a28cede1e5722',
    'agriculture': '98b3dae86cadc0ac7881b7a3bca76df4986557af5c7f9635a9ce6b5bbd7f7468',
    'services': '3dc3bcc63878e97d2b022c3ad520794d108e86a139929cef1e9601fca46d56b6',
}
MARKER = 'zm-specialist-intent-20261106'
PHP_OLD = "'<option value=\"service_question\">درخواست خدمات تخصصی</option>'"
PHP_NEW = ("'<option value=\"service_question\"'."
           "((string)($_GET['service']??'')==='1'?' selected':'')."
           "'>درخواست خدمات تخصصی</option>'")
HOME_OLD = ('id="zm-service-entry-home-20261106" class="primary-link" '
            'href="/ask-master/index.php"')
AGRI_OLD = ('id="zm-service-entry-agriculture-20261106" class="cta" '
            'href="/ask-master/index.php"')
SERVICES_OLD = '<a href="/ask-master/index.php" style="font-weight:bold;color:#14583a">'
NEW_HREF = 'href="/ask-master/index.php?service=1"'


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def validate() -> None:
    if os.geteuid() == 0 or os.geteuid() != WEB.stat().st_uid:
        raise RuntimeError('REFUSE_WRONG_SITE_USER')
    if WEB.is_symlink() or BACKUPS.is_symlink() or BACKUPS.parent.is_symlink():
        raise RuntimeError('REFUSE_UNSAFE_ROOT')
    for name, path in FILES.items():
        if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
            raise RuntimeError('REFUSE_UNSAFE_FILE:' + name)
    for route in ('agriculture', 'services'):
        boundary = WEB / route / '.htaccess'
        if boundary.is_symlink() or not boundary.is_file() or 'PassengerEnabled off' not in boundary.read_text():
            raise RuntimeError('REFUSE_NONSTATIC_ROUTE:' + route)


def transform(key: str, source: str) -> tuple[str, str]:
    if key == 'form':
        if source.count('zm-ask-master-service-kind-20261106:route') != 1:
            raise RuntimeError('REFUSE_MISSING_ORIGINAL_SERVICE_MAPPING')
        if source.count(PHP_OLD) != 1:
            raise RuntimeError('REFUSE_CHANGED_SERVICE_OPTION')
        changed = source.replace(PHP_OLD, PHP_NEW, 1)
        changed = changed.replace(PHP_NEW, '/* ' + MARKER + ':form */' + PHP_NEW, 1)
    elif key == 'home':
        if source.count(HOME_OLD) != 1:
            raise RuntimeError('REFUSE_CHANGED_HOME_INTENT_LINK')
        changed = source.replace(HOME_OLD, HOME_OLD.replace('href="/ask-master/index.php"', NEW_HREF), 1)
        changed = changed.replace(NEW_HREF, 'data-zm-intent="' + MARKER + '" ' + NEW_HREF, 1)
    elif key == 'agriculture':
        if source.count(AGRI_OLD) != 1:
            raise RuntimeError('REFUSE_CHANGED_AGRICULTURE_INTENT_LINK')
        changed = source.replace(AGRI_OLD, AGRI_OLD.replace('href="/ask-master/index.php"', NEW_HREF), 1)
        changed = changed.replace(NEW_HREF, 'data-zm-intent="' + MARKER + '" ' + NEW_HREF, 1)
    elif key == 'services':
        if source.count(SERVICES_OLD) != 3 or source.count('zm-service-deliverables-20261106') != 2:
            raise RuntimeError('REFUSE_CHANGED_SERVICE_OFFER_CARDS')
        changed = source.replace(SERVICES_OLD, SERVICES_OLD.replace('href="/ask-master/index.php"', NEW_HREF))
        # One marker, adjacent to the service-specific section; never touch
        # the earlier generic action hub's general inquiry link.
        anchor = '<section id="zm-service-deliverables-20261106"'
        changed = changed.replace(anchor, '<!-- ' + MARKER + ':services -->' + anchor, 1)
    else:
        raise RuntimeError('UNKNOWN_PAGE')
    if MARKER in source:
        raise RuntimeError('REFUSE_REPEATED_OR_UNKNOWN_INTENT_PATCH')
    if changed == source or changed.count(MARKER) != 1:
        raise RuntimeError('INVALID_INTENT_PATCH:' + key)
    return 'needs-patch', changed


def php_lint(content: bytes) -> None:
    binary = shutil.which('php') or '/opt/cpanel/ea-php82/root/usr/bin/php'
    if not Path(binary).is_file():
        raise RuntimeError('PHP_CLI_NOT_AVAILABLE')
    fd, tmp = tempfile.mkstemp(prefix='.service-intent-lint-', suffix='.php', dir=str(WEB / 'ask-master'))
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(content)
        os.chmod(tmp, 0o600)
        check = subprocess.run([binary, '-l', tmp], capture_output=True, timeout=25)
        if check.returncode:
            raise RuntimeError('PHP_SERVICE_INTENT_LINT_FAILED')
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def snapshot() -> dict:
    validate()
    result = {}
    for key, file in FILES.items():
        original = file.read_bytes()
        if sha(original) != EXPECTED[key]:
            raise RuntimeError('REFUSE_CHANGED_LIVE_VERSION:' + key)
        _, new = transform(key, original.decode('utf-8'))
        result[key] = {
            'file': file, 'old': original, 'new': new.encode('utf-8'),
            'old_sha': sha(original), 'new_sha': sha(new.encode('utf-8')),
            'mode': stat.S_IMODE(file.stat().st_mode),
        }
    php_lint(result['form']['new'])
    return result


def atomic(file: Path, payload: bytes, mode: int) -> None:
    fd, path = tempfile.mkstemp(prefix='.zm-intent-', dir=str(file.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(path, mode)
        os.replace(path, file)
    finally:
        if os.path.exists(path):
            os.unlink(path)


def folder(runid: str) -> Path:
    if not re.fullmatch(r'[0-9]{5,20}', runid):
        raise RuntimeError('REFUSE_BAD_RUN_ID')
    return BACKUPS / runid


def restore(runid: str) -> None:
    root = folder(runid)
    meta = json.loads((root / 'manifest.json').read_text())
    for key, target in FILES.items():
        old = (root / (key + '.backup')).read_bytes()
        if sha(old) != meta[key]['old_sha']:
            raise RuntimeError('REFUSE_CORRUPT_INTENT_BACKUP:' + key)
        now = sha(target.read_bytes())
        if now == meta[key]['old_sha']:
            continue
        if now != meta[key]['new_sha']:
            raise RuntimeError('REFUSE_ROLLBACK_CHANGED_BY_OTHER:' + key)
        atomic(target, old, meta[key]['mode'])
        print('INTENT_ROLLED_BACK=' + key)


def preview() -> None:
    for key, row in snapshot().items():
        print('INTENT_PREVIEW=' + key + ':' + row['old_sha'])


def publish(runid: str) -> None:
    rows = snapshot()
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    root = folder(runid)
    root.mkdir(mode=0o700)
    meta = {}
    for key, row in rows.items():
        saved = root / (key + '.backup')
        with saved.open('xb') as stream:
            stream.write(row['old'])
        saved.chmod(0o600)
        meta[key] = {k: row[k] for k in ('old_sha', 'new_sha', 'mode')}
    (root / 'manifest.json').write_text(json.dumps(meta, sort_keys=True))
    (root / 'manifest.json').chmod(0o600)
    try:
        for key, row in rows.items():
            file = row['file']
            if file.is_symlink() or sha(file.read_bytes()) != row['old_sha']:
                raise RuntimeError('REFUSE_CONCURRENT_EDIT:' + key)
            atomic(file, row['new'], row['mode'])
            print('INTENT_PUBLISHED=' + key)
    except Exception:
        restore(runid)
        raise


def verify(runid: str) -> None:
    validate()
    meta = json.loads((folder(runid) / 'manifest.json').read_text())
    for key, target in FILES.items():
        value = target.read_bytes()
        if sha(value) != meta[key]['new_sha'] or value.count(MARKER.encode()) != 1:
            raise RuntimeError('INTENT_ORIGIN_VERIFY_FAILED:' + key)
        if key == 'form':
            php_lint(value)
        print('INTENT_ORIGIN_VERIFIED=' + key)


def selftest() -> None:
    examples = {
        'form': 'zm-ask-master-service-kind-20261106:route ' + PHP_OLD,
        'home': HOME_OLD,
        'agriculture': AGRI_OLD,
        'services': '<section id="zm-service-deliverables-20261106"' +
                    (' ' + SERVICES_OLD) * 3 + 'zm-service-deliverables-20261106',
    }
    for key, value in examples.items():
        state, changed = transform(key, value)
        assert state == 'needs-patch' and changed.count(MARKER) == 1
        assert ("$_GET['service']" in changed) if key == 'form' else ('service=1' in changed)
    print('SERVICE_INTENT_GUARDED_SELFTEST_OK=1')


if __name__ == '__main__':
    argv = sys.argv[1:]
    if argv == ['selftest']:
        selftest()
    elif argv == ['preview']:
        preview()
    elif len(argv) == 2 and argv[0] in ('publish', 'verify', 'rollback'):
        if argv[0] == 'publish':
            publish(argv[1])
        elif argv[0] == 'verify':
            verify(argv[1])
        else:
            validate()
            restore(argv[1])
    else:
        raise RuntimeError('UNKNOWN_MODE')
