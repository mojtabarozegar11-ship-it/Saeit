#!/usr/bin/env python3
"""Release a FAO-based, browser-only irrigation planner on live static pages.

Exactly 9 relevant topic articles + /topics/ index + one new utility page.
Refuse drift, preserve canonicals, back up every existing file before writes,
and restore exact previous bytes if independent public checks fail.
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
ROOT=HOME/'public_html/topics'
WEB=HOME/'public_html'
BACKUPS=HOME/'.private/irrigation-planner-backups'
HUB=ROOT/'index.html'
ENGINE=ROOT/'tools/irrigation-planner/index.html'
URL='/topics/tools/irrigation-planner/'
MARKER='zm-fao-irrigation-planner-20261106'
TOPIC_ARTICLE_MARKER='zm-topic-utility-20261105:article'
TOPIC_HUB_MARKER='zm-topic-utility-20261105:hub'
TARGETS={
 'zm-r09/drip-irrigation/index.html':'آبیاری قطره‌ای',
 'zm-r09/sprinkler-irrigation/index.html':'آبیاری بارانی',
 'zm-r09/smart-irrigation/index.html':'آبیاری هوشمند',
 'zm-r09/water-use-management/index.html':'مدیریت مصرف آب',
 'zm-r09/agricultural-water/index.html':'منابع آب کشاورزی',
 'zm-r09/soil-moisture/index.html':'پایش رطوبت خاک',
 'zm-r09/farm-water-management/index.html':'مدیریت آب مزرعه',
 'zm-r09/water-reservoir/index.html':'استخر ذخیره آب',
 'zm-r03/greenhouse-irrigation/index.html':'آبیاری گلخانه',
}

LINK_HUB='''<a style="color:#f7d99f" href="/topics/tools/irrigation-planner/">برآورد آب آبیاری با روش FAO</a>\n  '''
LINK_TOPIC='''<a style="color:#f0d08b" href="/topics/tools/irrigation-planner/">برآورد نیاز آبی، حجم آب و زمان پمپاژ</a>\n  '''
HUB_INSERT_BEFORE='<a style="color:#f7d99f" href="/store/free-products/wheat-seed-rate-planner-v1/index.html">'
ARTICLE_INSERT_BEFORE='<a style="color:#f0d08b" href="/topics/tools/project-economics/">'

ENGINE_HTML='''<!doctype html>
<html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>محاسبه‌گر نیاز آب آبیاری با روش FAO | زمرد ملل</title>
<meta name="description" content="برآورد رایگان تبخیر و تعرق گیاه، عمق خالص و ناخالص آبیاری، حجم آب و زمان پمپاژ بر پایه داده‌های ورودی و روش فائو.">
<meta name="robots" content="index,follow"><link rel="canonical" href="https://zomorodmelal.ir/topics/tools/irrigation-planner/">
<style>
:root{color-scheme:dark}*{box-sizing:border-box}body{margin:0;background:#102b22;color:#f9edd2;font-family:Tahoma,Arial,sans-serif;line-height:1.95}
header,main,footer{width:min(870px,calc(100% - 24px));margin:auto}header,footer{padding:18px 0}a{color:#f1d28c}h1,h2{color:#f1d28c;line-height:1.5}h1{font-size:clamp(25px,4vw,38px)}
.card{background:#204234;border:1px solid #8b8267;border-radius:16px;padding:19px;margin:16px 0}.fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
label{display:block;font-weight:bold}input{width:100%;display:block;background:white;color:#132b20;border:2px solid #cfbf90;border-radius:8px;padding:10px;font:inherit}
button{font:inherit;padding:10px 18px;margin:12px 0 0 8px;border:2px solid #e6c782;border-radius:8px;cursor:pointer;background:#e6c782;color:#153626;font-weight:bold}
button.secondary{background:transparent;color:#f1d28c}button:disabled{opacity:.5}.note{font-size:.89em}#error{color:#ffd0b9;min-height:1.7em}
dl{display:grid;grid-template-columns:1fr auto;gap:5px 16px}dt,dd{margin:0;padding:8px 0;border-bottom:1px solid #ffffff26}dd{text-align:left;font-weight:bold;font-variant-numeric:tabular-nums}
#results[hidden]{display:none}input:focus-visible,button:focus-visible,a:focus-visible{outline:3px solid white;outline-offset:2px}
@media(max-width:620px){.fields{grid-template-columns:1fr}.card{padding:14px}dl{gap:5px 8px}}
</style></head><body>
<header><a href="/">زمرد ملل</a> · <a href="/topics/">دانشنامه</a> · <a href="/ask-master/index.php">ثبت درخواست</a></header>
<main><h1>محاسبه‌گر نیاز آب آبیاری و حجم پمپاژ</h1>
<p>با واردکردن داده‌های مزرعه یا گلخانه، برآورد سناریویی نیاز آبی را محاسبه کنید. این ابزار از دادهٔ خودتان استفاده می‌کند؛ به هواشناسی زنده متصل نیست و اطلاعات شما را ذخیره یا ارسال نمی‌کند.</p>
<form id="water-form" class="card" novalidate>
 <div class="fields">
  <label>عنوان کشت یا فعالیت<input id="crop" type="text" maxlength="100" placeholder="مثلاً گندم در مرحله رشد مشخص"></label>
  <label>ET₀ روزانه؛ تبخیر و تعرق مرجع (میلی‌متر/روز)<input id="eto" type="number" min="0" max="40" step="any" required placeholder="داده معتبر اقلیمی خودتان"></label>
  <label>Kc ضریب گیاهی متناسب با مرحله رشد<input id="kc" type="number" min="0" max="2.5" step="any" required placeholder="مقدار منتخب براساس گیاه و مرحله"></label>
  <label>بازه محاسبه (روز)<input id="days" type="number" min="1" max="365" step="1" required placeholder="مثلاً ۷ روز"></label>
  <label>بارش مؤثر کل بازه (میلی‌متر)<input id="rain" type="number" min="0" max="10000" step="any" required placeholder="در نبود بارش مؤثر: صفر"></label>
  <label>سطح زیر کشت (هکتار)<input id="area" type="number" min="0.0001" max="1000000" step="any" required placeholder="مثلاً ۲٫۵ هکتار"></label>
  <label>راندمان کاربرد آب (درصد)<input id="eff" type="number" min="1" max="100" step="any" required placeholder="از ارزیابی سامانه، نه حدس"></label>
  <label>دبی قابل تحویل پمپ (مترمکعب/ساعت) — اختیاری<input id="flow" type="number" min="0.001" max="1000000000" step="any" placeholder="برای محاسبه ساعت پمپاژ"></label>
  <label>هزینه آب و انرژی هر مترمکعب (تومان) — اختیاری<input id="cost" type="number" min="0" max="1000000000" step="any" placeholder="برای برآورد هزینه دوره"></label>
 </div><button type="submit">محاسبه نیاز آب</button><button type="reset" class="secondary">پاک‌کردن</button>
 <p id="error" role="alert" aria-live="assertive"></p>
</form>
<section id="results" class="card" aria-live="polite" hidden><h2>خروجی برآورد</h2><p id="summary"></p>
<dl><dt>ETc روزانه؛ نیاز تبخیر و تعرق گیاه</dt><dd id="etc-day"></dd>
<dt>ETc کل بازه</dt><dd id="etc-total"></dd>
<dt>عمق خالص آبیاری پس از بارش مؤثر</dt><dd id="net-depth"></dd>
<dt>عمق ناخالص با احتساب راندمان</dt><dd id="gross-depth"></dd>
<dt>حجم خالص آب</dt><dd id="net-volume"></dd>
<dt>حجم ناخالص مورد نیاز در ورودی سامانه</dt><dd id="gross-volume"></dd>
<dt>متوسط حجم روزانه در بازه</dt><dd id="daily-volume"></dd>
<dt>زمان کل پمپاژ در بازه</dt><dd id="pump-hours"></dd>
<dt>هزینه برآوردی کل آب و انرژی</dt><dd id="water-cost"></dd></dl>
<button type="button" id="download">دریافت گزارش JSON</button></section>
<section class="card"><h2>روش، منبع و محدوده اعتبار</h2>
<p>فرمول‌های محاسباتی: <strong>ETc = Kc × ET₀</strong>؛ نیاز خالص آبیاری = بزرگ‌ترِ «ETc کل − بارش مؤثر» و صفر؛ عمق ناخالص = عمق خالص ÷ (راندمان/۱۰۰)؛ هر یک میلی‌متر آب در یک هکتار برابر ۱۰ مترمکعب است.</p>
<p><a href="https://www.fao.org/4/x0490e/x0490e0b.htm" rel="noopener noreferrer">FAO-56: ضریب گیاهی و ETc</a> · <a href="https://www.fao.org/4/w4347e/w4347e0c.htm" rel="noopener noreferrer">FAO: نیاز خالص و ناخالص آب آبیاری</a></p>
<p class="note">این محاسبه تراز سادهٔ آب طی یک بازه است، نه برنامه زمان‌بندی آبیاری. انتخاب Kc مناسب مرحله رشد، صحت ET₀ و برآورد بارش مؤثر ضروری است. ذخیره رطوبت خاک، آبشویی شوری، تنش گیاه، محدودیت دبی و تغییر راندمان با زمان در این برآورد لحاظ نمی‌شوند؛ صفرشدن نیاز خالص به معنی بی‌نیازی قطعی از آبیاری نیست. برای تصمیم مزرعه‌ای شرایط واقعی باید بررسی شوند.</p>
<p><a href="/ask-master/index.php">ثبت پرسش و استعلام خدمات</a> · <a href="/ask-master/status.php">پیگیری درخواست</a> · <a href="/topics/tools/project-economics/">محاسبه اقتصادی فعالیت</a></p></section>
</main><footer>شرکت کشت و صنعت زمرد ملل · ابزار رایگان، بدون ارسال داده · <a href="/topics/">بازگشت به موضوعات</a></footer>
<script>
(()=>{'use strict';const form=document.getElementById('water-form'),error=document.getElementById('error'),results=document.getElementById('results');let report=null;
const elt=id=>document.getElementById(id);
const read=id=>{const x=elt(id);if(!x.value.trim())throw Error('فیلد «'+x.parentElement.firstChild.textContent.trim()+'» را تکمیل کنید.');const value=Number(x.value);if(!Number.isFinite(value)||value<Number(x.min)||value>Number(x.max))throw Error('مقدار «'+x.parentElement.firstChild.textContent.trim()+'» خارج از محدودهٔ مجاز است.');return value};
const fmt=n=>new Intl.NumberFormat('fa-IR',{maximumFractionDigits:2}).format(n);
const show=(id,n,unit)=>{elt(id).textContent=fmt(n)+' '+unit};
form.addEventListener('submit',e=>{e.preventDefault();error.textContent='';results.hidden=true;report=null;
 try{const eto=read('eto'),kc=read('kc'),days=read('days'),rain=read('rain'),area=read('area'),eff=read('eff');
 if(!Number.isInteger(days))throw Error('بازه زمانی باید تعداد صحیح روز باشد.');
 const flow=elt('flow').value.trim()?read('flow'):null,cost=elt('cost').value.trim()?read('cost'):null;
 const etcDay=eto*kc,etcTotal=etcDay*days,netDepth=Math.max(0,etcTotal-rain),grossDepth=netDepth/(eff/100);
 const netVolume=netDepth*area*10,grossVolume=grossDepth*area*10,dailyVolume=grossVolume/days;
 const pumpHours=flow===null?null:grossVolume/flow,totalCost=cost===null?null:grossVolume*cost;
 if(![etcDay,etcTotal,netDepth,grossDepth,netVolume,grossVolume,dailyVolume,pumpHours??0,totalCost??0].every(Number.isFinite))throw Error('حجم محاسبه از محدودهٔ عددی مجاز خارج است.');
 report={crop:elt('crop').value.trim(),method:'FAO-56 simple crop-coefficient and irrigation efficiency scenario',periodDays:days,inputs:{etoMmPerDay:eto,kc,effectiveRainMm:rain,areaHa:area,applicationEfficiencyPct:eff,pumpFlowM3PerHour:flow,costTomanPerM3:cost},outputs:{etcMmPerDay:etcDay,etcMmPeriod:etcTotal,netIrrigationMm:netDepth,grossIrrigationMm:grossDepth,netVolumeM3:netVolume,grossVolumeM3:grossVolume,averageDailyGrossM3:dailyVolume,pumpHours,costToman:totalCost},sources:['https://www.fao.org/4/x0490e/x0490e0b.htm','https://www.fao.org/4/w4347e/w4347e0c.htm'],notice:'Scenario estimate, not a validated irrigation schedule.'};
 elt('summary').textContent=(report.crop||'سناریوی بدون عنوان')+'؛ '+fmt(days)+' روز؛ '+fmt(area)+' هکتار';
 show('etc-day',etcDay,'میلی‌متر/روز');show('etc-total',etcTotal,'میلی‌متر');show('net-depth',netDepth,'میلی‌متر');
 show('gross-depth',grossDepth,'میلی‌متر');show('net-volume',netVolume,'مترمکعب');show('gross-volume',grossVolume,'مترمکعب');show('daily-volume',dailyVolume,'مترمکعب/روز');
 elt('pump-hours').textContent=pumpHours===null?'دبی پمپ وارد نشده':fmt(pumpHours)+' ساعت';
 elt('water-cost').textContent=totalCost===null?'هزینه واحد وارد نشده':fmt(totalCost)+' تومان';results.hidden=false;
 }catch(ex){error.textContent=ex.message;}
});
form.addEventListener('reset',()=>{report=null;results.hidden=true;error.textContent=''});
elt('download').addEventListener('click',()=>{if(!report)return;const blob=new Blob([JSON.stringify(report,null,2)],{type:'application/json;charset=utf-8'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download='zomorod-irrigation-plan.json';document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),1000)});
})();
</script><!-- zm-fao-irrigation-planner-20261106:engine --></body></html>
'''

def target_files():
    if os.geteuid()==0 or os.geteuid()!=WEB.stat().st_uid:
        raise RuntimeError('REFUSE_WRONG_USER')
    if ROOT.is_symlink() or not ROOT.is_dir() or HUB.is_symlink():
        raise RuntimeError('UNSAFE_STATIC_ROOT')
    if 'PassengerEnabled off' not in (ROOT/'.htaccess').read_text(encoding='utf-8'):
        raise RuntimeError('PASSENGER_STATIC_ROUTE_CHANGED')
    manifest=json.loads((ROOT/'topic-manifest.json').read_text(encoding='utf-8'))
    if manifest.get('newPages')!=545 or manifest.get('pageCount')!=605:
        raise RuntimeError('TOPIC_COUNT_DRIFT')
    expected={a['path'].lstrip('/') for a in manifest['topics']}
    for relative,label in TARGETS.items():
        canonical='topics/'+relative.removesuffix('index.html')
        if canonical not in expected:
            raise RuntimeError('TARGET_MISSING_FROM_MANIFEST:'+canonical)
        p=ROOT/relative
        if not p.is_file() or p.is_symlink() or p.parent.is_symlink() or p.parent.parent.is_symlink():
            raise RuntimeError('UNSAFE_TOPIC_FILE:'+relative)
    if ENGINE.is_symlink() or HUB.is_symlink():raise RuntimeError('UNSAFE_TARGET')
    return [HUB]+[ROOT/p for p in TARGETS]+[ENGINE]

def patch(path,source):
    if path==ENGINE:
        if source is None:return 'new-file',ENGINE_HTML
        if source==ENGINE_HTML:return 'already-patched',source
        raise RuntimeError('EXISTING_ENGINE_DIFFERENT')
    if path==HUB:
        marker=MARKER+':hub'
        if source.count(marker)==1 and source.count(URL)==1:return 'already-patched',source
        if MARKER in source or URL in source or source.count(HUB_INSERT_BEFORE)!=1:
            raise RuntimeError('HUB_DRIFT')
        if source.count('<li><a href=')!=605 or TOPIC_HUB_MARKER not in source:
            raise RuntimeError('HUB_INDEX_OR_PRIOR_RELEASE_MISSING')
        return 'needs-patch',source.replace(HUB_INSERT_BEFORE,LINK_HUB+HUB_INSERT_BEFORE,1).replace('</main>','<!-- '+marker+' --></main>',1)
    relative=str(path.relative_to(ROOT))
    marker=MARKER+':article'
    if source.count(marker)==1 and source.count(URL)==1:return 'already-patched',source
    if MARKER in source or URL in source or source.count(ARTICLE_INSERT_BEFORE)!=1:
        raise RuntimeError('ARTICLE_DRIFT:'+relative)
    if TOPIC_ARTICLE_MARKER not in source or source.count('data-zm-dedicated-topic=')!=1:
        raise RuntimeError('PRIOR_RELEASE_MISSING:'+relative)
    if '<h1>'+TARGETS[relative]+'</h1>' not in source:
        raise RuntimeError('ARTICLE_TITLE_CHANGED:'+relative)
    if source.count('<link rel="canonical"')!=1:
        raise RuntimeError('ARTICLE_CANONICAL_MISSING:'+relative)
    return 'needs-patch',source.replace(ARTICLE_INSERT_BEFORE,LINK_TOPIC+ARTICLE_INSERT_BEFORE,1).replace('</main>','<!-- '+marker+' --></main>',1)

def inspect(files):
    output=[]
    for p in files:
        source=None if p==ENGINE and not p.exists() else p.read_text(encoding='utf-8')
        state,new=patch(p,source)
        output.append((p,state,new,source))
    return output

def backup_dir(runid):
    if not re.fullmatch(r'\d{5,20}',runid):raise RuntimeError('INVALID_RUN_ID')
    if BACKUPS.is_symlink() or BACKUPS.parent.is_symlink():raise RuntimeError('UNSAFE_BACKUP_ROOT')
    BACKUPS.mkdir(parents=True,mode=0o700,exist_ok=True)
    os.chmod(BACKUPS,0o700)
    return BACKUPS/runid

def atomic_write(path,data,mode):
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.zm-irrigation-',dir=str(path.parent))
    try:
        with os.fdopen(fd,'wb') as out:
            out.write(data);out.flush();os.fsync(out.fileno())
        os.chmod(tmp,mode);os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def publish(runid,files):
    changes=[x for x in inspect(files) if x[1]!='already-patched']
    folder=backup_dir(runid)
    if folder.exists():raise RuntimeError('BACKUP_RUN_COLLISION')
    folder.mkdir(mode=0o700)
    entries=[]
    for path,state,new,source in changes:
        relative=str(path.relative_to(ROOT)); backup=folder/relative
        backup.parent.mkdir(parents=True,exist_ok=True)
        original=b'' if source is None else source.encode('utf-8')
        with backup.open('xb') as dest:dest.write(original)
        backup.chmod(0o600)
        entries.append({'path':relative,'isNew':state=='new-file','mode':0o644 if source is None else stat.S_IMODE(path.stat().st_mode)})
    (folder/'manifest.json').write_text(json.dumps(entries),encoding='utf-8')
    written=[]
    try:
        for path,state,new,source in changes:
            if path.is_symlink():raise RuntimeError('SYMLINK_DURING_RELEASE')
            entry=next(e for e in entries if e['path']==str(path.relative_to(ROOT)))
            atomic_write(path,new.encode('utf-8'),entry['mode'])
            written.append((path,state,source,entry['mode']))
    except Exception:
        for path,state,source,mode in reversed(written):
            if state=='new-file':
                if path.read_text(encoding='utf-8')==ENGINE_HTML:path.unlink()
            else:
                atomic_write(path,source.encode('utf-8'),mode)
        raise
    print('IRRIGATION_RELEASE_FILES='+str(len(changes))+' TOPIC_ARTICLES='+str(sum(p not in (HUB,ENGINE) for p,_,_,_ in changes)))

def verify_origin(files):
    for path in files:
        if patch(path,path.read_text(encoding='utf-8'))[0]!='already-patched':
            raise RuntimeError('ORIGIN_NOT_PATCHED:'+str(path))
    print('IRRIGATION_ORIGIN_VERIFIED='+str(len(files)))

def public(path,tokens):
    req=Request('https://zomorodmelal.ir'+path,headers={'User-Agent':'Zomorod-FAO-Irrigation-Release/1.0','Cache-Control':'no-cache'})
    with urlopen(req,timeout=30) as response:
        body=response.read(1100000).decode('utf-8','replace')
        if response.status!=200 or 'noindex' in response.headers.get('X-Robots-Tag','').lower():
            raise RuntimeError('PUBLIC_HTTP_OR_ROBOTS:'+path)
    if any(token not in body for token in tokens):
        raise RuntimeError('PUBLIC_CONTENT_MISSING:'+path)

def verify_public():
    cases=[('/topics/',[MARKER+':hub',URL,TOPIC_HUB_MARKER]),
           ('/topics/zm-r09/drip-irrigation/',[MARKER+':article',URL,TOPIC_ARTICLE_MARKER]),
           ('/topics/zm-r03/greenhouse-irrigation/',[MARKER+':article',URL,TOPIC_ARTICLE_MARKER]),
           (URL,[MARKER+':engine','id="water-form"','id="gross-volume"','https://www.fao.org/4/x0490e/x0490e0b.htm'])]
    latest=None
    for attempt in range(7):
        try:
            for path,tokens in cases:public(path,tokens)
            print('IRRIGATION_PUBLIC_VERIFIED=4');return
        except Exception as e:
            latest=repr(e)
            if attempt!=6:time.sleep(5)
    raise RuntimeError('PUBLIC_CHECK_FAILED:'+str(latest))

def rollback(runid):
    folder=backup_dir(runid)
    entries=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
    for entry in entries:
        path=ROOT/entry['path']
        if path.is_symlink() or patch(path,path.read_text(encoding='utf-8'))[0]!='already-patched':
            raise RuntimeError('REFUSE_ROLLBACK_DRIFT:'+entry['path'])
    for entry in entries:
        path=ROOT/entry['path']
        if entry['isNew']:path.unlink()
        else:atomic_write(path,(folder/entry['path']).read_bytes(),entry['mode'])
    print('IRRIGATION_ROLLED_BACK='+str(len(entries)))

def selftest():
    article=('<link rel="canonical" href="x"><body data-zm-dedicated-topic="one"><main><h1>آبیاری قطره‌ای</h1>'+
             '<a style="color:#f0d08b" href="/topics/tools/project-economics/">engine</a></main><!-- '+TOPIC_ARTICLE_MARKER+' -->')
    p=ROOT/'zm-r09/drip-irrigation/index.html'
    state,new=patch(p,article)
    assert state=='needs-patch' and URL in new and patch(p,new)[0]=='already-patched'
    hub='<main>'+('<li><a href="/topics/x/">x</a></li>'*605)+HUB_INSERT_BEFORE+'</main><!-- '+TOPIC_HUB_MARKER+' -->'
    state,new=patch(HUB,hub)
    assert state=='needs-patch' and patch(HUB,new)[0]=='already-patched'
    assert patch(ENGINE,None)[0]=='new-file' and patch(ENGINE,ENGINE_HTML)[0]=='already-patched'
    assert len(TARGETS)==9
    print('IRRIGATION_SELFTEST_OK=1')

if __name__=='__main__':
    if len(sys.argv)==2 and sys.argv[1]=='selftest':selftest();sys.exit(0)
    files=target_files()
    if len(sys.argv)==2 and sys.argv[1]=='preview':
        states=[x[1] for x in inspect(files)]
        print('IRRIGATION_PREVIEW='+json.dumps({s:states.count(s) for s in set(states)},sort_keys=True))
    elif len(sys.argv)==3 and sys.argv[1]=='publish':publish(sys.argv[2],files)
    elif len(sys.argv)==3 and sys.argv[1]=='verify-origin':verify_origin(files);verify_public()
    elif len(sys.argv)==3 and sys.argv[1]=='rollback':rollback(sys.argv[2])
    else:raise RuntimeError('UNKNOWN_MODE')
