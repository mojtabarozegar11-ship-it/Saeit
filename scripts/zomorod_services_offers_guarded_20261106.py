#!/usr/bin/env python3
"""Single-file reversible release of concrete Zomorod service offer details.

Preserves the already-live services action hub. The new section presents
conditional deliverables, required customer inputs and the existing form.
Does not submit forms, collect customers, send messages, or modify databases.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

HOME = Path('/home/zomorod2')
WEB = HOME / 'public_html'
ROUTE = WEB / 'services'
FILE = ROUTE / 'index.html'
BACKUPS = HOME / '.private/zomorod-services-offers-backups'
MARKER = 'zm-service-deliverables-20261106'
ANCHOR = '<!-- zm-services-conversion-20261106 -->'
TITLE_OLD = '<title>خدمات و حوزه‌های تخصصی | زمرد ملل</title>'
TITLE_NEW = '<title>شرکت خدمات کشاورزی و اقتصاد تولید | زمرد ملل</title>'
META = re.compile(r'<meta name="description" content="([^"]*)">')
META_NEW = ('<meta name="description" content="شرکت خدمات کشاورزی زمرد ملل؛ '
            'استعلام ارزیابی اقتصادی مزرعه، مدیریت منابع آب و امکان‌سنجی تولید. '
            'خروجی پیشنهادی، اطلاعات لازم و مسیر ثبت درخواست با شناسه پیگیری.">')

SECTION = '''
<section id="zm-service-deliverables-20261106" aria-labelledby="zm-service-deliverables-title"
 style="max-width:1150px;margin:25px auto;padding:23px 18px;border-radius:16px;background:#f4f5e9;color:#153326;box-sizing:border-box;font:inherit;line-height:1.9">
 <p style="color:#315b48;margin:0">ZOMOROD MELAL · SPECIALIST SERVICES</p>
 <h2 id="zm-service-deliverables-title" style="font-size:clamp(21px,2.6vw,29px);margin:5px 0 10px;color:#153b2a">خدمات تخصصی؛ موضوع، دادهٔ لازم و نتیجهٔ قابل بررسی</h2>
 <p>برای اینکه استعلام به نتیجه برسد، موضوع و اطلاعات اولیهٔ پروژه را ثبت کنید. موارد زیر نمونهٔ دامنهٔ بررسی هستند؛ نوع گزارش، زمان تحویل، قیمت و امکان اجرای هر خدمت تنها پس از ارزیابی و توافق مشخص می‌شود.</p>
 <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,280px),1fr));gap:14px;margin:20px 0">
  <article style="border:1px solid #8eae9b;border-radius:12px;padding:17px;background:white">
   <h3 style="color:#144834;margin:0 0 7px">۱. ارزیابی اقتصادی واحد کشاورزی</h3>
   <p><strong>کاربرد:</strong> ارزیابی سودآوری و تصمیم تولید در مزرعه، گلخانه یا واحد دامپروری.</p>
   <p><strong>اطلاعات لازم:</strong> سطح یا ظرفیت، محصول، مقدار تولید، هزینه نهاده‌ها و فروش.</p>
   <p><strong>خروجی پیشنهادی:</strong> ساختار هزینه، حاشیه سود، نقطهٔ سربه‌سر و سناریوهای تصمیم‌گیری.</p>
   <a href="/ask-master/index.php" style="font-weight:bold;color:#14583a">استعلام ارزیابی اقتصادی ←</a>
  </article>
  <article style="border:1px solid #8eae9b;border-radius:12px;padding:17px;background:white">
   <h3 style="color:#144834;margin:0 0 7px">۲. مدیریت آب و منابع تولید</h3>
   <p><strong>کاربرد:</strong> بررسی الگوی مصرف آب و انرژی و گزینه‌های بهبود بهره‌وری.</p>
   <p><strong>اطلاعات لازم:</strong> منطقه، نوع کشت، مساحت، منبع آب، روش آبیاری و محدودیت‌ها.</p>
   <p><strong>خروجی پیشنهادی:</strong> برآورد نیاز منابع، مقایسه گزینه‌ها و اولویت‌های اجرایی قابل سنجش.</p>
   <a href="/ask-master/index.php" style="font-weight:bold;color:#14583a">استعلام مدیریت منابع ←</a>
  </article>
  <article style="border:1px solid #8eae9b;border-radius:12px;padding:17px;background:white">
   <h3 style="color:#144834;margin:0 0 7px">۳. امکان‌سنجی پروژهٔ تولیدی</h3>
   <p><strong>کاربرد:</strong> بررسی اولیهٔ طرح توسعه، گلخانه، فرآوری یا زنجیرهٔ ارزش.</p>
   <p><strong>اطلاعات لازم:</strong> محصول، مکان، ظرفیت، سرمایهٔ در دسترس، بازار هدف و محدودیت‌ها.</p>
   <p><strong>خروجی پیشنهادی:</strong> سناریوهای هزینه و درآمد، ریسک‌های کلیدی و شاخص‌های تصمیم‌گیری سرمایه‌گذاری.</p>
   <a href="/ask-master/index.php" style="font-weight:bold;color:#14583a">استعلام امکان‌سنجی ←</a>
  </article>
 </div>
 <p style="margin:8px 0"><strong>گام بعدی:</strong> فرم را باز کنید، گزینهٔ «درخواست خدمات تخصصی» را انتخاب کنید و مسئله را بنویسید. شناسهٔ ثبت‌شده را برای پیگیری نزد خود نگه دارید.</p>
 <p style="font-size:.9em;color:#39534b;margin:8px 0 0">این موارد اعلام قیمت، مشاورهٔ قطعی، پذیرش سفارش یا تضمین نتیجه نیستند. خدمات دارای الزام مجوز فقط در حدود مجوز و قرارداد معتبر ارائه می‌شوند.</p>
</section><!-- zm-service-deliverables-20261106 -->
'''


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def validate() -> None:
    if os.geteuid() == 0 or os.geteuid() != WEB.stat().st_uid:
        raise RuntimeError('REFUSE_WRONG_SITE_USER')
    if ROUTE.is_symlink() or FILE.is_symlink() or not FILE.is_file() or BACKUPS.is_symlink():
        raise RuntimeError('REFUSE_UNSAFE_FILE')
    boundary = ROUTE / '.htaccess'
    if boundary.is_symlink() or not boundary.is_file() or 'PassengerEnabled off' not in boundary.read_text():
        raise RuntimeError('REFUSE_NONSTATIC_SERVICES_ROUTE')


def transform(source: str) -> tuple[str, str]:
    if source.count(ANCHOR) != 1 or source.count('<main id="main">') != 1:
        raise RuntimeError('REFUSE_CHANGED_SERVICE_STRUCTURE')
    if source.count('<link rel="canonical" href="https://zomorodmelal.ir/services/">') != 1:
        raise RuntimeError('REFUSE_CHANGED_CANONICAL')
    if source.count(MARKER) != 0:
        if source.count(MARKER) != 2 or source.count(SECTION) != 1 or TITLE_NEW not in source or META_NEW not in source:
            raise RuntimeError('REFUSE_PARTIAL_SERVICE_OFFERS_PATCH')
        return 'already-patched', source
    if source.count(TITLE_OLD) != 1 or len(source) < 10000:
        raise RuntimeError('REFUSE_CHANGED_SERVICE_TITLE_OR_CONTENT')
    metas = META.findall(source)
    if len(metas) != 1 or not metas[0].startswith('در این صفحه حوزه‌های قابل بررسی'):
        raise RuntimeError('REFUSE_CHANGED_SERVICE_DESCRIPTION')
    result = source.replace(TITLE_OLD, TITLE_NEW, 1)
    result = META.sub(lambda _: META_NEW, result, count=1)
    result = result.replace(ANCHOR, ANCHOR + SECTION, 1)
    return 'needs-patch', result


def atomic_write(target: Path, content: bytes, mode: int) -> None:
    fd, temp = tempfile.mkstemp(prefix='.zm-service-offers-', dir=str(target.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, mode)
        os.replace(temp, target)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def backup_folder(runid: str) -> Path:
    if not re.fullmatch(r'[0-9]{5,20}', runid):
        raise RuntimeError('REFUSE_INVALID_RUN_ID')
    return BACKUPS / runid


def preview() -> None:
    validate()
    source = FILE.read_bytes()
    state, _ = transform(source.decode('utf-8'))
    print('SERVICE_OFFERS_PREVIEW=' + state)
    print('SERVICE_OFFERS_ORIGIN_SHA256=' + digest(source))


def publish(runid: str) -> None:
    validate()
    original = FILE.read_bytes()
    state, updated = transform(original.decode('utf-8'))
    if state != 'needs-patch':
        raise RuntimeError('REFUSE_REPEATED_SERVICE_OFFERS_PUBLISH')
    new = updated.encode('utf-8')
    mode = stat.S_IMODE(FILE.stat().st_mode)
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    folder = backup_folder(runid)
    folder.mkdir(mode=0o700)
    saved = folder / 'services.index.html'
    with saved.open('xb') as stream:
        stream.write(original)
    saved.chmod(0o600)
    manifest = {'old': digest(original), 'new': digest(new), 'mode': mode}
    (folder / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    (folder / 'manifest.json').chmod(0o600)
    if FILE.is_symlink() or digest(FILE.read_bytes()) != manifest['old']:
        raise RuntimeError('REFUSE_CONCURRENT_SERVICE_EDIT')
    atomic_write(FILE, new, mode)
    print('SERVICE_OFFERS_PUBLISHED=1')


def verify(runid: str) -> None:
    validate()
    manifest = json.loads((backup_folder(runid) / 'manifest.json').read_text())
    source = FILE.read_bytes()
    if digest(source) != manifest['new'] or transform(source.decode('utf-8'))[0] != 'already-patched':
        raise RuntimeError('SERVICE_OFFERS_ORIGIN_VERIFY_FAILED')
    print('SERVICE_OFFERS_ORIGIN_VERIFIED=1')


def rollback(runid: str) -> None:
    validate()
    folder = backup_folder(runid)
    manifest = json.loads((folder / 'manifest.json').read_text())
    original = (folder / 'services.index.html').read_bytes()
    if digest(original) != manifest['old'] or digest(FILE.read_bytes()) != manifest['new']:
        raise RuntimeError('REFUSE_UNSAFE_SERVICE_OFFERS_ROLLBACK')
    atomic_write(FILE, original, manifest['mode'])
    print('SERVICE_OFFERS_ROLLBACK_VERIFIED=1')


def selftest() -> None:
    sample = ('<main id="main"><link rel="canonical" href="https://zomorodmelal.ir/services/">'
              + TITLE_OLD + '<meta name="description" content="در این صفحه حوزه‌های قابل بررسی و استعلام جداگ">'
              + ('x' * 11000) + ANCHOR)
    state, output = transform(sample)
    assert state == 'needs-patch' and TITLE_NEW in output and SECTION in output
    assert transform(output)[0] == 'already-patched'
    print('SERVICE_OFFERS_SELFTEST_OK=1')


if __name__ == '__main__':
    args = sys.argv[1:]
    if args == ['selftest']:
        selftest()
    elif args == ['preview']:
        preview()
    elif len(args) == 2 and args[0] in ('publish', 'verify', 'rollback'):
        {'publish': publish, 'verify': verify, 'rollback': rollback}[args[0]](args[1])
    else:
        raise RuntimeError('UNKNOWN_OR_UNSAFE_MODE')
