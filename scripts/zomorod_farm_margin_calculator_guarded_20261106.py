#!/usr/bin/env python3
"""Add a functioning on-page farm gross-margin tool to existing services page.

No user inputs go to a server; no form submissions or customer records touched.
Guarded by SHA-256 of the previously proven live origin, with private backups.
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
SERVICES = WEB / 'services/index.html'
PREDECESSOR = HOME / '.private/zomorod-service-intent-backups/42153111271/manifest.json'
PREDECESSOR_OLD = '3dc3bcc63878e97d2b022c3ad520794d108e86a139929cef1e9601fca46d56b6'
BACKUPS = HOME / '.private/zomorod-farm-margin-backups'
MARKER = 'zm-farm-margin-calculator-20261106'

CALCULATOR = r'''
<!-- zm-farm-margin-calculator-20261106:client-only -->
<section id="zm-farm-margin-calculator-20261106" aria-labelledby="zm-margin-title" class="zm-margin-panel">
 <style>
  .zm-margin-panel{max-width:1120px;margin:28px auto;padding:clamp(18px,3vw,30px);box-sizing:border-box;border:2px solid #b7c8af;border-radius:18px;background:#f6f8ee;color:#173528;font:inherit;line-height:1.85}
  .zm-margin-panel h2{color:#174b38;font-size:clamp(22px,3vw,30px);margin:0 0 8px}
  .zm-margin-panel p{margin:8px 0 14px}
  .zm-margin-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,250px),1fr));gap:16px}
  .zm-margin-panel label{display:block;font-weight:700;margin:0 0 6px}
  .zm-margin-panel input{width:100%;min-height:44px;box-sizing:border-box;border-radius:9px;border:1px solid #729382;padding:10px;font:inherit;color:#173528;background:#fff;direction:ltr;text-align:right}
  .zm-margin-panel input:focus-visible,.zm-margin-panel button:focus-visible,.zm-margin-panel a:focus-visible{outline:3px solid #a76b00;outline-offset:2px}
  .zm-margin-panel button,.zm-margin-panel .zm-margin-cta{display:inline-block;background:#185740;color:#fff;padding:11px 20px;margin:16px 0 4px;border:0;border-radius:9px;font:inherit;font-weight:700;cursor:pointer;text-decoration:none}
  .zm-margin-panel .zm-margin-cta{background:#a76b00}
  .zm-margin-output{white-space:pre-line;background:#e9f4e6;border-inline-start:5px solid #29704b;border-radius:8px;margin:14px 0;padding:16px;font-weight:600}
  .zm-margin-error{color:#912323;font-weight:700;min-height:1em}
  .zm-margin-note{font-size:.94em;color:#355a49}
 </style>
 <h2 id="zm-margin-title">محاسبه‌گر اقتصادی مزرعه: سود ناخالص و نقطهٔ سربه‌سر</h2>
 <p>پیش از سفارش مطالعهٔ اقتصادی، یک برآورد عددی اولیه از فعالیت خود به‌دست آورید. این ابزار آموزشی بر مبنای سطح، عملکرد، قیمت و هزینه‌های اعلامی شما محاسبه می‌کند؛ هیچ داده‌ای ذخیره یا ارسال نمی‌شود.</p>
 <div id="zm-margin-form">
  <div class="zm-margin-grid">
   <div><label for="zm-margin-area">سطح زیرکشت (هکتار)</label><input id="zm-margin-area" name="area" inputmode="decimal" autocomplete="off" maxlength="20" placeholder="مثلاً ۲" required></div>
   <div><label for="zm-margin-yield">عملکرد محصول (کیلوگرم در هکتار)</label><input id="zm-margin-yield" name="yield" inputmode="decimal" autocomplete="off" maxlength="20" placeholder="مثلاً ۵۰۰۰" required></div>
   <div><label for="zm-margin-price">قیمت فروش (تومان برای هر کیلوگرم)</label><input id="zm-margin-price" name="price" inputmode="decimal" autocomplete="off" maxlength="20" placeholder="مثلاً ۲۵۰۰۰" required></div>
   <div><label for="zm-margin-variable">هزینهٔ متغیر (تومان در هکتار)</label><input id="zm-margin-variable" name="variable" inputmode="decimal" autocomplete="off" maxlength="20" placeholder="بذر، نهاده، آب و دستمزد" required></div>
   <div><label for="zm-margin-fixed">هزینهٔ ثابت برآوردی (تومان در هکتار)</label><input id="zm-margin-fixed" name="fixed" inputmode="decimal" autocomplete="off" maxlength="20" placeholder="اجاره و استهلاک؛ اگر ندارد صفر" required></div>
  </div>
  <button id="zm-margin-run" type="button">محاسبهٔ نتیجهٔ اقتصادی</button>
 </div>
 <noscript><p class="zm-margin-note">برای محاسبهٔ خودکار، جاوااسکریپت مرورگر را فعال کنید. ثبت درخواست تخصصی بدون این ابزار هم امکان‌پذیر است.</p></noscript>
 <p id="zm-margin-error" class="zm-margin-error" role="alert"></p>
 <output id="zm-margin-output" class="zm-margin-output" aria-live="polite" hidden></output>
 <p class="zm-margin-note">روش محاسبه: درآمد = سطح × عملکرد × قیمت؛ حاشیهٔ ناخالص = درآمد − هزینهٔ متغیر؛ ماندهٔ برآوردی = درآمد − هزینهٔ متغیر − هزینهٔ ثابت. هزینهٔ سرمایه، مالیات، تأمین مالی، ریسک عملکرد و تغییرات بازار لحاظ نشده‌اند. این اعداد تضمین سود یا پیشنهاد سرمایه‌گذاری نیستند.</p>
 <p><a class="zm-margin-cta" href="/ask-master/index.php?service=1">درخواست تحلیل اقتصادی تخصصی مزرعه</a></p>
</section>
<script>
(function(){
  'use strict';
  var root=document.getElementById('zm-margin-form');
  if(!root){return;}
  var result=document.getElementById('zm-margin-output');
  var error=document.getElementById('zm-margin-error');
  var digits='۰۱۲۳۴۵۶۷۸۹',arabic='٠١٢٣٤٥٦٧٨٩';
  function numberFromUser(value){
    var s=String(value).trim().replace(/[۰-۹]/g,function(d){return String(digits.indexOf(d));})
      .replace(/[٠-٩]/g,function(d){return String(arabic.indexOf(d));})
      .replace(/[٬،,\s]/g,'').replace(/٫/g,'.');
    if(!/^\d+(?:\.\d+)?$/.test(s)){return NaN;}
    return Number(s);
  }
  function fm(value){return new Intl.NumberFormat('fa-IR',{maximumFractionDigits:0}).format(value);}
  function fd(value){return new Intl.NumberFormat('fa-IR',{maximumFractionDigits:2}).format(value);}
  function calculate(area,yieldKg,price,variable,fixed){
    var revenue=area*yieldKg*price;
    var variableTotal=area*variable;
    var fixedTotal=area*fixed;
    return {revenue:revenue,variableTotal:variableTotal,fixedTotal:fixedTotal,
      gross:revenue-variableTotal,remaining:revenue-variableTotal-fixedTotal,
      breakEven:(variable+fixed)/price,
      priceDrop:revenue*0.9-variableTotal-fixedTotal,
      costRise:revenue-variableTotal*1.1-fixedTotal};
  }
  document.getElementById('zm-margin-run').addEventListener('click',function(){
    result.hidden=true;error.textContent='';
    var field=function(name){return numberFromUser(root.querySelector('[name="'+name+'"]').value);};
    var a=field('area'),y=field('yield'),p=field('price'),v=field('variable'),f=field('fixed');
    if(![a,y,p,v,f].every(Number.isFinite)||a<=0||a>10000000||y<0||y>100000000||p<=0||p>1000000000000||v<0||f<0||v>1000000000000000||f>1000000000000000){
      error.textContent='لطفاً پنج مقدار معتبر و غیرمنفی وارد کنید؛ سطح و قیمت باید بزرگ‌تر از صفر باشند.';return;
    }
    var outcome=calculate(a,y,p,v,f);
    if(!Object.keys(outcome).every(function(k){return Number.isFinite(outcome[k]);})){
      error.textContent='اندازهٔ اعداد برای محاسبه بیش‌ازحد بزرگ است.';return;
    }
    result.textContent='درآمد فروش: '+fm(outcome.revenue)+' تومان\n'+
      'هزینهٔ متغیر کل: '+fm(outcome.variableTotal)+' تومان\n'+
      'حاشیهٔ ناخالص: '+fm(outcome.gross)+' تومان\n'+
      'هزینهٔ ثابت کل: '+fm(outcome.fixedTotal)+' تومان\n'+
      'ماندهٔ برآوردی پیش از مالیات و تأمین مالی: '+fm(outcome.remaining)+' تومان\n'+
      'عملکرد سربه‌سر برآوردی: '+fd(outcome.breakEven)+' کیلوگرم در هکتار\n'+
      'مانده در صورت کاهش ۱۰٪ قیمت فروش: '+fm(outcome.priceDrop)+' تومان\n'+
      'مانده در صورت افزایش ۱۰٪ هزینهٔ متغیر: '+fm(outcome.costRise)+' تومان';
    result.hidden=false;
  });
})();
</script>
'''


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def validate() -> None:
    if os.geteuid() == 0 or os.geteuid() != WEB.stat().st_uid:
        raise RuntimeError('FARM_MARGIN_REFUSE_WRONG_SITE_USER')
    for file in (WEB, SERVICES, SERVICES.parent, BACKUPS, BACKUPS.parent, PREDECESSOR):
        if file.is_symlink():
            raise RuntimeError('FARM_MARGIN_REFUSE_SYMLINK')
    if not SERVICES.is_file() or not PREDECESSOR.is_file():
        raise RuntimeError('FARM_MARGIN_MISSING_LIVE_PREDECESSOR')
    boundary = SERVICES.parent / '.htaccess'
    if not boundary.is_file() or 'PassengerEnabled off' not in boundary.read_text():
        raise RuntimeError('FARM_MARGIN_REFUSE_DYNAMIC_ROUTE')


def expected() -> str:
    previous = json.loads(PREDECESSOR.read_text())['services']
    if previous['old_sha'] != PREDECESSOR_OLD:
        raise RuntimeError('FARM_MARGIN_BAD_PREDECESSOR')
    return previous['new_sha']


def transform(value: bytes) -> bytes:
    html = value.decode('utf-8')
    if html.count('</main>') != 1 or MARKER in html:
        raise RuntimeError('FARM_MARGIN_REFUSE_CHANGED_HTML')
    if 'zm-service-deliverables-20261106' not in html or 'zm-specialist-intent-20261106:services' not in html:
        raise RuntimeError('FARM_MARGIN_REFUSE_MISSING_SERVICE_OFFER')
    return html.replace('</main>', CALCULATOR + '</main>', 1).encode('utf-8')


def check() -> tuple[bytes, bytes, int]:
    validate()
    original = SERVICES.read_bytes()
    if sha(original) != expected():
        raise RuntimeError('FARM_MARGIN_REFUSE_CONCURRENT_ORIGIN_EDIT')
    updated = transform(original)
    return original, updated, stat.S_IMODE(SERVICES.stat().st_mode)


def atomic(payload: bytes, mode: int) -> None:
    fd, path = tempfile.mkstemp(prefix='.farm-margin-', dir=str(SERVICES.parent))
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(payload)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(path, mode)
        os.replace(path, SERVICES)
    finally:
        if os.path.exists(path):
            os.unlink(path)


def root(run_id: str) -> Path:
    if not re.fullmatch(r'[0-9]{5,20}', run_id):
        raise RuntimeError('FARM_MARGIN_REFUSE_RUN_ID')
    return BACKUPS / run_id


def rollback(run_id: str) -> None:
    path = root(run_id)
    manifest = json.loads((path / 'manifest.json').read_text())
    original = (path / 'services.backup').read_bytes()
    if sha(original) != manifest['old_sha']:
        raise RuntimeError('FARM_MARGIN_CORRUPT_BACKUP')
    current = sha(SERVICES.read_bytes())
    if current == manifest['new_sha']:
        atomic(original, manifest['mode'])
        print('FARM_MARGIN_ROLLED_BACK=1')
    elif current == manifest['old_sha']:
        print('FARM_MARGIN_ALREADY_ROLLED_BACK=1')
    else:
        raise RuntimeError('FARM_MARGIN_REFUSE_OVERWRITE_OTHER_EDIT')


def publish(run_id: str) -> None:
    original, updated, mode = check()
    BACKUPS.mkdir(mode=0o700, exist_ok=True)
    dest = root(run_id)
    dest.mkdir(mode=0o700)
    with (dest / 'services.backup').open('xb') as out:
        out.write(original)
    (dest / 'services.backup').chmod(0o600)
    manifest = {'old_sha': sha(original), 'new_sha': sha(updated), 'mode': mode}
    (dest / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True))
    (dest / 'manifest.json').chmod(0o600)
    try:
        if sha(SERVICES.read_bytes()) != manifest['old_sha']:
            raise RuntimeError('FARM_MARGIN_CONCURRENT_EDIT_BEFORE_WRITE')
        atomic(updated, mode)
    except Exception:
        rollback(run_id)
        raise
    print('FARM_MARGIN_PUBLISHED=1')


def verify(run_id: str) -> None:
    validate()
    manifest = json.loads((root(run_id) / 'manifest.json').read_text())
    payload = SERVICES.read_bytes()
    if sha(payload) != manifest['new_sha'] or payload.count(MARKER.encode()) != 2:
        raise RuntimeError('FARM_MARGIN_ORIGIN_VERIFY_FAILED')
    print('FARM_MARGIN_ORIGIN_VERIFIED=1')


def selftest() -> None:
    original = b'<main>zm-service-deliverables-20261106 zm-specialist-intent-20261106:services</main>'
    output = transform(original)
    assert output.count(MARKER.encode()) == 2
    assert b'zm-margin-form' in output and b'ask-master/index.php?service=1' in output
    assert b'fetch(' not in CALCULATOR.encode() and b'XMLHttpRequest' not in CALCULATOR.encode()
    node = shutil.which('node')
    if node:
        script = CALCULATOR.split('<script>', 1)[1].split('</script>', 1)[0]
        fd, temp = tempfile.mkstemp(prefix='zm-farm-margin-', suffix='.js')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as out:
                out.write(script)
            if subprocess.run([node, '--check', temp], capture_output=True, timeout=15).returncode:
                raise RuntimeError('FARM_MARGIN_JS_SYNTAX_ERROR')
            harness = r'''
const fs=require('fs'),vm=require('vm');
const js=fs.readFileSync(process.argv[1],'utf8');
const fields={area:{value:'۲'},yield:{value:'۵۰۰۰'},price:{value:'۲۵٬۰۰۰'},
  variable:{value:'۴۰۰۰۰۰۰۰'},fixed:{value:'۱۰۰۰۰۰۰۰'}};
let onclick;
const root={querySelector:(selector)=>fields[selector.match(/name="([^"]+)"/)[1]]};
const output={hidden:true,textContent:''},error={textContent:''};
const button={addEventListener:(event,callback)=>{if(event!=='click')throw Error('not a click');onclick=callback;}};
const document={getElementById:(id)=>({
  'zm-margin-form':root,'zm-margin-run':button,
  'zm-margin-output':output,'zm-margin-error':error})[id]};
vm.runInNewContext(js,{document,Intl,Number,String});
onclick();
if(output.hidden||error.textContent)throw Error('valid numbers rejected');
function normal(s){return s.replace(/[۰-۹]/g,d=>String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))
  .replace(/[٬,\s]/g,'');}
const out=normal(output.textContent);
if(!out.includes('170000000')||!out.includes('150000000')||!out.includes('2000')){
  throw Error('margin/break-even calculation wrong');
}
fields.price.value='۰';onclick();
if(!output.hidden||!error.textContent)throw Error('zero price was accepted');
console.log('FARM_MARGIN_JS_MATH_AND_VALIDATION_OK=1');
'''
            trial = subprocess.run([node, '-e', harness, temp], capture_output=True, timeout=15)
            if trial.returncode:
                raise RuntimeError('FARM_MARGIN_JS_BEHAVIOR_FAILED:' + trial.stderr.decode('utf-8', 'replace')[-500:])
            print(trial.stdout.decode('utf-8', 'replace').strip())
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    print('FARM_MARGIN_SELFTEST_OK=1')


if __name__ == '__main__':
    args = sys.argv[1:]
    if args == ['selftest']:
        selftest()
    elif args == ['preview']:
        old, new, _ = check()
        print('FARM_MARGIN_PREFLIGHT_SHA=' + sha(old))
        print('FARM_MARGIN_TARGET_SHA=' + sha(new))
    elif len(args) == 2 and args[0] in ('publish', 'verify', 'rollback'):
        if args[0] == 'publish':
            publish(args[1])
        elif args[0] == 'verify':
            verify(args[1])
        else:
            validate()
            rollback(args[1])
    else:
        raise RuntimeError('FARM_MARGIN_UNKNOWN_MODE')
