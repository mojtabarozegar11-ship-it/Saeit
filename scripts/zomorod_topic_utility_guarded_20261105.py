#!/usr/bin/env python3
"""Add usable local-only utilities to the *live static* Zomorod topic pages.

Scope: 605-link topic directory, precisely 545 generated topic article files,
and one new standalone calculator below the existing /topics/ static boundary.
Never touches payments, mail, Django, the homepage, or research directory.
All changes are backed up privately, written atomically and reversible.
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

HOME = Path("/home/zomorod2")
WEB = HOME / "public_html"
TOPICS = WEB / "topics"
BACKUPS = HOME / ".private/topic-utility-backups"
ENGINE = TOPICS / "tools/project-economics/index.html"
HUB = TOPICS / "index.html"
GENERATED = "zm-all-cards-dedicated-topics-20261018:topic"
MARKER = "zm-topic-utility-20261105"
TOOL_URL = "/topics/tools/project-economics/"
SEED_URL = "/store/free-products/wheat-seed-rate-planner-v1/index.html"
REQUEST_URL = "/ask-master/index.php"
STATUS_URL = "/ask-master/status.php"

HUB_UI = '''
<aside id="zm-topic-finder-20261105" aria-label="جست‌وجو و ابزارهای کاربردی" style="border:1px solid #d6b46d;border-radius:18px;background:#244636;padding:18px;margin:18px 0;max-width:100%;box-sizing:border-box">
 <h2 style="margin:0 0 8px">پیدا کردن موضوع و انجام کار</h2>
 <label for="zm-topic-query">جست‌وجو میان ۶۰۵ موضوع</label>
 <div style="display:flex;flex-wrap:wrap;gap:10px;margin:8px 0">
  <input type="search" id="zm-topic-query" autocomplete="off" placeholder="مثلاً گندم، اقتصاد، آبیاری، فرش" style="flex:1 1 230px;min-width:0;font:inherit;padding:10px;border:2px solid #d6b46d;border-radius:9px;background:#fff;color:#13271e">
  <button id="zm-topic-clear" type="button" style="font:inherit;padding:8px 15px;border-radius:9px;cursor:pointer">نمایش همه</button>
 </div>
 <p id="zm-topic-count" role="status" aria-live="polite">۶۰۵ موضوع در ۲۹ گروه قابل مشاهده است.</p>
 <nav aria-label="امکانات عملی" style="display:flex;flex-wrap:wrap;gap:15px">
  <a style="color:#f7d99f" href="/topics/tools/project-economics/">محاسبه‌گر واقعی سود و نقطهٔ سربه‌سر</a>
  <a style="color:#f7d99f" href="/store/free-products/wheat-seed-rate-planner-v1/index.html">محاسبه بذر گندم</a>
  <a style="color:#f7d99f" href="/ask-master/index.php">ثبت درخواست و استعلام</a>
  <a style="color:#f7d99f" href="/ask-master/status.php">پیگیری درخواست</a>
 </nav>
 <p style="font-size:.85em">معرفی موضوع، وعدهٔ ارائهٔ خدمت نیست. ابزار مالی تنها سناریوی اعداد واردشده را محاسبه می‌کند.</p>
</aside>
<!-- zm-topic-utility-20261105:hub -->
'''

HUB_SCRIPT = '''
<script id="zm-topic-search-script-20261105">
(()=>{'use strict';
 const input=document.getElementById('zm-topic-query');
 const clear=document.getElementById('zm-topic-clear');
 const count=document.getElementById('zm-topic-count');
 const groups=Array.from(document.querySelectorAll('main > section[id^="zm-r"]'));
 const total=groups.reduce((n,s)=>n+s.querySelectorAll('li > a').length,0);
 const normalize=(s)=>String(s).toLocaleLowerCase('fa-IR').replace(/ي/g,'ی').replace(/ك/g,'ک').replace(/[\u064b-\u065f\u0670]/g,'').trim();
 if(!input||!clear||!count||groups.length!==29||total!==605)return;
 const entries=groups.map(section=>({section,items:Array.from(section.querySelectorAll('li')).map(li=>({li,text:normalize(li.textContent)})),label:normalize(section.querySelector('h2')?.textContent||'')}));
 function update(){
   const q=normalize(input.value);let shown=0,groupCount=0;
   for(const group of entries){let local=0;
     for(const item of group.items){const match=!q||item.text.includes(q)||group.label.includes(q);item.li.hidden=!match;if(match){shown++;local++;}}
     group.section.hidden=local===0;if(local)groupCount++;
   }
   count.textContent=q?`${shown.toLocaleString('fa-IR')} موضوع مرتبط در ${groupCount.toLocaleString('fa-IR')} گروه`:`${total.toLocaleString('fa-IR')} موضوع در ${groupCount.toLocaleString('fa-IR')} گروه`;
   if(q&&shown===0)count.textContent+='؛ نتیجه‌ای یافت نشد. عبارت دیگری وارد کنید.';
 }
 input.addEventListener('input',update);
 clear.addEventListener('click',()=>{input.value='';update();input.focus()});
 update();
})();
</script>
'''

ACTION_PANEL = '''
<aside id="zm-topic-usable-actions-20261105" aria-label="ابزار و مسیر اقدام" style="border:1px solid #d6b46d;border-radius:18px;background:#244636;padding:20px;margin:22px 0;box-sizing:border-box">
 <h2 style="margin:0 0 8px;color:#f0d08b">از مطالعه تا اقدام عملی</h2>
 <p>اگر موضوع این مقاله را برای یک فعالیت اقتصادی بررسی می‌کنید، درآمد، هزینه و نقطهٔ سربه‌سر را با داده‌های خود محاسبه کنید. این محاسبه رایگان، مستقل و بدون ارسال اطلاعات به سرور است.</p>
 <nav style="display:flex;flex-wrap:wrap;gap:15px">
  <a style="color:#f0d08b" href="/topics/tools/project-economics/">محاسبه سناریوی اقتصادی و دانلود نتیجه</a>
  <a style="color:#f0d08b" href="/ask-master/index.php">ثبت پرسش یا استعلام واقعی</a>
  <a style="color:#f0d08b" href="/ask-master/status.php">پیگیری درخواست ثبت‌شده</a>
 </nav>
 <p style="font-size:.85em">این پیوندها به معنی فعال بودن خدمت تخصصی برای تک‌تک موضوعات نیست؛ ابتدا امکان ارائهٔ خدمت بررسی می‌شود.</p>
</aside>
<!-- zm-topic-utility-20261105:article -->
'''

WHEAT_LINK = '''<p><a style="color:#f0d08b" href="/store/free-products/wheat-seed-rate-planner-v1/index.html">اجرای محاسبه‌گر رایگان مقدار بذر گندم</a></p>'''

ENGINE_HTML = '''<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>محاسبه‌گر سود و نقطهٔ سربه‌سر فعالیت | زمرد ملل</title>
<meta name="description" content="ابزار رایگان محاسبه درآمد، هزینه کل، سود عملیاتی، حاشیه سود، نقطه سربه‌سر و بازگشت سرمایه بر اساس اعداد واردشده.">
<meta name="robots" content="index,follow"><link rel="canonical" href="https://zomorodmelal.ir/topics/tools/project-economics/">
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#102b22;color:#f9edd2;font-family:Tahoma,Arial,sans-serif;line-height:1.9}
header,main,footer{width:min(840px,calc(100% - 24px));margin:auto}header,footer{padding:16px 0}a{color:#f1d28c}h1,h2{color:#f1d28c;line-height:1.5}h1{font-size:clamp(24px,4vw,38px)}
.card{background:#204234;border:1px solid #907e59;border-radius:16px;padding:18px;margin:15px 0}.fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
label{display:block;font-weight:bold}input{display:block;width:100%;border:2px solid #d5c394;border-radius:8px;background:white;color:#12281d;padding:11px;font:inherit}
button{font:inherit;padding:10px 20px;margin:10px 0 0 8px;cursor:pointer;border-radius:8px;border:2px solid #f1d28c;background:#e9ca87;color:#193426;font-weight:bold}button.secondary{background:transparent;color:#f1d28c}
button:disabled{opacity:.5;cursor:not-allowed}.error{color:#ffcebd;min-height:1.5em}#results[hidden]{display:none}dl{display:grid;grid-template-columns:1fr auto;gap:6px 20px}dt,dd{margin:0;border-bottom:1px solid #ffffff22;padding:7px 0}dd{font-weight:bold;text-align:left;font-variant-numeric:tabular-nums}small{font-size:.88em}a:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid #fff;outline-offset:3px}
@media(max-width:600px){.fields{grid-template-columns:1fr}dl{gap:6px 9px}.card{padding:13px}}
</style></head><body>
<header><a href="/">زمرد ملل</a> · <a href="/topics/">دانشنامه موضوعات</a> · <a href="/store/">فروشگاه</a></header>
<main><h1>محاسبه‌گر اقتصادی فعالیت و نقطهٔ سربه‌سر</h1>
<p>اعداد واقعی یا سناریوی فرضی خود را وارد کنید. محاسبه در همین مرورگر انجام می‌شود؛ داده‌ها ذخیره یا ارسال نمی‌شوند. واحد مبالغ «تومان» و بازهٔ تمام اعداد «یک ماه» است.</p>
<form id="economy-form" class="card" novalidate>
 <div class="fields">
  <label>عنوان فعالیت<input id="project" name="project" type="text" maxlength="100" placeholder="مثلاً مزرعه، کارگاه یا خدمت"></label>
  <label>واحد فروش<input id="unit" name="unit" type="text" maxlength="35" placeholder="مثلاً کیلوگرم، قطعه، سفارش"></label>
  <label>قیمت فروش هر واحد (تومان)<input id="price" name="price" type="number" min="0" max="1000000000000" step="any" required placeholder="مبلغ هر واحد"></label>
  <label>هزینه متغیر هر واحد (تومان)<input id="variable" name="variable" type="number" min="0" max="1000000000000" step="any" required placeholder="مواد، بسته‌بندی و ..."></label>
  <label>هزینه ثابت ماهانه (تومان)<input id="fixed" name="fixed" type="number" min="0" max="1000000000000" step="any" required placeholder="اجاره، حقوق، ..."></label>
  <label>مقدار فروش ماهانه (واحد)<input id="quantity" name="quantity" type="number" min="0" max="1000000000" step="1" required placeholder="تعداد واحد فروش"></label>
  <label>سرمایه‌گذاری اولیه (تومان) — اختیاری<input id="investment" name="investment" type="number" min="0" max="1000000000000" step="any" placeholder="برای برآورد بازگشت"></label>
 </div>
 <button type="submit">محاسبه نتیجه اقتصادی</button><button type="reset" class="secondary">پاک‌کردن</button>
 <p id="error" class="error" role="alert" aria-live="assertive"></p>
</form>
<section id="results" class="card" aria-live="polite" hidden><h2>خروجی محاسبه</h2><p id="scenario"></p>
 <dl><dt>درآمد فروش ماهانه</dt><dd id="revenue"></dd><dt>هزینه متغیر کل</dt><dd id="variable-total"></dd>
 <dt>کل هزینه ماهانه</dt><dd id="total-cost"></dd><dt>سود یا زیان ماهانه</dt><dd id="profit"></dd>
 <dt>حاشیه سود عملیاتی</dt><dd id="margin"></dd><dt>نقطهٔ سربه‌سر فروش</dt><dd id="breakeven"></dd>
 <dt>دوره بازگشت ساده سرمایه</dt><dd id="payback"></dd></dl>
 <button id="download" type="button">دریافت گزارش JSON</button></section>
<aside class="card"><h2>محدوده اعتبار</h2><p>این خروجی صرفاً از قیمت، مقدار فروش و هزینه‌های اعلام‌شده محاسبه می‌شود. مالیات، تورم، نرخ تنزیل، استهلاک، ریسک فروش، تغییر موجودی و سود مالی را جداگانه بررسی کنید. بازگشت سرمایه تخمین ساده است و تضمین سود یا توصیه سرمایه‌گذاری نیست.</p>
<p><a href="/ask-master/index.php">ثبت استعلام تخصصی در شرکت</a> · <a href="/ask-master/status.php">پیگیری درخواست</a></p></aside></main>
<footer>زمرد ملل · محاسبات سمت مرورگر، بدون ارسال داده · <a href="/topics/">بازگشت به دانشنامه</a></footer>
<script>
(()=>{'use strict';const form=document.getElementById('economy-form'),error=document.getElementById('error'),results=document.getElementById('results');let report=null;
const number=id=>{const el=document.getElementById(id);if(!el.value.trim())throw Error('فیلد «'+el.parentElement.textContent.trim().split('(')[0]+'» را تکمیل کنید.');const n=Number(el.value);if(!Number.isFinite(n)||n<0||n>Number(el.max))throw Error('عدد واردشده معتبر یا در محدوده مجاز نیست.');return n};
const money=n=>new Intl.NumberFormat('fa-IR',{maximumFractionDigits:2}).format(n)+' تومان';const numeric=n=>new Intl.NumberFormat('fa-IR',{maximumFractionDigits:2}).format(n);
const value=(id,v)=>{document.getElementById(id).textContent=v};
form.addEventListener('submit',e=>{e.preventDefault();error.textContent='';results.hidden=true;report=null;
 try{const price=number('price'),variable=number('variable'),fixed=number('fixed'),quantity=number('quantity');
 const invest=document.getElementById('investment').value.trim()?number('investment'):null;
 if(!Number.isInteger(quantity))throw Error('مقدار فروش ماهانه باید عدد صحیح باشد.');
 const revenue=price*quantity,variableTotal=variable*quantity,total=variableTotal+fixed,profit=revenue-total,contribution=price-variable;
 if(![revenue,variableTotal,total,profit,contribution].every(Number.isFinite))throw Error('اندازه سناریو از محدوده محاسبه بیرون است.');
 const breakEven=contribution>0?Math.ceil(fixed/contribution):null;
 const payback=invest===null?null:profit>0?invest/profit:null;
 const margin=revenue>0?100*profit/revenue:null;
 if((breakEven!==null&&!Number.isSafeInteger(breakEven))||(payback!==null&&!Number.isFinite(payback)))throw Error('نقطهٔ سربه‌سر یا بازگشت سرمایه از محدودهٔ محاسبه خارج است.');
 report={project:document.getElementById('project').value.trim(),unit:document.getElementById('unit').value.trim(),currency:'toman',period:'monthly',inputs:{price,variableCostPerUnit:variable,fixedCost:fixed,quantity,initialInvestment:invest},outputs:{revenue,variableTotal,totalCost:total,operatingProfit:profit,profitMarginPct:margin,breakEvenUnits:breakEven,simplePaybackMonths:payback},limitations:'Scenario only; taxes, depreciation, discounting and uncertainty excluded.'};
 value('scenario',report.project||'سناریوی بدون عنوان');value('revenue',money(revenue));value('variable-total',money(variableTotal));value('total-cost',money(total));
 value('profit',money(profit));value('margin',margin===null?'نامشخص؛ فروش صفر است':numeric(margin)+'٪');
 value('breakeven',breakEven===null?'با این قیمت و هزینه متغیر، نقطهٔ سربه‌سر وجود ندارد':numeric(breakEven)+' واحد در ماه');
 value('payback',invest===null?'سرمایه اولیه وارد نشده':payback===null?'با سود فعلی قابل برآورد نیست':numeric(payback)+' ماه');results.hidden=false;
 }catch(ex){error.textContent=ex.message;}
});
form.addEventListener('reset',()=>{report=null;results.hidden=true;error.textContent=''});
document.getElementById('download').addEventListener('click',()=>{if(!report)return;
 const blob=new Blob([JSON.stringify(report,null,2)],{type:'application/json;charset=utf-8'});const url=URL.createObjectURL(blob);
 const a=document.createElement('a');a.href=url;a.download='zomorod-project-economics.json';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
})();
</script><!-- zm-topic-utility-20261105:engine --></body></html>
'''

def validate_paths():
    if os.geteuid() == 0 or os.geteuid() != os.stat(WEB).st_uid:
        raise RuntimeError("REFUSE_WRONG_USER")
    if TOPICS.is_symlink() or not TOPICS.is_dir() or HUB.is_symlink():
        raise RuntimeError("UNSAFE_TOPICS_ROOT")
    rule = (TOPICS / ".htaccess").read_text(encoding="utf-8")
    if "PassengerEnabled off" not in rule:
        raise RuntimeError("TOPICS_STATIC_BOUNDARY_CHANGED")
    manifest = json.loads((TOPICS / "topic-manifest.json").read_text(encoding="utf-8"))
    if manifest.get("newPages") != 545 or manifest.get("pageCount") != 605:
        raise RuntimeError("TOPIC_MANIFEST_CHANGED")
    files = sorted(TOPICS.glob("zm-r*/*/index.html"))
    if len(files) != 545 or len({p.resolve() for p in files}) != 545:
        raise RuntimeError("TOPIC_FILE_COUNT_CHANGED")
    if any(p.is_symlink() or p.parent.is_symlink() for p in files):
        raise RuntimeError("SYMLINK_TOPIC_FILE")
    if ENGINE.exists() and ENGINE.is_symlink():
        raise RuntimeError("SYMLINK_CALCULATOR")
    return files

def patch_hub(source):
    marker = MARKER + ":hub"
    if source.count(marker) == 1 and source.count('id="zm-topic-search-script-20261105"') == 1:
        return "already-patched", source
    if marker in source or 'id="zm-topic-finder-20261105"' in source:
        raise RuntimeError("PARTIAL_HUB_PATCH")
    if source.count('href="https://zomorodmelal.ir/topics/"') != 1:
        raise RuntimeError("HUB_CANONICAL_MISMATCH")
    if source.count('<li><a href=') != 605 or source.count('<main>') != 1 or source.count('</body>') != 1:
        raise RuntimeError("HUB_STRUCTURE_MISMATCH")
    result = source.replace('<main>', '<main>'+HUB_UI, 1).replace('</body>',HUB_SCRIPT+'</body>',1)
    if result.count('<li><a href=') != 605 or result.count(marker) != 1:
        raise RuntimeError("HUB_LINK_REGRESSION")
    return "needs-patch", result

def patch_article(path,source):
    marker=MARKER+":article"
    if source.count(marker)==1:
        if source.count('id="zm-topic-usable-actions-20261105"')!=1:
            raise RuntimeError("PARTIAL_ARTICLE_PATCH:"+str(path))
        return "already-patched",source
    if marker in source or 'id="zm-topic-usable-actions-20261105"' in source:
        raise RuntimeError("PARTIAL_ARTICLE_PATCH:"+str(path))
    if GENERATED not in source or source.count('data-zm-dedicated-topic=')!=1:
        raise RuntimeError("NOT_GENERATED_TOPIC:"+str(path))
    if source.count('</main>')!=1 or source.count('<link rel="canonical"')!=1:
        raise RuntimeError("TOPIC_STRUCTURE_CHANGED:"+str(path))
    insert=ACTION_PANEL
    if path.parent.name=='wheat' and path.parent.parent.name=='zm-r01':
        insert=insert.replace('</nav>',WHEAT_LINK+'</nav>',1)
    result=source.replace('</main>',insert+'</main>',1)
    if result.count(marker)!=1 or result.count('<link rel="canonical"')!=1:
        raise RuntimeError("TOPIC_PATCH_REGRESSION:"+str(path))
    return "needs-patch",result

def items(files):
    output=[(HUB,patch_hub(HUB.read_text(encoding="utf-8")))]
    for p in files:
        output.append((p,patch_article(p,p.read_text(encoding="utf-8"))))
    if ENGINE.exists():
        body=ENGINE.read_text(encoding="utf-8")
        if body!=ENGINE_HTML:
            raise RuntimeError("REFUSE_EXISTING_CALCULATOR_DRIFT")
        output.append((ENGINE,("already-patched",body)))
    else:
        output.append((ENGINE,("new-file",ENGINE_HTML)))
    return output

def backup_root(run_id):
    if not re.fullmatch(r"\d{5,20}",run_id):
        raise RuntimeError("INVALID_RUN_ID")
    if BACKUPS.is_symlink() or BACKUPS.parent.is_symlink():
        raise RuntimeError("UNSAFE_BACKUPS")
    BACKUPS.mkdir(parents=True,mode=0o700,exist_ok=True)
    os.chmod(BACKUPS,0o700)
    folder=BACKUPS/run_id
    if folder.is_symlink():
        raise RuntimeError("INVALID_BACKUP_RUN")
    return folder

def atomic_write(path,data,mode):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.zm-topic-',dir=str(path.parent))
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.chmod(tmp,mode);os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def publish(run_id,files):
    changed=[(p,s,new) for p,(s,new) in items(files) if s!='already-patched']
    folder=backup_root(run_id)
    if folder.exists():
        raise RuntimeError("RUN_BACKUP_ALREADY_EXISTS")
    folder.mkdir(mode=0o700)
    record=[]
    for p,state,new in changed:
        is_new=state=='new-file'
        original=b'' if is_new else p.read_bytes()
        relative=p.relative_to(TOPICS)
        backup=folder/relative
        backup.parent.mkdir(parents=True,exist_ok=True)
        with backup.open('xb') as output:output.write(original)
        backup.chmod(0o600)
        record.append({'path':str(relative),'new':is_new,'mode':0o644 if is_new else stat.S_IMODE(p.stat().st_mode)})
    (folder/'manifest.json').write_text(json.dumps(record),encoding='utf-8')
    modified=[]
    try:
        for p,state,new in changed:
            if p.is_symlink():raise RuntimeError("SYMLINK_DURING_WRITE")
            entry=next(x for x in record if x['path']==str(p.relative_to(TOPICS)))
            atomic_write(p,new.encode('utf-8'),entry['mode'])
            modified.append((p,state))
    except Exception:
        for p,state in reversed(modified):
            entry=next(x for x in record if x['path']==str(p.relative_to(TOPICS)))
            old=(folder/entry['path']).read_bytes()
            if state=='new-file':
                if p.read_bytes()==ENGINE_HTML.encode('utf-8'):p.unlink()
            else:
                atomic_write(p,old,entry['mode'])
        raise
    print(f"TOPIC_UTILITY_UPDATED={len(changed)} ARTICLES={sum(p!=HUB and p!=ENGINE for p,_,_ in changed)}")

def verify_origin(files):
    assert patch_hub(HUB.read_text(encoding='utf-8'))[0]=='already-patched'
    for p in files:
        assert patch_article(p,p.read_text(encoding='utf-8'))[0]=='already-patched',str(p)
    assert ENGINE.read_text(encoding='utf-8')==ENGINE_HTML
    print("TOPIC_ORIGIN_VERIFIED=545 HUB_SEARCH=605 CALCULATOR=1")

def public(path,tokens):
    req=Request('https://zomorodmelal.ir'+path,headers={'User-Agent':'Zomorod-Topic-Utility/1.0','Cache-Control':'no-cache'})
    with urlopen(req,timeout=30) as response:
        body=response.read(1100000).decode('utf-8','replace')
        if response.status!=200 or 'noindex' in response.headers.get('X-Robots-Tag','').lower():
            raise RuntimeError('BAD_PUBLIC_STATUS:'+path)
    for token in tokens:
        if token not in body:raise RuntimeError('MISSING_PUBLIC_TOKEN:'+path+':'+token)

def verify_public():
    last=None
    samples=[('/topics/',[MARKER+':hub','id="zm-topic-query"','zm-topic-search-script-20261105']),
             ('/topics/zm-r01/wheat/',[MARKER+':article',SEED_URL,TOOL_URL]),
             ('/topics/zm-r01/barley/',[MARKER+':article',REQUEST_URL,TOOL_URL]),
             (TOOL_URL,[MARKER+':engine','id="economy-form"','id="breakeven"'])]
    for attempt in range(7):
        try:
            for path,tokens in samples:public(path,tokens)
            print("TOPIC_PUBLIC_VERIFIED=4");return
        except Exception as exc:
            last=repr(exc)
            if attempt!=6:time.sleep(5)
    raise RuntimeError('TOPIC_PUBLIC_VERIFY_FAILED:'+str(last))

def rollback(run_id):
    folder=backup_root(run_id)
    data=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    for entry in data:
        path=TOPICS/entry['path']
        if path.is_symlink():raise RuntimeError('SYMLINK_ROLLBACK')
        text=path.read_text(encoding='utf-8')
        if entry['new']:
            if text!=ENGINE_HTML:raise RuntimeError('CALCULATOR_DRIFT_ROLLBACK')
        elif path==HUB:
            if patch_hub(text)[0]!='already-patched':raise RuntimeError('HUB_DRIFT_ROLLBACK')
        elif patch_article(path,text)[0]!='already-patched':
            raise RuntimeError('ARTICLE_DRIFT_ROLLBACK:'+str(path))
    for entry in data:
        path=TOPICS/entry['path']
        if entry['new']:
            path.unlink()
        else:
            atomic_write(path,(folder/entry['path']).read_bytes(),entry['mode'])
    print('TOPIC_UTILITY_ROLLED_BACK='+str(len(data)))

def selftest():
    hub='<link rel="canonical" href="https://zomorodmelal.ir/topics/"><main>'+('<li><a href="/topics/x/">x</a></li>'*605)+'</main></body>'
    assert patch_hub(hub)[0]=='needs-patch'
    assert patch_hub(patch_hub(hub)[1])[0]=='already-patched'
    topic='<link rel="canonical" href="https://zomorodmelal.ir/topics/a/"><body data-zm-dedicated-topic="1"><main></main><!-- '+GENERATED+' -->'
    sample=Path('/tmp/topics/zm-r01/wheat/index.html')
    state,updated=patch_article(sample,topic)
    assert state=='needs-patch' and SEED_URL in updated
    assert patch_article(sample,updated)[0]=='already-patched'
    assert 'id="economy-form"' in ENGINE_HTML and 'id="breakeven"' in ENGINE_HTML
    print('TOPIC_UTILITY_SELFTEST_OK=1')

if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='selftest':
        selftest();sys.exit(0)
    files=validate_paths()
    if len(sys.argv)==2 and sys.argv[1]=='preview':
        states=[s for _,(s,_) in items(files)]
        print('TOPIC_UTILITY_PREVIEW='+json.dumps({s:states.count(s) for s in set(states)},sort_keys=True))
    elif len(sys.argv)==3 and sys.argv[1]=='publish':
        publish(sys.argv[2],files)
    elif len(sys.argv)==3 and sys.argv[1]=='verify-origin':
        verify_origin(files);verify_public()
    elif len(sys.argv)==3 and sys.argv[1]=='rollback':
        rollback(sys.argv[2])
    else:
        raise RuntimeError('UNKNOWN_MODE')
