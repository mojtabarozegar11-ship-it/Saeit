#!/usr/bin/env python3
"""Guarded single-page industry OEE utility release via authenticated cPanel.

Only modifies the public static industry landing page and adds a browser-only tool.
Does not handle purchases, client records, live industrial control or Django.
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
ROOT = WEB / 'topics'
PAGE = WEB / 'industry/index.html'
ENGINE = ROOT / 'tools/production-oee/index.html'
FILES = [PAGE, ENGINE]
BACKUPS = HOME / '.private/production-oee-release-backups'
URL = '/topics/tools/production-oee/'
MARKER = 'zm-production-oee-20261106'

ACTION = '''\n+<aside id="zm-production-oee-action-20261106" aria-label="محاسبه عملکرد واقعی تولید" style="background:#173f30;border:2px solid #d6b46d;border-radius:15px;padding:20px;margin:20px auto;max-width:1140px;color:#fff0cc;line-height:1.85">
 <h2 style="color:#f6d990;margin:0 0 6px">محاسبهٔ واقعی بهره‌وری خط تولید</h2>
 <p style="margin:6px 0 12px">با زمان تولید برنامه‌ریزی‌شده، توقف‌ها، سرعت استاندارد و تعداد محصولات سالم، شاخص OEE، ضایعات، ظرفیت مؤثر و بهای تمام‌شده هر واحد سالم را محاسبه کنید.</p>
 <nav aria-label="ابزارهای بهره‌وری صنعتی" style="display:flex;flex-wrap:wrap;gap:12px">
  <a href="/topics/tools/production-oee/" style="display:inline-block;border-radius:8px;background:#f6d990;color:#153427;padding:8px 13px;font-weight:bold">محاسبه OEE و ظرفیت واقعی ←</a>
  <a href="/topics/tools/farm-risk/" style="display:inline-block;border:1px solid #e4c98c;border-radius:8px;color:#ffe6b7;padding:8px 13px">تحلیل سود و ریسک ←</a>
  <a href="/ask-master/index.php" style="display:inline-block;border:1px solid #e4c98c;border-radius:8px;color:#ffe6b7;padding:8px 13px">ثبت استعلام خدمات ←</a>
 </nav>
 <p style="font-size:.86em;margin:12px 0 0">محاسبه صرفاً با دادهٔ کاربر انجام می‌شود و به معنای گواه کیفیت، ظرفیت تأییدشده یا پیشنهاد خرید تجهیزات نیست.</p>
</aside><!-- zm-production-oee-20261106:page -->\n+'''

ENGINE_HTML = '''<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>محاسبه‌گر OEE، ظرفیت تولید و هزینه واحد سالم | زمرد ملل</title>
<meta name="description" content="محاسبه آنلاین و رایگان OEE، دسترس‌پذیری، عملکرد، کیفیت، ضایعات، تولید قابل فروش و بهای واحد سالم با اطلاعات خط تولید شما.">
<meta name="robots" content="index,follow"><link rel="canonical" href="https://zomorodmelal.ir/topics/tools/production-oee/">
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#102b22;color:#f9edd2;font-family:Tahoma,Arial,sans-serif;line-height:1.8}
header,main,footer{width:min(1020px,calc(100% - 24px));margin:auto}header,footer{padding:16px 0}a{color:#f4d28d}h1,h2{color:#f4d28d;line-height:1.5}h1{font-size:clamp(23px,4vw,36px)}
.card{background:#204234;border:1px solid #a99369;border-radius:16px;padding:18px;margin:16px 0}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
label{display:block;line-height:1.6}label span{display:block;margin:2px 0 5px}input{width:100%;padding:10px;font:inherit;background:#fff;color:#102b22;border:2px solid #d6c49b;border-radius:8px}
button{font:inherit;font-weight:bold;border:2px solid #f0cf89;border-radius:8px;padding:9px 14px;margin:13px 0 0 8px;background:#f0cf89;color:#173a2b;cursor:pointer}button.secondary{background:transparent;color:#f0cf89}
button:focus-visible,input:focus-visible,a:focus-visible{outline:3px solid #fff;outline-offset:2px}#error{color:#ffd4b8;min-height:1.6em}#results[hidden]{display:none}
dl{display:grid;grid-template-columns:1fr auto;gap:4px 18px}dt,dd{margin:0;padding:9px 0;border-bottom:1px solid #ffffff30}dd{text-align:left;font-weight:bold;font-variant-numeric:tabular-nums}p.note{font-size:.9em}
@media(max-width:620px){.grid{grid-template-columns:1fr}.card{padding:13px}dl{grid-template-columns:1fr}dd{text-align:right;padding-top:0}dt{border:0;padding-bottom:0}}
</style></head><body>
<header><a href="/">زمرد ملل</a> · <a href="/industry/">صنعت</a> · <a href="/topics/tools/farm-risk/">تحلیل سود و ریسک</a></header>
<main><h1>محاسبه بهره‌وری واقعی خط تولید (OEE)</h1>
<p>برای <strong>یک خط، یک محصول و یک بازهٔ زمانی یکسان</strong>، اطلاعات تولید را وارد کنید. OEE حاصل‌ضرب دسترس‌پذیری، عملکرد و کیفیت است. همهٔ محاسبات در مرورگر شما انجام می‌شود و ورودی‌ها به سرور ارسال نمی‌شوند.</p>
<form class="card" id="oee-form" novalidate><h2>داده‌های واقعی دوره</h2>
 <div class="grid">
  <label><span>زمان برنامه‌ریزی‌شده تولید (دقیقه)</span><input type="number" id="planned" min="0.01" max="10000000" step="any" value="480" required></label>
  <label><span>توقف تولید در همان دوره (دقیقه)</span><input type="number" id="stop" min="0" max="10000000" step="any" value="45" required></label>
  <label><span>زمان چرخه ایده‌آل هر قطعه (ثانیه)</span><input type="number" id="cycle" min="0.0001" max="10000000" step="any" value="120" required></label>
  <label><span>کل قطعات تولیدشده (عدد)</span><input type="number" id="total" min="1" max="1000000000" step="1" value="200" required></label>
  <label><span>قطعات سالم در اولین عبور (عدد)</span><input type="number" id="good" min="0" max="1000000000" step="1" value="190" required></label>
  <label><span>هزینه کل همین دوره (تومان؛ اختیاری)</span><input type="number" id="cost" min="0" max="1000000000000000" step="any" value="15000000"></label>
 </div>
 <button type="submit">محاسبه OEE و هزینه</button><button type="reset" class="secondary">بازنشانی مقادیر</button><p id="error" role="alert" aria-live="assertive"></p>
</form>
<section id="results" class="card" aria-live="polite" hidden><h2>خروجی عملکرد دوره</h2><dl>
 <dt>زمان واقعی کارکرد</dt><dd id="runtime"></dd>
 <dt>دسترس‌پذیری (Availability)</dt><dd id="availability"></dd>
 <dt>عملکرد سرعت (Performance)</dt><dd id="performance"></dd>
 <dt>کیفیت عبور اول (Quality)</dt><dd id="quality"></dd>
 <dt>اثربخشی کلی تجهیزات (OEE)</dt><dd id="oee-value"></dd>
 <dt>ظرفیت ایده‌آل دوره (قطعه)</dt><dd id="capacity"></dd>
 <dt>تعداد سالم / معیوب</dt><dd id="counts"></dd>
 <dt>نرخ ضایعات</dt><dd id="scrap"></dd>
 <dt>نرخ محصول سالم در ساعت برنامه‌ریزی‌شده</dt><dd id="good-rate"></dd>
 <dt>بهای هر قطعه سالم (در صورت ورود هزینه)</dt><dd id="unit-cost"></dd>
 </dl><button type="button" id="download">دریافت گزارش JSON</button></section>
<section class="card"><h2>مبانی علمی و محدودیت‌ها</h2>
 <p><strong>A</strong> = زمان کارکرد ÷ زمان برنامه‌ریزی‌شده؛ <strong>P</strong> = زمان چرخه ایده‌آل × تعداد کل قطعات ÷ زمان کارکرد؛ <strong>Q</strong> = قطعات سالم در اولین عبور ÷ کل قطعات؛ <strong>OEE</strong> = A × P × Q. تعداد ظرفیت ایده‌آل، تعداد نظری حاصل از زمان برنامه‌ریزی‌شده ÷ زمان چرخه است.</p>
 <p>بهای واحد سالم = هزینهٔ واردشده برای همین دوره ÷ تعداد قطعات سالم. این بهای محاسباتی فقط زمانی معنی‌دار است که هزینه کل، همه هزینه‌های مرتبط انتخابی شما را دربرگیرد؛ مالیات، سرمایه‌گذاری و قیمت فروش جداگانه مدل نشده‌اند.</p>
 <p>منابع: <a href="https://nvlpubs.nist.gov/nistpubs/ams/NIST.AMS.100-18.pdf" rel="noopener noreferrer">NIST: Costs and Benefits of Advanced Maintenance in Manufacturing</a> · <a href="https://www.lean.org/lexicon-terms/overall-equipment-effectiveness/" rel="noopener noreferrer">Lean Enterprise Institute: OEE</a>.</p>
 <p class="note">این ابزار طراحی صنعتی، صدور گواهی، استاندارد ایمنی، ممیزی کیفیت یا کنترل لحظه‌ای ماشین‌آلات نیست. زمان چرخه ایده‌آل باید از شواهد فنی همان محصول و خط انتخاب شود. عملکرد بالای ۱۰۰٪ علامت ناسازگاری ورودی‌هاست و برای جلوگیری از نتیجه گمراه‌کننده رد می‌شود. ضایعات این ابزار فقط قطعات معیوب عبور اول است؛ دوباره‌کاری جداگانه مدل نشده است.</p>
 <p><a href="/ask-master/index.php">ثبت درخواست بررسی خط تولید</a> · <a href="/topics/tools/farm-risk/">تحلیل اقتصادی سه سناریو</a></p>
</section></main>
<footer>شرکت کشت و صنعت زمرد ملل · محاسبه رایگان و محلی · <a href="/services/">خدمات</a></footer>
<script>
(()=>{'use strict';const form=document.getElementById('oee-form'),error=document.getElementById('error'),results=document.getElementById('results');let report=null;
const el=id=>document.getElementById(id),format=n=>new Intl.NumberFormat('fa-IR',{maximumFractionDigits:2}).format(n),pct=n=>format(n*100)+'٪';
const read=(id,optional=false)=>{const e=el(id),raw=e.value.trim();if(!raw){if(optional)return null;throw Error('ورودی «'+e.parentElement.textContent.trim()+'» خالی است.')}const n=Number(raw);if(!Number.isFinite(n)||n<Number(e.min)||n>Number(e.max)||(e.step==='1'&&!Number.isInteger(n)))throw Error('ورودی «'+e.parentElement.textContent.trim()+'» معتبر نیست.');return n};
const put=(id,value)=>{el(id).textContent=value};
form.addEventListener('submit',event=>{event.preventDefault();error.textContent='';results.hidden=true;report=null;
try{const planned=read('planned'),stop=read('stop'),cycle=read('cycle'),total=read('total'),good=read('good'),cost=read('cost',true);if(stop>=planned)throw Error('توقف باید کمتر از زمان برنامه‌ریزی‌شده باشد.');if(good>total)throw Error('تعداد قطعات سالم نمی‌تواند از کل تولید بیشتر باشد.');
const runtime=planned-stop,availability=runtime/planned,performance=(cycle*total)/(runtime*60),quality=good/total,oee=availability*performance*quality,capacity=(planned*60)/cycle,scrap=(total-good)/total,goodRate=(good*60)/planned,unitCost=cost!==null&&good>0?cost/good:null;
if(![runtime,availability,performance,quality,oee,capacity,scrap,goodRate].every(Number.isFinite)||performance>1+1e-9)throw Error('سرعت تولید از ظرفیت ایده‌آل بیشتر شده است. واحد زمان یا زمان چرخه استاندارد را بازبینی کنید.');
put('runtime',format(runtime)+' دقیقه');put('availability',pct(availability));put('performance',pct(performance));put('quality',pct(quality));put('oee-value',pct(oee));put('capacity',format(capacity)+' قطعه نظری');put('counts',format(good)+' سالم / '+format(total-good)+' معیوب');put('scrap',pct(scrap));put('good-rate',format(goodRate)+' قطعه/ساعت');put('unit-cost',unitCost===null?'قابل محاسبه نیست':format(unitCost)+' تومان');
report={inputs:{plannedMinutes:planned,downtimeMinutes:stop,idealCycleSeconds:cycle,totalCount:total,firstPassGoodCount:good,periodCostToman:cost},outputs:{runtimeMinutes:runtime,availability,performance,quality,oee,idealPeriodCapacity:capacity,firstPassRejects:total-good,scrapRate:scrap,goodUnitsPerScheduledHour:goodRate,costPerGoodUnitToman:unitCost},formula:'OEE=availability*performance*quality',source:'NIST.AMS.100-18; Lean Enterprise Institute',limitations:'User-supplied single-line first-pass data; illustrative, not a certification.'};results.hidden=false;
}catch(ex){error.textContent=ex.message}});
form.addEventListener('reset',()=>{error.textContent='';results.hidden=true;report=null});
el('download').addEventListener('click',()=>{if(!report)return;const b=new Blob([JSON.stringify(report,null,2)],{type:'application/json;charset=utf-8'}),u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download='zomorod-production-oee.json';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1200)});
})();
</script><!-- zm-production-oee-20261106:engine --></body></html>
'''


def validate():
    if os.geteuid() == 0 or os.geteuid() != WEB.stat().st_uid:
        raise RuntimeError('REFUSE_WRONG_USER')
    for directory in [ROOT, PAGE.parent]:
        if directory.is_symlink() or not directory.is_dir():
            raise RuntimeError('UNSAFE_STATIC_DIRECTORY:' + str(directory))
        if 'PassengerEnabled off' not in (directory / '.htaccess').read_text(encoding='utf-8'):
            raise RuntimeError('PASSENGER_STATIC_BOUNDARY_MISSING:' + str(directory))
    if BACKUPS.is_symlink() or BACKUPS.parent.is_symlink():
        raise RuntimeError('UNSAFE_BACKUP_ROOT')
    for path in FILES:
        if path.is_symlink():
            raise RuntimeError('UNSAFE_TARGET:' + str(path))
    if not PAGE.is_file():
        raise RuntimeError('MISSING_INDUSTRY_PAGE')


def transform(path, source):
    if path == ENGINE:
        if source is None:
            return 'new-file', ENGINE_HTML
        if source == ENGINE_HTML:
            return 'already-patched', source
        raise RuntimeError('REFUSE_EXISTING_OEE_TOOL_DRIFT')
    if path != PAGE or source is None:
        raise RuntimeError('UNEXPECTED_PAGE')
    marker = MARKER + ':page'
    if marker in source:
        if source.count(marker) != 1 or source.count('id="zm-production-oee-action-20261106"') != 1 or source.count(URL) != 1:
            raise RuntimeError('PARTIAL_PAGE_PATCH')
        return 'already-patched', source
    if MARKER in source or URL in source or source.count('<main id="main">') != 1:
        raise RuntimeError('UNSAFE_PAGE_DRIFT')
    if 'INDUSTRY · QUALITY · VALUE CHAIN' not in source or source.count('<link rel="canonical"') != 1 or source.count('</main>') != 1:
        raise RuntimeError('INDUSTRY_PAGE_STRUCTURE_CHANGED')
    return 'needs-patch', source.replace('<main id="main">', '<main id="main">' + ACTION, 1)


def inspect():
    result = []
    for path in FILES:
        source = None if path == ENGINE and not path.exists() else path.read_text(encoding='utf-8')
        state, output = transform(path, source)
        result.append((path, state, source, output))
    return result


def safe_folder(runid):
    if not re.fullmatch('[0-9]{5,20}', runid):
        raise RuntimeError('INVALID_RUN_ID')
    BACKUPS.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(BACKUPS, 0o700)
    path = BACKUPS / runid
    if path.is_symlink():
        raise RuntimeError('UNSAFE_BACKUP_SYMLINK')
    return path


def atomic_write(path, content, mode):
    path.parent.mkdir(mode=0o755, parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.production-oee-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temp, mode)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def publish(runid):
    changes = [item for item in inspect() if item[1] != 'already-patched']
    target = safe_folder(runid)
    if target.exists():
        raise RuntimeError('BACKUP_RUN_COLLISION')
    target.mkdir(mode=0o700)
    entries = []
    for path, state, source, _ in changes:
        name = str(path.relative_to(WEB))
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream:
            stream.write(b'' if source is None else source.encode('utf-8'))
        destination.chmod(0o600)
        entries.append({'path': name, 'new': state == 'new-file', 'mode': 0o644 if source is None else stat.S_IMODE(path.stat().st_mode)})
    (target / 'manifest.json').write_text(json.dumps(entries), encoding='utf-8')
    completed = []
    try:
        for path, state, source, output in changes:
            item = next(entry for entry in entries if entry['path'] == str(path.relative_to(WEB)))
            atomic_write(path, output.encode('utf-8'), item['mode'])
            completed.append((path, state, source, item['mode']))
    except Exception:
        for path, state, source, mode in reversed(completed):
            if state == 'new-file':
                if path.read_text(encoding='utf-8') == ENGINE_HTML:
                    path.unlink()
            else:
                atomic_write(path, source.encode('utf-8'), mode)
        raise
    print('PRODUCTION_OEE_PUBLISHED_FILES=' + str(len(changes)))


def verify_origin():
    for path in FILES:
        if transform(path, path.read_text(encoding='utf-8'))[0] != 'already-patched':
            raise RuntimeError('ORIGIN_NOT_PATCHED:' + str(path))
    print('PRODUCTION_OEE_ORIGIN_OK=' + str(len(FILES)))


def verify_public():
    checks = {'/industry/': [MARKER + ':page', URL], URL: [MARKER + ':engine', 'id="oee-form"', 'id="oee-value"']}
    for attempt in range(7):
        try:
            for path, tokens in checks.items():
                request = Request('https://zomorodmelal.ir' + path, headers={'User-Agent': 'Zomorod-OEE-Publisher/1.0', 'Cache-Control': 'no-cache'})
                with urlopen(request, timeout=30) as response:
                    body = response.read(1100000).decode('utf-8', 'replace')
                    if response.status != 200:
                        raise RuntimeError('PUBLIC_HTTP:' + path)
                for token in tokens:
                    if token not in body:
                        raise RuntimeError('PUBLIC_MISSING:' + path + ':' + token)
            print('PRODUCTION_OEE_PUBLIC_OK=2')
            return
        except Exception:
            if attempt == 6:
                raise
            time.sleep(5)


def rollback(runid):
    folder = safe_folder(runid)
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
    print('PRODUCTION_OEE_ROLLED_BACK=' + str(len(entries)))


def selftest():
    source = '<head><link rel="canonical" href="x"></head><main id="main"><span>INDUSTRY · QUALITY · VALUE CHAIN</span></main>'
    state, patched = transform(PAGE, source)
    assert state == 'needs-patch' and transform(PAGE, patched)[0] == 'already-patched'
    assert transform(ENGINE, None)[0] == 'new-file' and transform(ENGINE, ENGINE_HTML)[0] == 'already-patched'
    print('PRODUCTION_OEE_SELFTEST_OK=1')


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == 'selftest':
        selftest()
        sys.exit(0)
    validate()
    if len(sys.argv) == 2 and sys.argv[1] == 'preview':
        print('PRODUCTION_OEE_PREVIEW=' + json.dumps({str(path.relative_to(WEB)): state for path, state, _, _ in inspect()}, sort_keys=True))
    elif len(sys.argv) == 3 and sys.argv[1] == 'publish':
        publish(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == 'verify-origin':
        verify_origin()
        verify_public()
    elif len(sys.argv) == 3 and sys.argv[1] == 'rollback':
        rollback(sys.argv[2])
    else:
        raise RuntimeError('UNKNOWN_MODE')
