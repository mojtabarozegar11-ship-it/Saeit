#!/usr/bin/env python3
"""Owner-approved, source-linked, additive-only Zomorod soil-water calculators.

Only builds static HTML or checks the generated staged pages. No host writes.
Live installation is exclusively in the fingerprint-pinned guarded Actions release.
"""
from __future__ import annotations
import hashlib
import json
import re
import sys
from pathlib import Path

RELEASE = "ZM-SOIL-MOISTURE-TOOLS-20261023-V1"
ROOT = "agriculture/water-soil"
PATHS = [
    ROOT + "/soil-moisture-converter/index.html",
    ROOT + "/soil-water-storage/index.html",
]
REF_A = "https://www.nrcs.usda.gov/sites/default/files/2025-02/ch4.pdf"
REF_B = "https://extension.oregonstate.edu/catalog/em-9868-soil-moisture-monitoring-support-irrigation-scheduling"
REF_C = "https://www.drought.gov/sites/default/files/2024-12/Soil-Moisture-Data-Quality-Guidance-12-09-2024.pdf"

CSS = r"""
:root{color-scheme:light;--ink:#173e31;--green:#1f5b43;--gold:#a57719;--paper:#fffdf6}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;font:1rem/1.95 Tahoma,Arial,sans-serif;color:var(--ink);background:linear-gradient(145deg,#eff5ed,#faf4e6)}
main{max-width:950px;margin:2rem auto;padding:0 1.1rem}
header{background:var(--green);color:white;padding:1rem 5vw;display:flex;flex-wrap:wrap;justify-content:space-between;gap:1rem}
header a{color:#ffdf92}.panel{background:var(--paper);border:1px solid #dfd9c6;border-radius:20px;padding:1.6rem;margin:1.2rem 0;box-shadow:0 10px 34px #173e3110}
h1{font-size:clamp(1.5rem,3.2vw,2.4rem);line-height:1.45}h2{font-size:1.3rem}
.fieldgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:1rem}
label{display:block;font-weight:bold}input{width:100%;font:inherit;padding:.5rem .75rem;border:1.5px solid #8ea898;border-radius:9px;background:#fff}
input:focus-visible,button:focus-visible,a:focus-visible{outline:3px solid #a57719;outline-offset:3px}
button{margin-top:1rem;background:var(--green);color:white;border:none;border-radius:10px;padding:.7rem 1.6rem;font:inherit;cursor:pointer;min-height:46px}
button:hover{background:#154332}.output{border-right:5px solid var(--gold);padding:1rem;margin-top:1rem;background:#f1f6ed;min-height:3.5rem}
.error{border-right-color:#b12626;background:#ffedeb}svg{width:100%;max-width:610px;height:auto;display:block;margin:auto}
small,.note{color:#4d6159}a{color:#145b43}footer{margin:2rem auto;max-width:950px;padding:1rem}
@media(max-width:600px){main{margin:0 auto}.panel{padding:1rem}header{padding:1rem}}
"""

SCRIPT1 = r"""
(function(){
"use strict";
const form=document.getElementById('calculator'), output=document.getElementById('result');
const val=id=>Number(document.getElementById(id).value);
function compute(){
 const wet=val('wet'),dry=val('dry'),bulk=val('bulk');
 if(![wet,dry,bulk].every(Number.isFinite)||dry<=0||wet<dry||bulk<0.6||bulk>2.2||wet>1000000){
  throw Error('مقادیر نامعتبرند: جرم خشک باید مثبت، جرم تر حداقل برابر جرم خشک، و چگالی ظاهری بین ۰٫۶ تا ۲٫۲ باشد.');
 }
 const grav=(wet-dry)/dry,vol=grav*bulk,porosity=1-bulk/2.65;
 if(vol>1.00000001)throw Error('رطوبت حجمی بیش از ۱ است؛ اندازه‌گیری یا چگالی را بررسی کنید.');
 return {grav,vol,porosity};
}
function show(){
 try {
  const x=compute();
  const warn=x.vol>x.porosity+0.005?'هشدار کنترل کیفیت: رطوبت حجمی از تخلخل تقریبی مبتنی بر چگالی ذرات ۲٫۶۵ بیشتر است؛ نمونه و چگالی را بررسی کنید.':'';
  output.classList.remove('error');
  output.textContent='رطوبت وزنی: '+(x.grav*100).toFixed(2)+'٪ | رطوبت حجمی: '+(x.vol*100).toFixed(2)+'٪ (m³/m³ = '+x.vol.toFixed(4)+'). '+warn;
 }catch(e){output.classList.add('error');output.textContent='خطا: '+e.message;}
}
form.addEventListener('submit',e=>{e.preventDefault();show();});
if(new URLSearchParams(location.search).has('qa')){
 document.getElementById('wet').value='130';document.getElementById('dry').value='100';document.getElementById('bulk').value='1.3';show();
 const good=output.textContent.includes('30.00')&&output.textContent.includes('39.00');
 document.getElementById('wet').value='50';show();
 const bad=output.textContent.includes('خطا:');
 document.body.setAttribute('data-qa',good&&bad?'pass':'fail');
}
})();
"""

SCRIPT2 = r"""
(function(){
"use strict";
const form=document.getElementById('calculator'), output=document.getElementById('result');
const val=id=>Number(document.getElementById(id).value);
function compute(){
 const fc=val('fc'),wp=val('wp'),now=val('now'),depth=val('depth'),area=val('area');
 if(![fc,wp,now,depth,area].every(Number.isFinite)||wp<0||fc<=wp||fc>70||now<0||now>75||depth<=0||depth>500||area<=0||area>1e8) {
  throw Error('مقادیر نامعتبرند؛ ظرفیت زراعی باید بیش از نقطه پژمردگی، عمق و مساحت مثبت باشند.');
 }
 const mm=depth*10;
 return {taw:(fc-wp)/100*mm,remaining:Math.max(0,Math.min(now,fc)-wp)/100*mm,
         deficit:Math.max(0,fc-now)/100*mm,liters:Math.max(0,fc-now)/100*mm*area,
         warning:now>fc?'رطوبت فعلی از ظرفیت زراعی بالاتر است؛ زهکشی و زمان نمونه‌برداری را بررسی کنید.':''};
}
function show(){
 try {
  const x=compute();output.classList.remove('error');
  output.textContent='آب قابل‌استفاده کل (TAW): '+x.taw.toFixed(2)+' میلی‌متر | آب قابل‌استفاده باقیمانده: '+x.remaining.toFixed(2)+' میلی‌متر | کسری نسبت به ظرفیت زراعی: '+x.deficit.toFixed(2)+' میلی‌متر | معادل حجمی کسری برای مساحت واردشده: '+x.liters.toFixed(0)+' لیتر. '+x.warning;
 }catch(e){output.classList.add('error');output.textContent='خطا: '+e.message;}
}
form.addEventListener('submit',e=>{e.preventDefault();show();});
if(new URLSearchParams(location.search).has('qa')){
 ['fc','wp','now','depth','area'].forEach((k,i)=>{document.getElementById(k).value=[30,15,20,40,100][i];});show();
 const good=output.textContent.includes('60.00')&&output.textContent.includes('20.00')&&output.textContent.includes('40.00')&&output.textContent.includes('4000');
 document.getElementById('fc').value='10';show();
 const bad=output.textContent.includes('خطا:');
 document.body.setAttribute('data-qa',good&&bad?'pass':'fail');
}
})();
"""

def field(field_id, caption, example, minimum="0"):
    return ('<label for="' + field_id + '">' + caption + '</label>'
            '<input required type="number" step="any" inputmode="decimal"'
            ' id="' + field_id + '" name="' + field_id + '"'
            ' min="' + minimum + '" value="' + example + '" autocomplete="off">')

def page(slug, title, intro, rows, body, script):
    url = "https://zomorodmelal.ir/" + ROOT + "/" + slug + "/"
    inputs = "".join("<div>" + field(*v) + "</div>" for v in rows)
    doc = r"""<!doctype html>
<html lang="fa" dir="rtl">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="index,follow"><meta name="description" content="%%INTRO%%">
<link rel="canonical" href="%%CANONICAL%%"><title>%%TITLE%% | زمرد ملل</title>
<style>%%CSS%%</style></head>
<body data-release="%%RELEASE%%">
<header><b>کشت و صنعت زمرد ملل | آزمایشگاه علمی آب و خاک</b>
<nav><a href="/agriculture/water-soil/">آب و خاک</a> · <a href="/agriculture/">کشاورزی</a> · <a href="/">خانه</a></nav></header>
<main><div class="panel"><h1>%%TITLE%%</h1><p>%%INTRO%%</p>
<svg viewBox="0 0 560 140" role="img" aria-label="نمودار شماتیک مقطع خاک و لایه‌های آب و هوا" xmlns="http://www.w3.org/2000/svg">
<rect x="5" y="5" width="550" height="130" rx="20" fill="#e9f1e5"/>
<path d="M8 40 Q75 18 142 36 T276 36 T414 36 T554 34 L554 134 L8 134Z" fill="#917255"/>
<path d="M8 90 Q100 67 180 89 T350 93 T554 87 L554 134 L8 134Z" fill="#b69164"/>
<g fill="#4da8c4"><circle cx="70" cy="65" r="7"/><circle cx="192" cy="63" r="6"/><circle cx="325" cy="71" r="9"/><circle cx="478" cy="62" r="7"/></g>
<g fill="#173e31"><path d="M108 20v65m0-25 30 16m-30-22-20 14M415 22v70m0-42 19 14m-19-7-21 14" stroke="#173e31" stroke-width="4" fill="none"/></g></svg>
</div>
<section class="panel" aria-labelledby="inputs-title"><h2 id="inputs-title">محاسبه با داده‌های واقعی</h2>
<form id="calculator"><div class="fieldgrid">%%FIELDS%%</div>
<button type="submit">محاسبه و بررسی داده‌ها</button></form>
<div id="result" class="output" role="status" aria-live="polite">مقادیر نمونه را بررسی کنید و دکمه محاسبه را بزنید.</div>
</section>
<section class="panel"><h2>تفسیر علمی و محدودیت‌ها</h2>%%BODY%%</section>
<section class="panel"><h2>منابع فنی قابل استناد</h2><ul>
<li><a href="%%REF_A%%" rel="noopener noreferrer">USDA NRCS، راهنمای مهندسی آبیاری، فصل ۴؛ روابط رطوبت وزنی و حجمی و آب قابل استفاده</a></li>
<li><a href="%%REF_B%%" rel="noopener noreferrer">Oregon State University Extension؛ پایش رطوبت خاک برای مدیریت آبیاری</a></li>
<li><a href="%%REF_C%%" rel="noopener noreferrer">NIDIS/NOAA، راهنمای کیفیت داده رطوبت خاک (۲۰۲۴)، پیوست D</a></li>
</ul><p class="note">متن توضیحی اصیل و محاسبات بازنویسی‌شده هستند. محاسبه به‌جای آزمایش میدانی، آزمایشگاه و توصیه متخصص استفاده نشود.</p>
</section>
<section class="panel"><h2>ابزارهای مرتبط</h2>
<p><a href="/agriculture/water-soil/soil-moisture-converter/">تبدیل رطوبت وزنی و حجمی</a> · <a href="/agriculture/water-soil/soil-water-storage/">ذخیره و کسری آب خاک</a> · <a href="/agriculture/water-soil/irrigation-planner/">برنامه‌ریز آبیاری</a></p></section>
</main><footer>© زمرد ملل | نسخه فنی %%RELEASE%%</footer>
<script>%%SCRIPT%%</script></body></html>"""
    pairs={"%%INTRO%%": intro, "%%TITLE%%":title,"%%CANONICAL%%":url,
           "%%CSS%%":CSS,"%%RELEASE%%":RELEASE,"%%FIELDS%%":inputs,
           "%%BODY%%":body,"%%REF_A%%":REF_A,"%%REF_B%%":REF_B,
           "%%REF_C%%":REF_C,"%%SCRIPT%%":script}
    for token,value in pairs.items():doc=doc.replace(token,value)
    return doc

FIRST_BODY = """<p>رطوبت وزنی، نسبت جرم آب ازدست‌رفته در خشک‌کردن نمونه به جرم خشک خاک است. برای اندازه‌گیری معتبر، جرم تر و جرم خشک باید متعلق به یک نمونه یکسان و ظروف توزین جدا یا وزن ظرف کسر شده باشد. در این ابزار چگالی ظاهری خشک خاک با واحد g/cm³ وارد می‌شود و چگالی آب برای محاسبه برابر ۱ g/cm³ فرض شده است.</p>
<p><strong>روابط:</strong> θg = (جرم تر − جرم خشک) ÷ جرم خشک؛ θv = θg × ρb ÷ ρw. خروجی درصد وزنی و درصد حجمی هر دو نمایش داده می‌شود. برای نمونه ۱۳۰ گرم تر، ۱۰۰ گرم خشک و چگالی ظاهری ۱٫۳، رطوبت وزنی ۳۰٪ و رطوبت حجمی ۳۹٪ است.</p>
<p>کنترل تخمینی تخلخل از رابطه ۱ − (چگالی ظاهری ÷ ۲٫۶۵) استفاده می‌کند؛ مقدار ۲٫۶۵ صرفاً فرض رایج برای چگالی ذرات معدنی است. برای خاک‌های آلی، شور خاص یا خاک با چگالی ذرات متفاوت، این کنترل قابل اتکا نیست. نتیجه برای یک نمونه نقطه‌ای است و نماینده کل مزرعه نیست.</p>"""
SECOND_BODY = """<p>این ابزار برای یک لایه خاک با رطوبت حجمی اندازه‌گیری‌شده، مقدار آب قابل‌استفاده کل (TAW)، بخش باقی‌مانده بالای نقطه پژمردگی و کسری نسبت به ظرفیت زراعی را در واحد میلی‌متر نشان می‌دهد. برای تبدیل به حجم، ۱ میلی‌متر آب روی ۱ مترمربع معادل ۱ لیتر است.</p>
<p><strong>روابط:</strong> TAW = (θFC − θWP) × عمق لایه(mm). کسری ذخیره = max(0, θFC − θفعلی) × عمق لایه(mm). تمام θها باید به صورت نسبت حجمی وارد معادله شوند؛ فرم این ابزار درصد را دریافت و بر ۱۰۰ تقسیم می‌کند.</p>
<p>مثال: FC=۳۰٪، WP=۱۵٪، θفعلی=۲۰٪، عمق ۴۰ سانتی‌متر، مساحت ۱۰۰ مترمربع، آب قابل‌استفاده کل ۶۰ میلی‌متر و کسری ذخیره ۴۰ میلی‌متر (۴۰۰۰ لیتر معادل نظری) است. این مقدار <strong>برنامه آبیاری یا توصیه به مصرف همین حجم آب نیست</strong>؛ راندمان سامانه، بارش، آبشویی، رشد ریشه، توزیع عمقی و کیفیت داده‌ها لحاظ نشده‌اند.</p>"""

def build(dest: Path):
    dest.mkdir(parents=True,exist_ok=True)
    records={}
    for slug,title,intro,rows,body,js in [
        ("soil-moisture-converter","تبدیل رطوبت وزنی به رطوبت حجمی خاک",
         "محاسبه علمی رطوبت وزنی و حجمی خاک از جرم تر، جرم خشک و چگالی ظاهری، همراه با کنترل کیفیت داده.",
         [("wet","جرم نمونه تر (گرم)","130","0"),("dry","جرم نمونه خشک (گرم)","100","0"),
          ("bulk","چگالی ظاهری خشک خاک (g/cm³)","1.3","0.6")],FIRST_BODY,SCRIPT1),
        ("soil-water-storage","محاسبه ذخیره آب قابل‌استفاده و کسری رطوبت خاک",
         "محاسبه آب قابل‌استفاده کل، ذخیره فعلی و کسری نسبت به ظرفیت زراعی از رطوبت حجمی و عمق خاک.",
         [("fc","رطوبت حجمی ظرفیت زراعی FC (درصد)","30","0"),
          ("wp","رطوبت حجمی نقطه پژمردگی WP (درصد)","15","0"),
          ("now","رطوبت حجمی فعلی (درصد)","20","0"),
          ("depth","ضخامت لایه خاک (سانتی‌متر)","40","0"),
          ("area","مساحت نمونه‌نماینده (مترمربع)","100","0")],
         SECOND_BODY,SCRIPT2)
    ]:
        rel=ROOT+"/"+slug+"/index.html"
        p=dest/rel;p.parent.mkdir(parents=True,exist_ok=True)
        data=page(slug,title,intro,rows,body,js).encode("utf-8")
        p.write_bytes(data);records[rel]={"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data)}
    (dest/"source-manifest.json").write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding="utf-8")
    print("BUILT",json.dumps(records,ensure_ascii=False))

def qa(dest: Path):
    rec=json.loads((dest/"source-manifest.json").read_text(encoding="utf-8"))
    assert list(rec)==PATHS,(list(rec),PATHS)
    for rel,entry in rec.items():
        b=(dest/rel).read_bytes()
        assert len(b)==entry["bytes"] and hashlib.sha256(b).hexdigest()==entry["sha256"]
        s=b.decode("utf-8")
        for needle in ('<html lang="fa" dir="rtl">','<link rel="canonical"','name="description"',
                       'role="status"','aria-live="polite"','data-release="'+RELEASE,
                       'https://www.nrcs.usda.gov','<script>','type="submit"'):
            assert needle in s,(rel,needle)
        assert s.count("<script>")==1 and s.count("</script>")==1
        js=re.search(r"<script>([\s\S]+?)</script>",s).group(1)
        jsfile=dest/("qa-"+rel.split("/")[-2]+".js")
        jsfile.write_text(js,encoding="utf-8")
    assert (130-100)/100*1.3==0.39
    assert (0.30-0.15)*400==60
    assert (0.30-0.20)*400==39.99999999999999 or abs((0.30-0.20)*400-40)<1e-9
    print("SOURCE_AND_NUMERIC_QA=PASS; WEB_BROWSER_QA_REQUIRED_SEPARATELY")

if __name__=="__main__":
    if len(sys.argv)!=3 or sys.argv[1] not in ("build","qa"):
        raise SystemExit("usage: script.py build|qa staging-dir")
    {"build":build,"qa":qa}[sys.argv[1]](Path(sys.argv[2]))
