#!/usr/bin/env python3
"""Guarded service-inquiry form route on the Zomorod cPanel origin.

Preserves the existing CSRF, rate limiting, SQLite enum, ticket handling and
privacy policy. Maps the new UI choice to the already supported question kind,
with a recognizable server-side message prefix. No records are read or sent.
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
import time
from pathlib import Path
from urllib.request import Request, urlopen

HOME = Path('/home/zomorod2')
WEB = HOME / 'public_html'
FORM = WEB / 'ask-master/index.php'
RESEARCH = WEB / 'research/index.html'
PLANNER = WEB / 'topics/tools/field-trial-design/index.html'
FILES = (FORM, RESEARCH, PLANNER)
BACKUP = HOME / '.private/ask-master-service-kind-backups'
ORIGINAL_PHP_SHA256 = '37590b3f6766455ba031370543bac0711520cc869184d295843979a1ded1e6f4'
MARKER = 'zm-ask-master-service-kind-20261106'
OPTION_ANCHOR = """'</option><option value="order_question">'"""
OPTION_REPLACEMENT = """'</option>'.($fa?'<option value="service_question">درخواست خدمات تخصصی</option>':'').'<option value="order_question">'"""
POST_PATTERN = re.compile(r"if\(\$_SERVER\['REQUEST_METHOD'\]==='POST'\)\{\s*try\{")
POST_INSERT = '''
/* zm-ask-master-service-kind-20261106:route */
if($fa && (string)($_POST['kind']??'')==='service_question'){
    $serviceMessage=trim((string)($_POST['question']??''));
    if(strlen($serviceMessage)<5)throw new InvalidArgumentException('Service inquiry text required');
    $_POST['kind']='question';
    $_POST['question']='[SERVICE_INQUIRY] '.$serviceMessage;
}
'''
RESEARCH_OLD = 'در فرم، «پرسش عمومی» را برای استعلام خدمات انتخاب کنید'
RESEARCH_NEW = 'در فرم، «درخواست خدمات تخصصی» را برای استعلام انتخاب کنید'
PLANNER_OLD = 'در فرم، گزینهٔ «پرسش عمومی» را انتخاب و مسئله'
PLANNER_NEW = 'در فرم، گزینهٔ «درخواست خدمات تخصصی» را انتخاب و مسئله'


def digest(source):
    return hashlib.sha256(source.encode('utf-8')).hexdigest()


def validate():
    if os.geteuid() == 0 or os.geteuid() != WEB.stat().st_uid:
        raise RuntimeError('REFUSE_WRONG_USER')
    for path in FILES:
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('UNSAFE_OR_MISSING_TARGET:' + str(path))
    if BACKUP.is_symlink() or BACKUP.parent.is_symlink():
        raise RuntimeError('UNSAFE_BACKUP_PATH')
    for directory in (WEB / 'research', WEB / 'topics'):
        if directory.is_symlink() or 'PassengerEnabled off' not in (directory / '.htaccess').read_text(encoding='utf-8'):
            raise RuntimeError('STATIC_BOUNDARY_DRIFT:' + str(directory))


def transform(path, source):
    if path == FORM:
        if MARKER in source:
            if source.count(MARKER + ':route') != 1 or source.count('value="service_question"') != 1 or source.count(OPTION_REPLACEMENT) != 1:
                raise RuntimeError('PARTIAL_PHP_PATCH')
            return 'already-patched', source
        if digest(source) != ORIGINAL_PHP_SHA256:
            raise RuntimeError('REFUSE_UNKNOWN_PHP_VERSION')
        if source.count(OPTION_ANCHOR) != 1:
            raise RuntimeError('REFUSE_UNKNOWN_PHP_SELECT')
        matches = list(POST_PATTERN.finditer(source))
        if len(matches) != 1:
            raise RuntimeError('REFUSE_UNKNOWN_PHP_POST_HANDLER')
        inserted = source[:matches[0].end()] + POST_INSERT + source[matches[0].end():]
        patched = inserted.replace(OPTION_ANCHOR, OPTION_REPLACEMENT, 1)
        return 'needs-patch', patched
    if path == RESEARCH:
        if 'zm-research-service-inquiry-20261106:landing' not in source:
            raise RuntimeError('RESEARCH_INQUIRY_NOT_PRESENT')
        old, new = RESEARCH_OLD, RESEARCH_NEW
    elif path == PLANNER:
        if 'zm-research-service-inquiry-20261106:planner' not in source:
            raise RuntimeError('PLANNER_INQUIRY_NOT_PRESENT')
        old, new = PLANNER_OLD, PLANNER_NEW
    else:
        raise RuntimeError('UNEXPECTED_TARGET')
    if old in source:
        if source.count(old) != 1 or new in source:
            raise RuntimeError('STATIC_INQUIRY_GUIDANCE_DRIFT')
        return 'needs-patch', source.replace(old, new, 1)
    if source.count(new) == 1:
        return 'already-patched', source
    raise RuntimeError('REFUSE_UNKNOWN_STATIC_REVISION')


def inspect():
    results = []
    for path in FILES:
        source = path.read_text(encoding='utf-8')
        state, patched = transform(path, source)
        results.append((path, state, source, patched))
    return results


def php_binary():
    candidates = [shutil.which('php')]
    candidates += sorted(Path('/opt/cpanel').glob('ea-php*/root/usr/bin/php'), reverse=True)
    for path in candidates:
        if path and Path(path).is_file() and os.access(path, os.X_OK):
            return str(path)
    raise RuntimeError('PHP_LINTER_NOT_AVAILABLE')


def php_lint(source):
    BACKUP.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(BACKUP, 0o700)
    handle, temporary = tempfile.mkstemp(prefix='.service-kind-lint-', suffix='.php', dir=str(BACKUP))
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as stream:
            stream.write(source)
        os.chmod(temporary, 0o600)
        p = subprocess.run([php_binary(), '-l', temporary], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20, check=False)
        if p.returncode != 0:
            raise RuntimeError('PHP_LINT_FAILED')
        print('SERVICE_KIND_PHP_LINT_OK=1')
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def folder_for(runid):
    if not re.fullmatch(r'[0-9]{5,20}', runid):
        raise RuntimeError('INVALID_RUN_ID')
    BACKUP.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(BACKUP, 0o700)
    folder = BACKUP / runid
    if folder.is_symlink():
        raise RuntimeError('UNSAFE_BACKUP_SYMLINK')
    return folder


def atomic_write(path, data, mode):
    fd, temp = tempfile.mkstemp(prefix='.service-kind-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def preview():
    inspected = inspect()
    php_lint(next(x[3] for x in inspected if x[0] == FORM))
    print('SERVICE_KIND_PREVIEW=' + json.dumps({str(path.relative_to(WEB)): state for path, state, _, _ in inspected}, sort_keys=True))


def publish(runid):
    inspected = inspect()
    php_lint(next(x[3] for x in inspected if x[0] == FORM))
    changes = [x for x in inspected if x[1] == 'needs-patch']
    folder = folder_for(runid)
    if folder.exists():
        raise RuntimeError('BACKUP_ID_COLLISION')
    folder.mkdir(mode=0o700)
    entries = []
    for path, _, source, _ in changes:
        rel = str(path.relative_to(WEB))
        dest = folder / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('xb') as stream:
            stream.write(source.encode('utf-8'))
        dest.chmod(0o600)
        entries.append({'path': rel, 'mode': stat.S_IMODE(path.stat().st_mode)})
    (folder / 'manifest.json').write_text(json.dumps(entries), encoding='utf-8')
    written = []
    try:
        for path, _, source, target in changes:
            mode = next(entry['mode'] for entry in entries if entry['path'] == str(path.relative_to(WEB)))
            atomic_write(path, target.encode('utf-8'), mode)
            written.append((path, source, mode))
    except Exception:
        for path, source, mode in reversed(written):
            if transform(path, path.read_text(encoding='utf-8'))[0] == 'already-patched':
                atomic_write(path, source.encode('utf-8'), mode)
        raise
    print('SERVICE_KIND_PUBLISHED=' + str(len(changes)))


def verify_origin():
    for path in FILES:
        if transform(path, path.read_text(encoding='utf-8'))[0] != 'already-patched':
            raise RuntimeError('ORIGIN_UNVERIFIED:' + str(path))
    php_lint(FORM.read_text(encoding='utf-8'))
    print('SERVICE_KIND_ORIGIN_OK=3')
    verify_public()


def verify_public():
    checks = {
        '/ask-master/index.php': ['<option value="service_question">', 'value="order_question"'],
        '/research/': [RESEARCH_NEW, 'zm-research-service-inquiry-20261106:landing'],
        '/topics/tools/field-trial-design/': [PLANNER_NEW, 'zm-research-service-inquiry-20261106:planner'],
    }
    for attempt in range(6):
        try:
            for route, markers in checks.items():
                request = Request('https://zomorodmelal.ir' + route, headers={'User-Agent': 'Zomorod-Service-Kind-Release/1.0', 'Cache-Control': 'no-cache'})
                with urlopen(request, timeout=30) as response:
                    body = response.read(1200000).decode('utf-8', 'replace')
                    if response.status != 200 or not all(marker in body for marker in markers):
                        raise RuntimeError('PUBLIC_SERVICE_KIND_MISSING:' + route)
            print('SERVICE_KIND_PUBLIC_OK=3')
            return
        except Exception:
            if attempt == 5:
                raise
            time.sleep(5)


def rollback(runid):
    folder = folder_for(runid)
    entries = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    for entry in entries:
        path = WEB / entry['path']
        if path.is_symlink() or transform(path, path.read_text(encoding='utf-8'))[0] != 'already-patched':
            raise RuntimeError('REFUSE_ROLLBACK_DRIFT:' + entry['path'])
    for entry in entries:
        path = WEB / entry['path']
        atomic_write(path, (folder / entry['path']).read_bytes(), int(entry['mode']))
    print('SERVICE_KIND_ROLLED_BACK=' + str(len(entries)))


def selftest():
    assert RESEARCH_OLD != RESEARCH_NEW and PLANNER_OLD != PLANNER_NEW
    assert 'service_question' in OPTION_REPLACEMENT
    assert 'SERVICE_INQUIRY' in POST_INSERT
    assert not any('service_question' in option for option in ('question', 'order_question'))
    print('SERVICE_KIND_SELFTEST_OK=1')


if __name__ == '__main__':
    if sys.argv[1:] == ['selftest']:
        selftest()
        sys.exit(0)
    validate()
    if sys.argv[1:] == ['preview']:
        preview()
    elif len(sys.argv) == 3 and sys.argv[1] == 'publish':
        publish(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == 'verify-origin':
        verify_origin()
    elif len(sys.argv) == 3 and sys.argv[1] == 'rollback':
        rollback(sys.argv[2])
    else:
        raise RuntimeError('UNKNOWN_MODE')
