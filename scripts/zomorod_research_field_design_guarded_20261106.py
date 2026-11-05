#!/usr/bin/env python3
"""Guarded static RCBD field-trial planner release, run as the cPanel owner.

No credentials or user-submitted research data are collected. The planner uses
client-side deterministic allocation and creates local CSV/JSON downloads.
"""
from __future__ import annotations

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
TOPICS = WEB / 'topics'
RESEARCH = WEB / 'research'
PAGE = RESEARCH / 'index.html'
ENGINE = TOPICS / 'tools/field-trial-design/index.html'
FILES = (PAGE, ENGINE)
BACKUPS = HOME / '.private/field-trial-design-backups'
URL = '/topics/tools/field-trial-design/'
MARKER = 'zm-field-trial-design-20261106'

ACTION = '''\n<section id="zm-field-trial-design-action-20261106" aria-label="طراحی آزمایش کشاورزی" style="background:#173f30;border:2px solid #d6b46d;border-radius:15px;padding:20px;margin:20px auto;max-width:1140px;color:#fff0cc;line-height:1.85">
 <h2 style="color:#f6d990;margin:0 0 6px">طراحی تصادفی آزمایش مزرعه‌ای</h2>
 <p style="margin:6px 0 12px">تیمارهای آزمایشی، تعداد بلوک‌ها و شناسهٔ بازتولید را وارد کنید؛ نقشهٔ طرح بلوک کامل تصادفی (RCBD) و دفتر ثبت اندازه‌گیری را رایگان دریافت کنید.</p>
 <a href="/topics/tools/field-trial-design/" style="display:inline-block;border-radius:8px;background:#f6d990;color:#153427;padding:8px 13px;font-weight:bold">ساخت نقشه و دریافت فایل آزمایش ←</a>
 <p style="font-size:.88em;margin:12px 0 0">تخصیص تصادفی با دستگاه شما انجام می‌شود؛ اعتبار طرح، تعداد تکرارها و نحوهٔ چینش نهایی باید متناسب با شرایط واقعی زمین بررسی شود.</p>
</section><!-- zm-field-trial-design-20261106:page -->\n'''

ENGINE_HTML = r'''<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>طراحی آزمایش بلوک کامل تصادفی RCBD و نقشه مزرعه | زمرد ملل</title>
<meta name="description" content="ابزار رایگان طراحی آزمایش کشاورزی RCBD؛ تصادفی‌سازی تیمارها در هر بلوک، تولید نقشه قابل تکرار و دانلود CSV و JSON دفتر داده‌ها بدون ارسال اطلاعات.">
<meta name="robots" content="index,follow"><link rel="canonical" href="https://zomorodmelal.ir/topics/tools/field-trial-design/">
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#102b22;color:#f9edd2;font-family:Tahoma,Arial,sans-serif;line-height:1.85}
header,main,footer{width:min(1060px,calc(100% - 24px));margin:auto}header,footer{padding:16px 0}a{color:#f4d28d}h1,h2{color:#f4d28d;line-height:1.5}h1{font-size:clamp(23px,4vw,36px)}
.card{background:#204234;border:1px solid #a99369;border-radius:16px;padding:18px;margin:16px 0}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
label{display:block;line-height:1.6}label span{display:block;margin:2px 0 5px}input,textarea{width:100%;padding:10px;font:inherit;background:#fff;color:#102b22;border:2px solid #d6c49b;border-radius:8px}textarea{min-height:150px;resize:vertical;direction:auto}
button{font:inherit;font-weight:bold;border:2px solid #f0cf89;border-radius:8px;padding:9px 14px;margin:13px 0 0 8px;background:#f0cf89;color:#173a2b;cursor:pointer}button.secondary{background:transparent;color:#f0cf89}
button:focus-visible,input:focus-visible,textarea:focus-visible,a:focus-visible{outline:3px solid #fff;outline-offset:2px}#error{color:#ffd4b8;min-height:1.6em}#results[hidden]{display:none}
.muted{font-size:.9em;color:#e5d6b3}.layout{overflow-x:auto}table{border-collapse:collapse;width:100%;min-width:430px}th,td{border:1px solid #8e9979;padding:7px 10px;text-align:center}th{background:#15382a;color:#f4d28d}td{background:#285440;white-space:normal;max-width:160px;overflow-wrap:anywhere}caption{caption-side:bottom;text-align:right;padding:8px;font-size:.84em}
@media(max-width:640px){.grid{grid-template-columns:1fr}.card{padding:12px}}
</style></head><body>
<header><a href="/">زمرد ملل</a> · <a href="/research/">پژوهش</a> · <a href="/topics/tools/irrigation-planner/">برنامه‌ریزی آبیاری</a></header>
<main><h1>طراحی آزمایش بلوک کامل تصادفی (RCBD)</h1>
<p>در طرح بلوک کامل تصادفی، <strong>هر تیمار دقیقاً یک بار در هر بلوک</strong> قرار می‌گیرد و ترتیب تیمارها به‌طور مستقل درون هر بلوک تصادفی می‌شود. با ثبت شناسهٔ تصادفی‌سازی می‌توانید همان تخصیص را دوباره بسازید؛ هیچ اطلاعاتی به سرور ارسال نمی‌شود.</p>
<form id="design-form" class="card" novalidate>
 <h2>مشخصات طرح و تیمارها</h2>
 <div class="grid">
  <label><span>نام تیمارها، هر سطر یک تیمار (۲ تا ۲۰ تیمار)</span><textarea id="treatments" required>شاهد
کود آلی
کود معدنی
تغذیه ترکیبی</textarea></label>
  <div>
   <label><span>تعداد بلوک یا تکرار مستقل (۲ تا ۲۰)</span><input id="blocks" type="number" min="2" max="20" step="1" value="4" required></label>
   <label><span>شناسهٔ تصادفی‌سازی برای بازتولید (Seed)</span><input id="seed" type="text" maxlength="80" value="ZM-RCBD-1405-01" autocomplete="off" required></label>
   <p class="muted">تعداد کرت‌ها = تعداد تیمارها × تعداد بلوک‌ها. عنوان‌ها باید یکتا باشند. ترتیب جدول «موقعیت‌های فرضی» است و جای‌گذاری فیزیکی باید با شیب، خاک و مسیر ماشین‌آلات هماهنگ شود.</p>
  </div>
 </div>
 <button type="submit">ساخت نقشهٔ تصادفی</button><button type="reset" class="secondary">بازنشانی</button><p id="error" role="alert" aria-live="assertive"></p>
</form>
<section class="card" id="results" hidden aria-live="polite">
 <h2>نقشهٔ قابل بازتولید</h2><p id="summary"></p>
 <div id="layout" class="layout" aria-label="جدول تیمارها در بلوک‌ها"></div>
 <button id="csv" type="button">دریافت CSV و دفتر داده</button><button id="json" type="button" class="secondary">دریافت JSON طرح</button>
 <p class="muted">در CSV ستون‌های اندازه‌گیری و یادداشت خالی‌اند تا داده‌های واقعی پس از اجرای آزمایش ثبت شوند. هر ستون جدول، یک موقعیت فرضی در بلوک است؛ هر ردیف، یک بلوک کامل.</p>
</section>
<section class="card"><h2>روش علمی، حدود کاربرد و منابع</h2>
 <p>ابتدا پرسش، متغیر پاسخ و واحد آزمایشی مستقل را مشخص کنید. بلوک‌ها را در بخش‌هایی از زمین تعریف کنید که شرایط داخلی نسبتاً مشابه دارند؛ سپس همهٔ تیمارها را داخل هر بلوک به‌صورت تصادفی تخصیص دهید. اندازه‌گیری چندباره از یک کرت، جای تکرار مستقل را نمی‌گیرد.</p>
 <p>این ابزار فقط تخصیص تصادفی و دفتر ثبت را تولید می‌کند؛ <strong>محاسبهٔ توان آماری، کفایت تکرار، تحلیل واریانس، اثرات مجاورت، حفاظت زیستی، رضایت/مجوز پژوهش و اعتبار علمی نتایج</strong> را بررسی یا تأیید نمی‌کند. برای شیب‌های چندگانه، کرت‌های خردشده، تیمارهای ناسازگار یا طرح‌های پیچیده از طراحی تخصصی استفاده کنید. شناسهٔ ثابت صرفاً قابلیت بازتولید می‌دهد و برای کورسازی امنیتی یا پژوهش حساس مناسب نیست.</p>
 <p>منابع آموزشی: <a href="https://www.itl.nist.gov/div898/handbook/pri/section3/pri332.htm" rel="noopener noreferrer">NIST: Randomized Block Designs</a> · <a href="https://extension.psu.edu/conducting-on-farm-research" rel="noopener noreferrer">Penn State Extension: Conducting On-Farm Research</a> · <a href="https://online.stat.psu.edu/stat503/Lesson04" rel="noopener noreferrer">Penn State: Design of Experiments</a>.</p>
 <p><a href="/research/">بازگشت به پژوهش</a> · <a href="/topics/">دانشنامه تخصصی</a></p>
</section></main><footer>شرکت کشت و صنعت زمرد ملل · ابزار رایگان، محلی و بدون نیاز به حساب کاربری</footer>
<script>
(()=>{'use strict';
const $=id=>document.getElementById(id),form=$('design-form'),error=$('error'),results=$('results');let exportData=null;
function hash(value){let h=2166136261;for(const b of new TextEncoder().encode(value)){h=Math.imul(h^b,16777619)>>>0;}return h||0x9e3779b9}
function rand(state){let x=state>>>0;return ()=>{x^=x<<13;x^=x>>>17;x^=x<<5;return (x>>>0)}}
function uniform(next,n){const limit=Math.floor(4294967296/n)*n;let x;do{x=next()}while(x>=limit);return x%n}
function allocate(names,blocks,seed){const rows=[];for(let b=1;b<=blocks;b++){const order=names.slice(),next=rand(hash(seed+'|'+b));for(let j=order.length-1;j>0;j--){const k=uniform(next,j+1);[order[j],order[k]]=[order[k],order[j]]}for(let p=0;p<order.length;p++)rows.push({plotId:'B'+String(b).padStart(2,'0')+'-P'+String(p+1).padStart(2,'0'),block:b,position:p+1,treatment:order[p],measurement:'',unit:'',notes:''})}return rows}
function fail(message){error.textContent=message;results.hidden=true;exportData=null}
function render(){error.textContent='';results.hidden=true;exportData=null;
 const names=$('treatments').value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean),blocks=Number($('blocks').value),seed=$('seed').value.trim();
 if(names.length<2||names.length>20)return fail('بین ۲ تا ۲۰ تیمار غیرخالی را در سطرهای جداگانه وارد کنید.');
 if(names.some(x=>x.length>64))return fail('نام هر تیمار باید حداکثر ۶۴ نویسه باشد.');
 if(new Set(names.map(x=>x.normalize('NFC').toLocaleLowerCase())).size!==names.length)return fail('نام تیمارها نباید تکراری باشد.');
 if(!Number.isInteger(blocks)||blocks<2||blocks>20)return fail('تعداد بلوک باید عدد صحیح بین ۲ تا ۲۰ باشد.');
 if(!seed||seed.length>80)return fail('شناسه تصادفی‌سازی معتبر و حداکثر ۸۰ نویسه وارد کنید.');
 const rows=allocate(names,blocks,seed),table=document.createElement('table'),thead=table.createTHead(),head=thead.insertRow();
 for(const text of ['بلوک',...names.map((_,i)=>'موقعیت '+(i+1))]){const th=document.createElement('th');th.scope='col';th.textContent=text;head.appendChild(th)}
 const body=table.createTBody();for(let b=1;b<=blocks;b++){const tr=body.insertRow(),th=document.createElement('th');th.scope='row';th.textContent='بلوک '+b;tr.appendChild(th);for(const row of rows.filter(r=>r.block===b)){const cell=tr.insertCell();cell.textContent=row.treatment;cell.title=row.plotId}}
 const caption=table.createCaption();caption.textContent='موقعیت‌ها در هر بلوک، مستقل تصادفی شده‌اند. جهت فیزیکی کرت‌ها را جداگانه ثبت کنید.';
 $('layout').replaceChildren(table);$('summary').textContent=names.length+' تیمار × '+blocks+' بلوک = '+rows.length+' کرت؛ شناسه بازتولید: '+seed;
 exportData={design:'Randomized Complete Block Design (RCBD)',version:1,seed,randomizer:'UTF-8 FNV1a32 + xorshift32 + rejection-sampled Fisher-Yates per block',treatments:names,blocks,plots:rows,notes:'Assignment only; validate independent experimental units and field layout before implementation.'};results.hidden=false;
}
function safeCsv(value){let s=String(value??'');if(/^[\s]*[=+@-]/.test(s)||/^[\s]*[\t\r]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"'}
function download(filename,mime,body){const blob=new Blob([body],{type:mime}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=filename;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1200)}
form.addEventListener('submit',e=>{e.preventDefault();render()});form.addEventListener('reset',()=>{error.textContent='';results.hidden=true;exportData=null});
$('csv').addEventListener('click',()=>{if(!exportData)return;const cols=['plotId','block','position','treatment','measurement','unit','notes'];const rows=[cols,...exportData.plots.map(p=>cols.map(k=>p[k]))];download('zomorod-rcbd-field-plan.csv','text/csv;charset=utf-8','\ufeff'+rows.map(r=>r.map(safeCsv).join(',')).join('\r\n'))});
$('json').addEventListener('click',()=>{if(!exportData)return;download('zomorod-rcbd-field-plan.json','application/json;charset=utf-8',JSON.stringify(exportData,null,2))});
})();
</script><!-- zm-field-trial-design-20261106:engine --></body></html>
'''


def validate():
    if os.geteuid() == 0 or os.geteuid() != WEB.stat().st_uid:
        raise RuntimeError('REFUSE_WRONG_USER')
    for directory in (TOPICS, RESEARCH):
        if directory.is_symlink() or not directory.is_dir():
            raise RuntimeError('UNSAFE_STATIC_DIRECTORY:' + str(directory))
        if 'PassengerEnabled off' not in (directory / '.htaccess').read_text(encoding='utf-8'):
            raise RuntimeError('PASSENGER_STATIC_BOUNDARY_MISSING:' + str(directory))
    if BACKUPS.is_symlink() or BACKUPS.parent.is_symlink():
        raise RuntimeError('UNSAFE_BACKUP_ROOT')
    if not PAGE.is_file():
        raise RuntimeError('MISSING_RESEARCH_PAGE')
    if any(path.is_symlink() for path in FILES):
        raise RuntimeError('UNSAFE_TARGET_SYMLINK')


def transform(path, source):
    if path == ENGINE:
        if source is None:
            return 'new-file', ENGINE_HTML
        if source == ENGINE_HTML:
            return 'already-patched', source
        raise RuntimeError('REFUSE_EXISTING_FIELD_TOOL_DRIFT')
    if path != PAGE or source is None:
        raise RuntimeError('UNEXPECTED_PAGE')
    if MARKER + ':page' in source:
        if source.count(MARKER + ':page') != 1 or source.count('id="zm-field-trial-design-action-20261106"') != 1 or source.count(URL) != 1:
            raise RuntimeError('PARTIAL_RESEARCH_PATCH')
        return 'already-patched', source
    if MARKER in source or URL in source or source.count('<main id="main">') != 1:
        raise RuntimeError('UNSAFE_RESEARCH_PAGE_DRIFT')
    if 'RESEARCH · EVIDENCE · PRACTICE' not in source or source.count('<link rel="canonical"') != 1 or source.count('</main>') != 1:
        raise RuntimeError('RESEARCH_PAGE_STRUCTURE_CHANGED')
    return 'needs-patch', source.replace('<main id="main">', '<main id="main">' + ACTION, 1)


def inspect():
    result = []
    for path in FILES:
        source = None if path == ENGINE and not path.exists() else path.read_text(encoding='utf-8')
        result.append((path, *transform(path, source), source))
    return result


def backup_folder(runid):
    if not re.fullmatch(r'[0-9]{5,20}', runid):
        raise RuntimeError('INVALID_RUN_ID')
    BACKUPS.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(BACKUPS, 0o700)
    folder = BACKUPS / runid
    if folder.is_symlink():
        raise RuntimeError('UNSAFE_BACKUP_SYMLINK')
    return folder


def atomic_write(path, data, mode):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    fd, temp = tempfile.mkstemp(prefix='.field-trial-design-', dir=str(path.parent))
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


def publish(runid):
    changes = [item for item in inspect() if item[1] != 'already-patched']
    folder = backup_folder(runid)
    if folder.exists():
        raise RuntimeError('BACKUP_RUN_COLLISION')
    folder.mkdir(mode=0o700)
    entries = []
    for path, state, content, source in changes:
        relative = str(path.relative_to(WEB))
        destination = folder / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream:
            stream.write(b'' if source is None else source.encode('utf-8'))
        destination.chmod(0o600)
        entries.append({'path': relative, 'new': state == 'new-file', 'mode': 0o644 if source is None else stat.S_IMODE(path.stat().st_mode)})
    (folder / 'manifest.json').write_text(json.dumps(entries), encoding='utf-8')
    completed = []
    try:
        for path, state, content, source in changes:
            mode = next(e['mode'] for e in entries if e['path'] == str(path.relative_to(WEB)))
            atomic_write(path, content.encode('utf-8'), mode)
            completed.append((path, state, source, mode))
    except Exception:
        for path, state, source, mode in reversed(completed):
            if state == 'new-file':
                if path.read_text(encoding='utf-8') == ENGINE_HTML:
                    path.unlink()
            else:
                atomic_write(path, source.encode('utf-8'), mode)
        raise
    print('FIELD_TRIAL_PUBLISHED_FILES=' + str(len(changes)))


def verify_origin():
    for path in FILES:
        if transform(path, path.read_text(encoding='utf-8'))[0] != 'already-patched':
            raise RuntimeError('ORIGIN_NOT_PATCHED:' + str(path))
    print('FIELD_TRIAL_ORIGIN_OK=2')
    verify_public()


def verify_public():
    checks = {'/research/': [MARKER + ':page', URL], URL: [MARKER + ':engine', 'id="design-form"', 'id="layout"', 'NIST: Randomized Block Designs']}
    for attempt in range(7):
        try:
            for path, tokens in checks.items():
                request = Request('https://zomorodmelal.ir' + path, headers={'User-Agent': 'Zomorod-Field-Trial-Release/1.0', 'Cache-Control': 'no-cache'})
                with urlopen(request, timeout=30) as response:
                    body = response.read(1100000).decode('utf-8', 'replace')
                    if response.status != 200:
                        raise RuntimeError('PUBLIC_HTTP:' + path)
                    for token in tokens:
                        if token not in body:
                            raise RuntimeError('PUBLIC_MISSING:' + path + ':' + token)
            print('FIELD_TRIAL_PUBLIC_OK=2')
            return
        except Exception:
            if attempt == 6:
                raise
            time.sleep(5)


def rollback(runid):
    folder = backup_folder(runid)
    entries = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
    for item in entries:
        path = WEB / item['path']
        if path.is_symlink() or transform(path, path.read_text(encoding='utf-8'))[0] != 'already-patched':
            raise RuntimeError('REFUSE_ROLLBACK_DRIFT:' + item['path'])
    for item in entries:
        path = WEB / item['path']
        if item['new']:
            path.unlink()
        else:
            atomic_write(path, (folder / item['path']).read_bytes(), item['mode'])
    print('FIELD_TRIAL_ROLLED_BACK=' + str(len(entries)))


def selftest():
    source = '<head><link rel="canonical" href="x"></head><main id="main"><span>RESEARCH · EVIDENCE · PRACTICE</span></main>'
    state, patched = transform(PAGE, source)
    assert state == 'needs-patch' and transform(PAGE, patched)[0] == 'already-patched'
    assert transform(ENGINE, None)[0] == 'new-file' and transform(ENGINE, ENGINE_HTML)[0] == 'already-patched'
    print('FIELD_TRIAL_SELFTEST_OK=1')


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'selftest':
        selftest()
        sys.exit(0)
    validate()
    if len(sys.argv) == 2 and sys.argv[1] == 'preview':
        print('FIELD_TRIAL_PREVIEW=' + json.dumps({str(path.relative_to(WEB)): state for path, state, _, _ in inspect()}, sort_keys=True))
    elif len(sys.argv) == 3 and sys.argv[1] == 'publish':
        publish(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == 'verify-origin':
        verify_origin()
    elif len(sys.argv) == 3 and sys.argv[1] == 'rollback':
        rollback(sys.argv[2])
    else:
        raise RuntimeError('UNKNOWN_MODE')
