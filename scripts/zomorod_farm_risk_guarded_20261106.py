#!/usr/bin/env python3
"""Release a deterministic three-scenario enterprise budget tool on Zomorod.

Scope: two live public economic pages and one new standalone browser-only tool.
No payments, messages, API keys, orders or Django code are changed.
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

HOME=Path('/home/zomorod2')
WEB=HOME/'public_html'
ROOT=WEB/'topics'
ENGINE=ROOT/'tools/farm-risk/index.html'
BACKUPS=HOME/'.private/farm-risk-release-backups'
URL='/topics/tools/farm-risk/'
MARKER='zm-farm-risk-20261106'
PAGES={'economy':'رصد اقتصاد ایران و جهان','market':'بازار و محصولات'}
FILES=[WEB/slug/'index.html' for slug in PAGES]+[ENGINE]

ACTION='''\n<aside id="zm-farm-risk-action-20261106" aria-label="ابزار تحلیل اقتصادی" style="background:#173f30;border:2px solid #d6b46d;border-radius:15px;padding:20px;margin:20px auto;max-width:1140px;color:#fff0cc;line-height:1.85">
 <h2 style="color:#f6d990;margin:0 0 5px">ابزار عملی تحلیل سود و ریسک</h2>
 <p style="margin:6px 0 12px">برای یک فعالیت کشاورزی، صنعتی یا تجاری، درآمد و هزینهٔ سه سناریو را با احتمال‌های انتخابی خود مقایسه کنید؛ این ابزار از قیمت زنده یا پیش‌بینی بازار استفاده نمی‌کند.</p>
 <nav aria-label="محاسبه‌گرهای اقتصادی" style="display:flex;flex-wrap:wrap;gap:12px">
  <a href="/topics/tools/farm-risk/" style="display:inline-block;border-radius:8px;background:#f6d990;color:#153427;padding:8px 13px;font-weight:bold">تحلیل سود و ریسک سه سناریو ←</a>
  <a href="/topics/tools/project-economics/" style="display:inline-block;border:1px solid #e4c98c;border-radius:8px;color:#ffe6b7;padding:8px 13px">محاسبهٔ نقطهٔ سربه‌سر ←</a>
  <a href="/ask-master/index.php" style="display:inline-block;border:1px solid #e4c98c;border-radius:8px;color:#ffe6b7;padding:8px 13px">ثبت پرسش یا استعلام ←</a>
 </nav>
 <p style="font-size:.87em;margin:12px 0 0">محاسبات، تنها سناریوی اعداد ورودی است و به معنی تضمین درآمد یا ارائهٔ خدمت نیست.</p>
</aside><!-- zm-farm-risk-20261106:page -->\n'''

ENGINE_HTML='''<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>تحلیل سود و ریسک سه‌سناریویی کسب‌وکار | زمرد ملل</title>
<meta name="description" content="محاسبه رایگان بودجه فعالیت کشاورزی و کسب‌وکار در سه سناریو، سود ناخالص و خالص، سود مورد انتظار و احتمال زیان با احتمال‌های ورودی.">
<meta name="robots" content="index,follow"><link rel="canonical" href="https://zomorodmelal.ir/topics/tools/farm-risk/">
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#102b22;color:#f9edd2;font-family:Tahoma,Arial,sans-serif;line-height:1.85}
header,main,footer{width:min(1050px,calc(100% - 24px));margin:auto}header,footer{padding:17px 0}a{color:#f4d28d}h1,h2,h3{color:#f4d28d;line-height:1.5}h1{font-size:clamp(24px,4vw,36px)}
.card{background:#204234;border:1px solid #a99369;border-radius:16px;padding:18px;margin:16px 0}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.scenarios{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
fieldset{min-width:0;border:1px solid #96876c;border-radius:12px;padding:14px}legend{font-weight:bold;color:#f9d591}label{display:block;margin:8px 0;font-size:.95em}input{width:100%;padding:9px;font:inherit;background:#fff;color:#102b22;border:2px solid #d6c49b;border-radius:8px}
button{font:inherit;font-weight:bold;border:2px solid #f0cf89;border-radius:8px;padding:9px 16px;margin:12px 0 0 8px;background:#f0cf89;color:#173a2b;cursor:pointer}button.secondary{background:transparent;color:#f0cf89}
button:focus-visible,input:focus-visible,a:focus-visible{outline:3px solid #fff;outline-offset:2px}#error{color:#ffd4b8;min-height:1.6em}#results[hidden]{display:none}
table{border-collapse:collapse;width:100%;margin:10px 0}td,th{padding:9px;border:1px solid #8d8366;text-align:right}td:last-child{text-align:left;font-variant-numeric:tabular-nums}dl{display:grid;grid-template-columns:1fr auto;gap:6px 15px}dt,dd{margin:0;padding:7px 0;border-bottom:1px solid #ffffff27}dd{text-align:left;font-weight:bold}.note{font-size:.9em}
@media(max-width:850px){.scenarios{grid-template-columns:1fr}}@media(max-width:550px){.grid{grid-template-columns:1fr}.card{padding:12px}td,th{padding:6px;font-size:.86em}}
</style></head><body>
<header><a href="/">زمرد ملل</a> · <a href="/economy/">اقتصاد</a> · <a href="/market/">بازار</a> · <a href="/topics/tools/project-economics/">محاسبهٔ نقطه سربه‌سر</a></header>
<main><h1>تحلیل سه‌سناریویی سود و ریسک فعالیت</h1>
<p>مقادیر درآمد و هزینه را برای یک بازهٔ زمانی یکسان، مثلاً یک فصل یا یک سال، و به تومان وارد کنید. احتمال هر سناریو را خودتان تعیین می‌کنید. محاسبه در مرورگر انجام می‌شود؛ اعداد در سرور ثبت یا ارسال نمی‌شوند.</p>
<form id="risk-form" class="card" novalidate>
 <div class="grid"><label>نام فعالیت<input id="enterprise" maxlength="100" type="text" placeholder="مثلاً گلخانه سبزی در یک فصل"></label><label>دوره بررسی<input id="period" maxlength="80" type="text" placeholder="مثلاً یک فصل؛ در هر سه حالت یکسان"></label></div>
 <div class="scenarios">
  <fieldset><legend>سناریوی نامطلوب</legend><label>احتمال وقوع (درصد)<input id="p0" type="number" min="0" max="100" step="any" required></label><label>درآمد فروش (تومان)<input id="r0" type="number" min="0" max="1000000000000000" step="any" required></label><label>هزینه متغیر (تومان)<input id="v0" type="number" min="0" max="1000000000000000" step="any" required></label><label>هزینه ثابت تخصیصی (تومان)<input id="f0" type="number" min="0" max="1000000000000000" step="any" required></label></fieldset>
  <fieldset><legend>سناریوی محتمل</legend><label>احتمال وقوع (درصد)<input id="p1" type="number" min="0" max="100" step="any" required></label><label>درآمد فروش (تومان)<input id="r1" type="number" min="0" max="1000000000000000" step="any" required></label><label>هزینه متغیر (تومان)<input id="v1" type="number" min="0" max="1000000000000000" step="any" required></label><label>هزینه ثابت تخصیصی (تومان)<input id="f1" type="number" min="0" max="1000000000000000" step="any" required></label></fieldset>
  <fieldset><legend>سناریوی مطلوب</legend><label>احتمال وقوع (درصد)<input id="p2" type="number" min="0" max="100" step="any" required></label><label>درآمد فروش (تومان)<input id="r2" type="number" min="0" max="1000000000000000" step="any" required></label><label>هزینه متغیر (تومان)<input id="v2" type="number" min="0" max="1000000000000000" step="any" required></label><label>هزینه ثابت تخصیصی (تومان)<input id="f2" type="number" min="0" max="1000000000000000" step="any" required></label></fieldset>
 </div><button type="submit">محاسبهٔ بودجه و ریسک</button><button type="reset" class="secondary">پاک‌کردن فرم</button><p id="error" role="alert" aria-live="assertive"></p>
</form>
<section id="results" class="card" aria-live="polite" hidden><h2>خروجی محاسبه</h2><p id="subtitle"></p>
<table><thead><tr><th>سناریو</th><th>حاشیهٔ ناخالص</th><th>سود خالص</th><th>حداقل فروش سربه‌سر*</th></tr></thead><tbody id="rows"></tbody></table>
<dl><dt>سود خالص مورد انتظار (وزنی)</dt><dd id="expected-profit"></dd><dt>حاشیهٔ ناخالص مورد انتظار</dt><dd id="expected-gross"></dd><dt>احتمال زیان در سناریوهای ورودی</dt><dd id="loss-probability"></dd><dt>کمترین سود خالص در سناریوها</dt><dd id="worst-profit"></dd><dt>انحراف معیار سناریویی سود خالص</dt><dd id="profit-sd"></dd></dl>
<button id="download" type="button">دریافت گزارش JSON</button></section>
<section class="card"><h2>روش محاسبه و محدودیت</h2>
<p>حاشیهٔ ناخالص = درآمد − هزینهٔ متغیر؛ سود خالص عملیاتی = حاشیهٔ ناخالص − هزینهٔ ثابت تخصیصی. سود مورد انتظار = مجموع سود هر سناریو ضربدر احتمال آن. احتمال زیان = مجموع احتمال سناریوهای دارای سود خالص منفی. انحراف معیار، پراکندگی همین سه حالت فرضی است.</p>
<p>* فروش سربه‌سر تنها وقتی قابل محاسبه است که درآمد مثبت و نسبت حاشیهٔ ناخالص به درآمد مثبت باشد؛ فرض می‌کند ساختار هزینهٔ متغیر نسبت به فروش ثابت است.</p>
<p>منابع روش بودجه فعالیت کشاورزی: <a href="https://www.fao.org/4/i3229e/i3229e.pdf" rel="noopener noreferrer">FAO: Managing Risk in Farming</a> · <a href="https://www.fao.org/4/a0812e/a0812e05.pdf" rel="noopener noreferrer">FAO: Farm Planning and Enterprise Budgeting</a>.</p>
<p class="note">احتمال‌ها، قیمت‌ها و هزینه‌ها را کاربر وارد می‌کند و تأیید یا پیش‌بینی مستقل نیستند. مالیات، هزینه تأمین مالی، تورم، جریان نقد ماهانه و ریسک‌های خارج از سه حالت در این ابزار مدل نشده‌اند. سود مورد انتظار، تضمین درآمد یا توصیه سرمایه‌گذاری نیست.</p>
<p><a href="/ask-master/index.php">ثبت پرسش یا استعلام</a> · <a href="/topics/tools/project-economics/">محاسبهٔ فعالیت با نقطه سربه‌سر</a></p></section>
</main><footer>شرکت کشت و صنعت زمرد ملل · ابزار رایگان بدون ارسال داده · <a href="/services/">خدمات</a></footer>
<script>
(()=>{'use strict';const form=document.getElementById('risk-form'),error=document.getElementById('error'),results=document.getElementById('results');let report=null;
const el=id=>document.getElementById(id),fmt=n=>new Intl.NumberFormat('fa-IR',{maximumFractionDigits:2}).format(n);
const val=id=>{const x=el(id),name=x.parentElement.textContent.trim();if(!x.value.trim())throw Error('مقدار «'+name+'» را وارد کنید.');const n=Number(x.value);if(!Number.isFinite(n)||n<Number(x.min)||n>Number(x.max))throw Error('مقدار «'+name+'» نامعتبر است.');return n};
const amount=n=>fmt(n)+' تومان';const write=(id,text)=>{el(id).textContent=text};
form.addEventListener('submit',e=>{e.preventDefault();error.textContent='';results.hidden=true;report=null;
try{const names=['نامطلوب','محتمل','مطلوب'],scenarios=names.map((name,i)=>{const probability=val('p'+i),revenue=val('r'+i),variableCost=val('v'+i),fixedCost=val('f'+i);const grossMargin=revenue-variableCost,netProfit=grossMargin-fixedCost,rate=revenue>0?grossMargin/revenue:null,breakEvenRevenue=rate!==null&&rate>0?fixedCost/rate:null;return{name,probability,revenue,variableCost,fixedCost,grossMargin,netProfit,breakEvenRevenue}});
const total=scenarios.reduce((n,s)=>n+s.probability,0);if(Math.abs(total-100)>1e-7)throw Error('مجموع احتمال سه سناریو باید دقیقاً ۱۰۰ درصد باشد؛ مجموع فعلی '+fmt(total)+' درصد است.');
const expectedProfit=scenarios.reduce((n,s)=>n+s.netProfit*s.probability/100,0),expectedGross=scenarios.reduce((n,s)=>n+s.grossMargin*s.probability/100,0);const lossProbability=scenarios.reduce((n,s)=>n+(s.netProfit<0?s.probability:0),0);const variance=scenarios.reduce((n,s)=>n+s.probability/100*(s.netProfit-expectedProfit)**2,0),profitSD=Math.sqrt(variance),worstProfit=Math.min(...scenarios.map(s=>s.netProfit));
if(![expectedProfit,expectedGross,lossProbability,profitSD,worstProfit].every(Number.isFinite))throw Error('اعداد سناریو بیش از محدوده مجاز هستند.');
const rows=el('rows');rows.replaceChildren();for(const s of scenarios){const tr=document.createElement('tr');for(const v of [s.name,amount(s.grossMargin),amount(s.netProfit),s.breakEvenRevenue===null?'قابل محاسبه نیست':amount(s.breakEvenRevenue)]){const td=document.createElement('td');td.textContent=v;tr.appendChild(td)}rows.appendChild(tr)}
write('expected-profit',amount(expectedProfit));write('expected-gross',amount(expectedGross));write('loss-probability',fmt(lossProbability)+'٪');write('worst-profit',amount(worstProfit));write('profit-sd',amount(profitSD));write('subtitle',(el('enterprise').value.trim()||'فعالیت بدون عنوان')+' · '+(el('period').value.trim()||'دورهٔ نامشخص'));
report={activity:el('enterprise').value.trim(),period:el('period').value.trim(),currency:'IRR toman (user-entered)',scenarios,outputs:{expectedProfit,expectedGross,lossProbability,profitSD,worstProfit},method:'Weighted three-scenario enterprise gross margin and net operating profit',source:'FAO enterprise budgeting',warning:'Only user-defined illustrative scenarios; not a forecast.'};results.hidden=false;
}catch(ex){error.textContent=ex.message;}});
form.addEventListener('reset',()=>{error.textContent='';results.hidden=true;report=null});
el('download').addEventListener('click',()=>{if(!report)return;const b=new Blob([JSON.stringify(report,null,2)],{type:'application/json;charset=utf-8'}),u=URL.createObjectURL(b),a=document.createElement('a');a.href=u;a.download='zomorod-farm-risk.json';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(u),1200)});
})();
</script><!-- zm-farm-risk-20261106:engine --></body></html>
'''

def validate():
    if os.geteuid()==0 or os.geteuid()!=WEB.stat().st_uid:raise RuntimeError('REFUSE_WRONG_USER')
    for directory in [ROOT]+[WEB/k for k in PAGES]:
        if directory.is_symlink() or not directory.is_dir():raise RuntimeError('UNSAFE_STATIC_DIRECTORY:'+str(directory))
        if 'PassengerEnabled off' not in (directory/'.htaccess').read_text(encoding='utf-8'):
            raise RuntimeError('PASSENGER_STATIC_BOUNDARY_MISSING:'+str(directory))
    if BACKUPS.is_symlink() or BACKUPS.parent.is_symlink():raise RuntimeError('UNSAFE_BACKUP_ROOT')
    for path in FILES:
        if path.is_symlink():raise RuntimeError('UNSAFE_TARGET:'+str(path))
    if not all(p.is_file() for p in FILES[:-1]):raise RuntimeError('MISSING_EXISTING_PAGE')

def transform(path,source):
    if path==ENGINE:
        if source is None:return 'new-file',ENGINE_HTML
        if source==ENGINE_HTML:return 'already-patched',source
        raise RuntimeError('REFUSE_EXISTING_RISK_TOOL_DRIFT')
    slug=path.parent.name
    if slug not in PAGES:raise RuntimeError('UNEXPECTED_PAGE')
    marker=MARKER+':page'
    if marker in source:
        if source.count(marker)!=1 or source.count('id="zm-farm-risk-action-20261106"')!=1 or source.count(URL)!=1:
            raise RuntimeError('PARTIAL_PAGE_PATCH')
        return 'already-patched',source
    if MARKER in source or URL in source or source.count('<main id="main">')!=1:
        raise RuntimeError('UNSAFE_PAGE_DRIFT:'+slug)
    if '<h1>'+PAGES[slug]+'</h1>' not in source or source.count('<link rel="canonical"')!=1 or source.count('</main>')!=1:
        raise RuntimeError('PAGE_TITLE_OR_STRUCTURE_CHANGED:'+slug)
    return 'needs-patch',source.replace('<main id="main">','<main id="main">'+ACTION,1)

def inspect():
    result=[]
    for path in FILES:
        source=None if path==ENGINE and not path.exists() else path.read_text(encoding='utf-8')
        state,output=transform(path,source)
        result.append((path,state,source,output))
    return result

def safe_folder(runid):
    if not re.fullmatch('[0-9]{5,20}',runid):raise RuntimeError('INVALID_RUN_ID')
    BACKUPS.mkdir(mode=0o700,parents=True,exist_ok=True)
    os.chmod(BACKUPS,0o700)
    path=BACKUPS/runid
    if path.is_symlink():raise RuntimeError('UNSAFE_BACKUP_SYMLINK')
    return path

def atomic_write(path,content,mode):
    path.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix='.farm-risk-',dir=str(path.parent))
    try:
        with os.fdopen(fd,'wb') as out:
            out.write(content);out.flush();os.fsync(out.fileno())
        os.chmod(temp,mode);os.replace(temp,path)
    finally:
        if os.path.exists(temp):os.unlink(temp)

def publish(runid):
    changes=[x for x in inspect() if x[1]!='already-patched']
    target=safe_folder(runid)
    if target.exists():raise RuntimeError('BACKUP_RUN_COLLISION')
    target.mkdir(mode=0o700)
    entries=[]
    for path,state,source,output in changes:
        name=str(path.relative_to(WEB));dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open('xb') as f:f.write(b'' if source is None else source.encode('utf-8'))
        dest.chmod(0o600)
        entries.append({'path':name,'new':state=='new-file','mode':0o644 if source is None else stat.S_IMODE(path.stat().st_mode)})
    (target/'manifest.json').write_text(json.dumps(entries),encoding='utf-8')
    completed=[]
    try:
        for path,state,source,output in changes:
            entry=next(x for x in entries if x['path']==str(path.relative_to(WEB)))
            atomic_write(path,output.encode('utf-8'),entry['mode']);completed.append((path,state,source,entry['mode']))
    except Exception:
        for path,state,source,mode in reversed(completed):
            if state=='new-file':
                if path.read_text(encoding='utf-8')==ENGINE_HTML:path.unlink()
            else:atomic_write(path,source.encode('utf-8'),mode)
        raise
    print('FARM_RISK_PUBLISHED_FILES='+str(len(changes)))

def verify_origin():
    for path in FILES:
        if transform(path,path.read_text(encoding='utf-8'))[0]!='already-patched':
            raise RuntimeError('ORIGIN_NOT_PATCHED:'+str(path))
    print('FARM_RISK_ORIGIN_OK='+str(len(FILES)))

def verify_public():
    checks={'/economy/':[MARKER+':page',URL],'/market/':[MARKER+':page',URL],URL:[MARKER+':engine','id="risk-form"','id="expected-profit"']}
    for attempt in range(7):
        try:
            for path,tokens in checks.items():
                req=Request('https://zomorodmelal.ir'+path,headers={'User-Agent':'Zomorod-Farm-Risk-Publisher/1.0','Cache-Control':'no-cache'})
                with urlopen(req,timeout=30) as response:
                    body=response.read(1100000).decode('utf-8','replace')
                    if response.status!=200:raise RuntimeError('PUBLIC_HTTP:'+path)
                for token in tokens:
                    if token not in body:raise RuntimeError('PUBLIC_MISSING:'+path+':'+token)
            print('FARM_RISK_PUBLIC_OK=3');return
        except Exception:
            if attempt==6:raise
            time.sleep(5)

def rollback(runid):
    folder=safe_folder(runid)
    entries=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    for entry in entries:
        p=WEB/entry['path']
        if p.is_symlink() or transform(p,p.read_text(encoding='utf-8'))[0]!='already-patched':
            raise RuntimeError('REFUSE_ROLLBACK_DRIFT:'+entry['path'])
    for entry in entries:
        p=WEB/entry['path']
        if entry['new']:p.unlink()
        else:atomic_write(p,(folder/entry['path']).read_bytes(),entry['mode'])
    print('FARM_RISK_ROLLED_BACK='+str(len(entries)))

def selftest():
    sample='<head><link rel="canonical" href="x"></head><main id="main"><h1>رصد اقتصاد ایران و جهان</h1></main>'
    p=WEB/'economy/index.html'
    state,new=transform(p,sample)
    assert state=='needs-patch' and transform(p,new)[0]=='already-patched'
    assert transform(ENGINE,None)[0]=='new-file' and transform(ENGINE,ENGINE_HTML)[0]=='already-patched'
    print('FARM_RISK_SELFTEST_OK=1')

if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='selftest':selftest();sys.exit(0)
    validate()
    if len(sys.argv)==2 and sys.argv[1]=='preview':
        print('FARM_RISK_PREVIEW='+json.dumps({str(p.relative_to(WEB)):s for p,s,_,_ in inspect()},sort_keys=True))
    elif len(sys.argv)==3 and sys.argv[1]=='publish':publish(sys.argv[2])
    elif len(sys.argv)==3 and sys.argv[1]=='verify-origin':verify_origin();verify_public()
    elif len(sys.argv)==3 and sys.argv[1]=='rollback':rollback(sys.argv[2])
    else:raise RuntimeError('UNKNOWN_MODE')
