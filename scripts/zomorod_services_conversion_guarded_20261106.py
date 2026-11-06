#!/usr/bin/env python3
"""Make the real Zomorod services page actionable, without changing backends.

This script touches exactly /home/zomorod2/public_html/services/index.html.
It only links existing request/tracking and locally computed utilities, and
backs up exact previous bytes before replacement.  No forms are submitted.
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
WEB = HOME/'public_html'
ROUTE = WEB/'services'
FILE = ROUTE/'index.html'
BACKUPS = HOME/'.private/services-conversion-backups'
MARKER = 'zm-services-conversion-20261106'
ANCHOR = '<main id="main">'

PANEL = '''\n<aside id="zm-services-action-hub-20261106" role="region" aria-label="امکانات واقعی خدمات زمرد ملل" style="box-sizing:border-box;max-width:1150px;margin:20px auto;padding:20px;background:#173d2f;color:#fff0ce;border:2px solid #c0a979;border-radius:17px;font-family:inherit;line-height:1.9">
 <h2 style="color:#f6d89a;margin:0 0 6px;font-size:clamp(21px,2.5vw,28px)">از معرفی خدمات تا اقدام مشخص</h2>
 <p style="margin:4px 0 14px">موضوع خود را برای بررسی اولیه ثبت کنید، درخواست قبلی را پیگیری کنید یا با ابزارهای رایگان حجم آب و اقتصاد پروژه را برآورد کنید.</p>
 <nav aria-label="درخواست و ابزارهای عملی" style="display:flex;flex-wrap:wrap;gap:11px">
  <a href="/ask-master/index.php" style="display:inline-block;padding:8px 13px;background:#f6d89a;color:#19372a;border-radius:8px;font-weight:bold;text-decoration:none">ثبت پرسش یا استعلام خدمات ←</a>
  <a href="/ask-master/status.php" style="display:inline-block;padding:8px 13px;color:#fff1cf;border:1px solid #e2c98e;border-radius:8px">پیگیری درخواست ←</a>
  <a href="/topics/tools/project-economics/" style="display:inline-block;padding:8px 13px;color:#fff1cf;border:1px solid #e2c98e;border-radius:8px">محاسبهٔ اقتصادی رایگان ←</a>
  <a href="/topics/tools/irrigation-planner/" style="display:inline-block;padding:8px 13px;color:#fff1cf;border:1px solid #e2c98e;border-radius:8px">محاسبهٔ نیاز آبی رایگان ←</a>
 </nav>
 <p style="font-size:.87em;margin:12px 0 0">ثبت درخواست، به معنی پذیرش قطعی پروژه، اعلام قیمت یا تعهد به انجام خدمت نیست. نتیجهٔ بررسی از مسیر رسمی اطلاع‌رسانی می‌شود.</p>
</aside><!-- zm-services-conversion-20261106 -->\n'''

def validate():
    if os.geteuid()==0 or os.geteuid()!=WEB.stat().st_uid:
        raise RuntimeError('REFUSE_WRONG_USER')
    if ROUTE.is_symlink() or FILE.is_symlink() or not FILE.is_file():
        raise RuntimeError('UNSAFE_SERVICES_FILE')
    if 'PassengerEnabled off' not in (ROUTE/'.htaccess').read_text(encoding='utf-8'):
        raise RuntimeError('STATIC_SERVICES_BOUNDARY_CHANGED')
    if BACKUPS.is_symlink() or BACKUPS.parent.is_symlink():
        raise RuntimeError('UNSAFE_BACKUP_ROOT')

def transform(source):
    if MARKER in source:
        if source.count(MARKER)!=1 or source.count('id="zm-services-action-hub-20261106"')!=1:
            raise RuntimeError('PARTIAL_SERVICES_PATCH')
        if source.count(ANCHOR)!=1 or source.count('<link rel="canonical"')!=1:
            raise RuntimeError('SERVICES_STRUCTURE_CHANGED')
        return 'already-patched',source
    if source.count(ANCHOR)!=1 or source.count('<link rel="canonical"')!=1:
        raise RuntimeError('SERVICES_STRUCTURE_CHANGED')
    if 'خدمات و حوزه‌های تخصصی | زمرد ملل' not in source or 'هر خدمت، با یک' not in source:
        raise RuntimeError('SERVICES_CONTENT_CHANGED')
    if 'زمرد' not in source or source.count('</main>')!=1:
        raise RuntimeError('SERVICES_MAIN_MISSING')
    return 'needs-patch',source.replace(ANCHOR,ANCHOR+PANEL,1)

def atomic(path,data,mode):
    fd,tmp=tempfile.mkstemp(prefix='.zm-services-',dir=str(path.parent))
    try:
        with os.fdopen(fd,'wb') as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,mode)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def folder(runid):
    if not re.fullmatch(r'[0-9]{5,20}',runid):raise RuntimeError('INVALID_RUN_ID')
    BACKUPS.mkdir(mode=0o700,parents=True,exist_ok=True)
    os.chmod(BACKUPS,0o700)
    target=BACKUPS/runid
    if target.is_symlink():raise RuntimeError('BACKUP_SYMLINK')
    return target

def publish(runid):
    source=FILE.read_bytes()
    mode=stat.S_IMODE(FILE.stat().st_mode)
    state,new=transform(source.decode('utf-8'))
    if state=='already-patched':print('SERVICES_ALREADY_PATCHED=1');return
    target=folder(runid)
    target.mkdir(mode=0o700)
    original=target/'services.index.html'
    with original.open('xb') as f:f.write(source)
    original.chmod(0o600)
    (target/'manifest.json').write_text(json.dumps({'sha256':hashlib.sha256(source).hexdigest(),'mode':mode}),encoding='utf-8')
    atomic(FILE,new.encode('utf-8'),mode)
    print('SERVICES_ACTION_PANEL_PUBLISHED=1')

def verify_origin():
    state,_=transform(FILE.read_text(encoding='utf-8'))
    if state!='already-patched':raise RuntimeError('ORIGIN_SERVICES_NOT_PATCHED')
    print('SERVICES_ORIGIN_VERIFIED=1')

def verify_public():
    for attempt in range(7):
        try:
            url='https://zomorodmelal.ir/services/?zm_services_verify=20261106'
            req=Request(url,headers={'User-Agent':'Zomorod-Services-Conversion/1.0','Cache-Control':'no-cache'})
            with urlopen(req,timeout=28) as r:
                body=r.read(800000).decode('utf-8','replace')
                assert r.status==200
            for token in (MARKER,'id="zm-services-action-hub-20261106"','href="/ask-master/index.php"','href="/ask-master/status.php"','href="/topics/tools/irrigation-planner/"'):
                if token not in body:raise RuntimeError('PUBLIC_TOKEN_MISSING:'+token)
            print('SERVICES_PUBLIC_VERIFIED=1');return
        except Exception:
            if attempt==6:raise
            time.sleep(5)

def rollback(runid):
    target=folder(runid)
    meta=json.loads((target/'manifest.json').read_text(encoding='utf-8'))
    original=(target/'services.index.html').read_bytes()
    if hashlib.sha256(original).hexdigest()!=meta['sha256']:
        raise RuntimeError('INVALID_BACKUP_HASH')
    if transform(FILE.read_text(encoding='utf-8'))[0]!='already-patched':
        raise RuntimeError('REFUSE_ROLLBACK_DRIFT')
    atomic(FILE,original,meta['mode'])
    print('SERVICES_ROLLBACK_RESTORED=1')

def selftest():
    before='<html><head><title>خدمات و حوزه‌های تخصصی | زمرد ملل</title><link rel="canonical" href="x"></head><body><main id="main"><h1>هر خدمت، با یک انتخاب</h1></main></body></html>'
    state,after=transform(before)
    assert state=='needs-patch' and after.count(MARKER)==1
    assert transform(after)[0]=='already-patched'
    assert len(after)>len(before) and '/ask-master/index.php' in after
    print('SERVICES_SELFTEST_OK=1')

if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='selftest':selftest();sys.exit(0)
    validate()
    if len(sys.argv)==2 and sys.argv[1]=='preview':
        print('SERVICES_PREVIEW='+transform(FILE.read_text(encoding='utf-8'))[0])
    elif len(sys.argv)==3 and sys.argv[1]=='publish':publish(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=='verify-origin':verify_origin();verify_public()
    elif len(sys.argv)==3 and sys.argv[1]=='rollback':rollback(sys.argv[2])
    else:raise RuntimeError('UNKNOWN_MODE')
