#!/usr/bin/env python3
"""Add honest inquiry paths to live research landing and RCBD planner.

No message is submitted, no existing PHP endpoint is altered, and no payment is
initiated. All changes are strictly scoped and backed up before publication.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen

HOME = Path('/home/zomorod2')
WEB = HOME / 'public_html'
RESEARCH = WEB / 'research/index.html'
PLANNER = WEB / 'topics/tools/field-trial-design/index.html'
PATHS = (RESEARCH, PLANNER)
BACKUP = HOME / '.private/research-inquiry-release-backups'
MARKER = 'zm-research-service-inquiry-20261106'
LANDING_ANCHOR = '<!-- zm-field-trial-design-20261106:page -->'
PLANNER_ANCHOR = '<!-- zm-field-trial-design-20261106:engine -->'
PLANNER_V2_SHA256 = '8e34d5246cef5721cf60f0d8f07acbda3427b3bd3c8f2a63d881ce548a3b4909'

LANDING_ACTION = '''\n<aside id="zm-research-service-inquiry-20261106" aria-label="درخواست بررسی خدمات پژوهشی" style="max-width:1140px;margin:16px auto;padding:18px 20px;border-radius:14px;border:2px solid #d4b978;background:#15382d;color:#fff0ca;line-height:1.9">
 <h2 style="margin:0 0 6px;color:#f8df9a">از طرح آزمایش تا درخواست بررسی تخصصی</h2>
 <p style="margin:6px 0 12px">اگر برای طراحی آزمایش، اقتصاد طرح، پژوهش کشاورزی یا تفسیر روش تحقیق به بررسی اختصاصی نیاز دارید، شرح مسئله، هدف و محدودهٔ کار را ثبت کنید. این مسیر فقط برای استعلام اولیه است.</p>
 <nav aria-label="ارتباط برای خدمات پژوهشی" style="display:flex;gap:10px;flex-wrap:wrap">
  <a href="/ask-master/index.php" style="display:inline-block;padding:9px 14px;border-radius:9px;background:#f8df9a;color:#183e30;font-weight:bold">ثبت درخواست بررسی اولیه ←</a>
  <a href="/ask-master/status.php" style="display:inline-block;padding:9px 14px;border-radius:9px;border:1px solid #f8df9a;color:#fff1c9">پیگیری درخواست قبلی ←</a>
  <a href="/contact/" style="display:inline-block;padding:9px 14px;border-radius:9px;border:1px solid #f8df9a;color:#fff1c9">شرایط همکاری ←</a>
 </nav>
 <p style="font-size:.88em;margin:12px 0 0">در فرم، «پرسش عمومی» را برای استعلام خدمات انتخاب کنید و موضوع مورد نظر را بنویسید. ثبت پیام تضمین پذیرش، زمان‌بندی، قیمت یا اجرای پروژه نیست. هیچ اطلاعات محرمانه‌ای در درخواست اولیه ارسال نکنید.</p>
</aside><!-- zm-research-service-inquiry-20261106:landing -->\n'''

PLANNER_ACTION = '''\n<section class="card" id="zm-research-service-inquiry-20261106" aria-label="بررسی تخصصی طرح آزمایش">
 <h2>بررسی اختصاصی طرح پژوهشی</h2>
 <p>اگر لازم است تعداد تکرارها، انتخاب بلوک، متغیر پاسخ یا طرح آماری با شرایط واقعی مزرعه بررسی شود، می‌توانید یک استعلام اولیه ثبت کنید. نقشهٔ تولیدشده در این صفحه خودکار ارسال نمی‌شود؛ تنها جزئیاتی که شخصاً در فرم می‌نویسید ثبت خواهد شد.</p>
 <p><a href="/ask-master/index.php">ثبت استعلام پژوهشی ←</a> · <a href="/ask-master/status.php">پیگیری وضعیت ←</a> · <a href="/contact/">شرایط همکاری ←</a></p>
 <p class="muted">در فرم، گزینهٔ «پرسش عمومی» را انتخاب و مسئله، نوع آزمایش و پرسش علمی خود را شرح دهید. استعلام به معنی تأیید انجام پروژه، اعلام هزینه یا تعهد قراردادی نیست.</p>
</section><!-- zm-research-service-inquiry-20261106:planner -->\n'''


def checksum(source: str) -> str:
    return hashlib.sha256(source.encode('utf-8')).hexdigest()


def validate():
    if os.geteuid() == 0 or os.geteuid() != WEB.stat().st_uid:
        raise RuntimeError('REFUSE_WRONG_SITE_USER')
    for directory in (WEB / 'research', WEB / 'topics'):
        if directory.is_symlink() or not directory.is_dir():
            raise RuntimeError('UNSAFE_DIRECTORY:' + str(directory))
        if 'PassengerEnabled off' not in (directory / '.htaccess').read_text(encoding='utf-8'):
            raise RuntimeError('STATIC_PASSENGER_BOUNDARY_MISSING:' + str(directory))
    for path in PATHS:
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('UNSAFE_OR_MISSING_PAGE:' + str(path))
    if BACKUP.is_symlink() or BACKUP.parent.is_symlink():
        raise RuntimeError('UNSAFE_BACKUP_ROOT')


def transform(path, source):
    if path == RESEARCH:
        expected_marker = MARKER + ':landing'
        anchor = LANDING_ANCHOR
        addition = LANDING_ACTION
        if 'RESEARCH · EVIDENCE · PRACTICE' not in source:
            raise RuntimeError('RESEARCH_IDENTITY_DRIFT')
    elif path == PLANNER:
        expected_marker = MARKER + ':planner'
        anchor = PLANNER_ANCHOR
        addition = PLANNER_ACTION
        if 'Randomized Complete Block Design (RCBD)' not in source or 'xoshiro128**' not in source:
            raise RuntimeError('PLANNER_VERSION_DRIFT')
    else:
        raise RuntimeError('UNEXPECTED_TARGET')
    if expected_marker in source:
        if source.count(expected_marker) != 1 or source.count('id="zm-research-service-inquiry-20261106"') != 1:
            raise RuntimeError('PARTIAL_INQUIRY_PATCH')
        return 'already-patched', source
    if MARKER in source or source.count(anchor) != 1:
        raise RuntimeError('REFUSE_PARTIAL_OR_DRIFTED_MARKER')
    if path == PLANNER and checksum(source) != PLANNER_V2_SHA256:
        raise RuntimeError('REFUSE_UNKNOWN_PLANNER_REVISION')
    if path == RESEARCH and source.count('<main id="main">') != 1:
        raise RuntimeError('RESEARCH_MARKUP_DRIFT')
    return 'needs-patch', source.replace(anchor, addition + anchor, 1)


def inspect():
    items = []
    for path in PATHS:
        source = path.read_text(encoding='utf-8')
        state, target = transform(path, source)
        items.append((path, state, source, target))
    return items


def folder_for(runid):
    if not re.fullmatch(r'[0-9]{5,20}', runid):
        raise RuntimeError('INVALID_RUN_ID')
    BACKUP.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(BACKUP, 0o700)
    folder = BACKUP / runid
    if folder.is_symlink():
        raise RuntimeError('UNSAFE_BACKUP_LINK')
    return folder


def atomic_write(path, payload, mode):
    fd, tmp = tempfile.mkstemp(prefix='.research-inquiry-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def publish(runid):
    changes = [x for x in inspect() if x[1] == 'needs-patch']
    folder = folder_for(runid)
    if folder.exists():
        raise RuntimeError('BACKUP_COLLISION')
    folder.mkdir(mode=0o700)
    entries = []
    for path, _, source, _ in changes:
        relative = str(path.relative_to(WEB))
        dest = folder / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open('xb') as stream:
            stream.write(source.encode('utf-8'))
        dest.chmod(0o600)
        entries.append({'path': relative, 'mode': stat.S_IMODE(path.stat().st_mode)})
    (folder / 'manifest.json').write_text(json.dumps(entries), encoding='utf-8')
    written = []
    try:
        for path, _, source, target in changes:
            mode = next(e['mode'] for e in entries if e['path'] == str(path.relative_to(WEB)))
            atomic_write(path, target.encode('utf-8'), mode)
            written.append((path, source, mode))
    except Exception:
        for path, source, mode in reversed(written):
            if transform(path, path.read_text(encoding='utf-8'))[0] == 'already-patched':
                atomic_write(path, source.encode('utf-8'), mode)
        raise
    print('RESEARCH_INQUIRY_PUBLISHED=' + str(len(changes)))


def verify_origin():
    for path in PATHS:
        if transform(path, path.read_text(encoding='utf-8'))[0] != 'already-patched':
            raise RuntimeError('ORIGIN_INQUIRY_MISSING:' + str(path))
    print('RESEARCH_INQUIRY_ORIGIN_OK=2')
    verify_public()


def verify_public():
    for attempt in range(7):
        try:
            checks = {'/research/': [MARKER + ':landing', '/ask-master/index.php'],
                      '/topics/tools/field-trial-design/': [MARKER + ':planner', '/ask-master/index.php', 'xoshiro128**']}
            for path, tokens in checks.items():
                req = Request('https://zomorodmelal.ir' + path, headers={'User-Agent': 'Zomorod-Research-Inquiry/1.0', 'Cache-Control': 'no-cache'})
                with urlopen(req, timeout=30) as response:
                    body = response.read(1200000).decode('utf-8', 'replace')
                    if response.status != 200 or not all(token in body for token in tokens):
                        raise RuntimeError('PUBLIC_INQUIRY_MISSING:' + path)
            print('RESEARCH_INQUIRY_PUBLIC_OK=2')
            return
        except Exception:
            if attempt == 6:
                raise
            time.sleep(4)


def rollback(runid):
    folder = folder_for(runid)
    entries = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    for entry in entries:
        path = WEB / entry['path']
        if path.is_symlink() or transform(path, path.read_text(encoding='utf-8'))[0] != 'already-patched':
            raise RuntimeError('REFUSE_ROLLBACK_DRIFT:' + entry['path'])
    for entry in entries:
        atomic_write(WEB / entry['path'], (folder / entry['path']).read_bytes(), int(entry['mode']))
    print('RESEARCH_INQUIRY_ROLLED_BACK=' + str(len(entries)))


def selftest():
    a = '<main id="main">RESEARCH · EVIDENCE · PRACTICE' + LANDING_ANCHOR + '</main>'
    state, output = transform(RESEARCH, a)
    assert state == 'needs-patch' and transform(RESEARCH, output)[0] == 'already-patched'
    print('RESEARCH_INQUIRY_SELFTEST_OK=1')


if __name__ == '__main__':
    if sys.argv[1:] == ['selftest']:
        selftest()
        sys.exit(0)
    validate()
    if sys.argv[1:] == ['preview']:
        print('RESEARCH_INQUIRY_PREVIEW=' + json.dumps({str(p.relative_to(WEB)): s for p, s, _, _ in inspect()}, sort_keys=True))
    elif len(sys.argv) == 3 and sys.argv[1] == 'publish':
        publish(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == 'verify-origin':
        verify_origin()
    elif len(sys.argv) == 3 and sys.argv[1] == 'rollback':
        rollback(sys.argv[2])
    else:
        raise RuntimeError('UNKNOWN_MODE')
