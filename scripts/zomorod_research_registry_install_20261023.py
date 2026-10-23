#!/usr/bin/env python3
"""Install a reversible, evidence-safe Zomorod scientific project register.

Clones the *existing* research page shell to retain real live branding.
Creates a new page and empty verified dataset (never fabricates projects),
links from the original research landing page, and installs a private updater.
GitHub Actions serves solely as an authenticated SSH relay to cPanel.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
from pathlib import Path

MARKER = "zm-research-registry-link-20261023"
PAGE_MARKER = "zm-research-project-directory-20261023"
TITLE = "شناسنامه طرح‌های پژوهشی و ژنتیکی | زمرد ملل"
DESCRIPTION = ("فهرست شناسنامه و وضعیت طرح‌های علمی شرکت کشت و صنعت زمرد ملل؛ "
               "قواعد ثبت شناسه، مسئول پژوهش، روش، مراحل اجرا و مدارک مجاز به انتشار.")
PAGE_MAIN = """<main id="main">
<section class="zm-hero" aria-labelledby="zm-registry-h1"><div class="zm-container zm-hero-inner">
<div><span class="zm-overline">ZOMOROD MELAL · RESEARCH TRANSPARENCY</span>
<h1 id="zm-registry-h1">شناسنامه <em>طرح‌های پژوهشی</em> و ژنتیکی</h1>
<p>این سامانه برای انتشار شفاف اطلاعات طرح‌های واقعی علمی طراحی شده است: شناسه یکتا، مسئول علمی، مسئله و روش، مرحله پیشرفت و پیوند مستندات مجاز به انتشار. تنها پرونده‌های پذیرفته‌شده در کنترل مستندات در فهرست عمومی نمایش داده می‌شوند.</p>
<div class="zm-actions"><a class="zm-link" href="/research/">بازگشت به حوزه پژوهش ←</a>
<a class="zm-link zm-link-ghost" href="/contact/">درخواست همکاری علمی ↗</a></div></div>
<figure><img src="/static/site/heroes/research.webp" alt="تصویر موضوعی روش‌های پژوهش علمی در زمرد ملل" width="800" height="640" loading="eager"></figure>
</div></section>
<section class="zm-page-section" id="zm-research-project-directory-20261023" aria-labelledby="zm-registry-list-title">
<div class="zm-container"><div class="zm-section-head"><div>
<span class="zm-eyebrow">PUBLIC RESEARCH PROJECT RECORDS</span>
<h2 id="zm-registry-list-title">فهرست عمومی قابل جست‌وجو</h2></div>
<p>عدد این فهرست از پرونده‌های واقعیِ دارای مستندات و مجوز انتشار محاسبه می‌شود. درج موضوع پژوهشی، ساخت واحد تخصصی یا تولید محتوای آموزشی به‌تنهایی پروژه تکمیل‌شده نیست.</p></div>
<div class="zm-registry-overview" role="group" aria-label="شاخص‌های ثبت پروژه">
<div><strong id="zm-registry-count">۰</strong><span>پرونده عمومی دارای مجوز انتشار</span></div>
<div><strong>۹۰٪</strong><span>سهم اعلام‌شده پژوهش علمی و ژنتیکی از فعالیت شرکت</span></div>
<div><strong>۷ معیار</strong><span>شناسه، عنوان، مسئول، روش، مرحله، شاهد و مجوز انتشار</span></div></div>
<div class="zm-registry-controls">
<label for="zm-registry-search">جست‌وجوی عنوان، شناسه و مسئول علمی
<input id="zm-registry-search" type="search" placeholder="مثلاً ژنتیک، شناسه طرح یا مسئول پژوهش" autocomplete="off"></label>
<label for="zm-registry-status">مرحله طرح
<select id="zm-registry-status"><option value="">همه مراحل</option>
<option value="registered">ثبت اولیه</option><option value="in_progress">در حال اجرا</option>
<option value="analysis">تحلیل داده</option><option value="completed">گزارش تکمیل‌شده</option>
<option value="published">منتشرشده</option></select></label>
</div>
<div id="zm-registry-results" class="zm-registry-results" aria-live="polite" aria-atomic="true">
<div class="zm-registry-empty"><h3>هنوز پرونده پژوهشی قابل‌انتشار ثبت نشده است</h3>
<p>این وضعیت به معنای نبود فعالیت علمی در شرکت نیست؛ یعنی هنوز پرونده‌ای با شناسه معتبر، مسئول علمی، روش، مدرک و مجوز انتشار در این فهرست ثبت نشده است. این سامانه پروژه یا تأییدیه ساختگی تولید نمی‌کند.</p></div>
</div>
<p class="zm-registry-disclaimer">اطلاعات پرونده‌های آینده طبق اسناد اعلامی ارائه می‌شوند. تأیید مستقل روش، نتایج یا صلاحیت متخصص تنها وقتی ادعا می‌شود که گواه معتبر آن جداگانه قابل بررسی باشد.</p>
</div></section>
<section class="zm-page-section" aria-labelledby="zm-registry-themes-title"><div class="zm-container">
<div class="zm-section-head"><div><span class="zm-eyebrow">SCIENTIFIC THEMES · NOT VERIFIED RESULTS</span>
<h2 id="zm-registry-themes-title">حوزه‌های مطالعاتی، نه پروژه‌های تأییدشده</h2></div>
<p>چهار حوزه زیر از زمینه‌های اعلام‌شده تحقیق و توسعه شرکت‌اند و نباید با پروژه دارای نتیجه عملیاتی یا مقاله داوری‌شده اشتباه گرفته شوند.</p></div>
<div class="zm-card-grid">
<article class="zm-card"><span>01 / محور علمی</span><h3>ژنتیک مولکولی و ژنومیک</h3><p>بررسی روش‌های تحلیل توالی، تنوع ژنتیکی و تفسیر داده‌های مولکولی در طرح‌های قابل تعریف.</p><a href="/agriculture/genetics/">شناخت حوزه ژنتیک ←</a></article>
<article class="zm-card"><span>02 / محور علمی</span><h3>اصلاح نژاد گیاه، دام و طیور</h3><p>چارچوب ثبت شجره، صفات اندازه‌گیری‌شده، طراحی آزمایش و معیار سنجش پیشرفت اصلاح نژادی.</p><a href="/research/">اصول روش پژوهش ←</a></article>
<article class="zm-card"><span>03 / محور علمی</span><h3>بیوانفورماتیک و هوش مصنوعی زیستی</h3><p>مدیریت داده، مدل‌سازی و ارزیابی خطا، سوگیری و بازتولیدپذیری تحلیل‌های زیستی.</p><a href="/research/directory/units/molecular-genetics/">واحد ژنتیک مولکولی ←</a></article>
<article class="zm-card"><span>04 / محور علمی</span><h3>میکروبیولوژی و غذاهای فراسودمند</h3><p>صورت‌بندی مسئله و معیارهای آزمون کیفیت در میکروبیولوژی و فرمولاسیون غذایی؛ بدون ادعای محصول یا نتیجه آزمایشگاهیِ تکمیل‌شده.</p><a href="/contact/">ارتباط پژوهشی ←</a></article>
</div></div></section>
<section class="zm-page-section" aria-labelledby="zm-registry-gate-title"><div class="zm-container">
<div class="zm-section-head"><div><span class="zm-eyebrow">SCIENTIFIC RECORD · QUALITY GATE</span>
<h2 id="zm-registry-gate-title">شرایط ثبت هر شناسنامه واقعی</h2></div>
<p>انتشار صرفاً پس از تکمیل اطلاعات و کنترل اجازه انتشار صورت می‌گیرد. اطلاعات محرمانه، داده شخصی، نمونه زیستی و اسناد بدون مجوز به سایت عمومی منتقل نمی‌شوند.</p></div>
<ol class="zm-registry-steps"><li>ثبت شناسه یکتا و عنوان روشن پژوهش.</li>
<li>ثبت نام مسئول علمی واقعی و حوزه تخصص.</li>
<li>توصیف روش، جمعیت مورد مطالعه، داده و محدودیت‌ها.</li>
<li>مشخص‌کردن مرحله اجرا و تاریخ آخرین به‌روزرسانی.</li>
<li>ارائه مدارک مجاز با پیوند HTTPS و اثرانگشت SHA-256.</li>
<li>ثبت مجوز صریح انتشار هر پرونده در بایگانی خصوصی.</li>
<li>ارزیابی وضعیت ادعاها و درج عمومی بدون ادعای تأییدیه مستقلِ اثبات‌نشده.</li></ol>
<p><a class="zm-link" href="/about/">درباره شرکت و مأموریت پژوهشی ←</a></p>
</div></section>
</main>"""
STYLES = """<style id="zm-research-registry-style-20261023">
.zm-registry-overview{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin:24px 0 30px}
.zm-registry-overview>div{border:1px solid rgba(222,188,99,.35);border-radius:18px;background:rgba(249,224,160,.05);padding:22px;display:flex;flex-direction:column;gap:10px;min-height:120px}
.zm-registry-overview strong{font-size:clamp(29px,3.3vw,47px);color:#f5d78b;line-height:1.15}
.zm-registry-overview span{line-height:1.8}
.zm-registry-controls{display:grid;grid-template-columns:minmax(0,2fr) minmax(190px,1fr);gap:16px;margin:10px 0 26px}
.zm-registry-controls label{display:flex;flex-direction:column;gap:10px;font-weight:700}
.zm-registry-controls input,.zm-registry-controls select{font:inherit;min-height:52px;width:100%;padding:10px 15px;border:1px solid rgba(235,202,121,.55);border-radius:12px;color:#f9efca;background:#213b29}
.zm-registry-controls input::placeholder{color:#d5d6c5}
.zm-registry-controls input:focus-visible,.zm-registry-controls select:focus-visible{outline:3px solid #eec66c;outline-offset:2px}
.zm-registry-empty{padding:30px;border:1px dashed rgba(241,206,122,.6);background:rgba(12,30,16,.23);border-radius:18px}
.zm-registry-empty h3{color:#f6d88a;margin:0 0 15px}
.zm-registry-empty p,.zm-registry-disclaimer{line-height:2}
.zm-registry-disclaimer{opacity:.85;font-size:.94em}
.zm-registry-results{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}
.zm-registry-results:has(.zm-registry-empty){grid-template-columns:1fr}
.zm-registry-record{border:1px solid rgba(235,202,121,.45);border-radius:18px;background:rgba(255,255,255,.04);padding:24px}
.zm-registry-record h3{color:#f5d78b;margin:10px 0}
.zm-registry-record p{line-height:1.9}
.zm-registry-record small{opacity:.85}
.zm-registry-record details{padding:8px 0}
.zm-registry-record summary{cursor:pointer;color:#efd18d;font-weight:700}
.zm-registry-record a{color:#f5d78b}
.zm-registry-steps{columns:2;column-gap:48px;margin:18px 0 28px;padding-inline-start:28px;line-height:2.5}
.zm-registry-steps li{break-inside:avoid;padding-inline-start:7px}
@media(max-width:800px){.zm-registry-overview,.zm-registry-controls,.zm-registry-results{grid-template-columns:1fr}.zm-registry-steps{columns:1}}
</style>"""
SCRIPT = """<script id="zm-research-registry-app-20261023">
(function(){
"use strict";
const root=document.getElementById("zm-registry-results");
const count=document.getElementById("zm-registry-count");
const search=document.getElementById("zm-registry-search");
const status=document.getElementById("zm-registry-status");
if(!root||!count||!search||!status)return;
const labels={registered:"ثبت اولیه",in_progress:"در حال اجرا",analysis:"تحلیل داده",completed:"گزارش تکمیل‌شده",published:"منتشرشده"};
const domain={genetics:"ژنتیک",plant_breeding:"اصلاح نژاد گیاهی",animal_breeding:"اصلاح نژاد دامی",bioinformatics:"بیوانفورماتیک",microbiology:"میکروبیولوژی",functional_food:"غذای فراسودمند",agricultural_economics:"اقتصاد کشاورزی",other:"سایر تحقیقات"};
let rows=[];
function el(tag,cls,txt){const n=document.createElement(tag);if(cls)n.className=cls;if(txt!==undefined)n.textContent=String(txt);return n;}
function empty(message){root.replaceChildren();const box=el("div","zm-registry-empty");box.append(el("h3","",message),el("p","","نمایش اطلاعات تنها پس از ثبت مسئول علمی، روش، مدارک و مجوز انتشار مجاز است. حوزه‌های موضوعی پایین صفحه، پروژه تأییدشده محسوب نمی‌شوند."));root.append(box);}
function render(){
const term=search.value.trim().toLocaleLowerCase("fa");
const selected=status.value;
const filtered=rows.filter(p=>(!selected||p.status===selected)&&(!term||[p.id,p.title,p.lead,p.summary].join(" ").toLocaleLowerCase("fa").includes(term)));
root.replaceChildren();
if(!filtered.length){empty(rows.length?"هیچ پرونده‌ای با این جست‌وجو یافت نشد":"هنوز هیچ پرونده مستندِ مجاز برای انتشار عمومی ثبت نشده است");return;}
for(const p of filtered){
const card=el("article","zm-registry-record");
card.append(el("small","",p.id+" · "+(domain[p.domain]||"پژوهش")));
card.append(el("h3","",p.title),el("p","",p.summary));
card.append(el("p","","مسئول علمی: "+p.lead),el("p","","مرحله: "+(labels[p.status]||"نامشخص")+" · بازبینی: "+p.updated_on));
const d=el("details");d.append(el("summary","","روش‌شناسی و محدودیت‌های ثبت‌شده"),el("p","",p.method));card.append(d);
const e=el("details");e.append(el("summary","","مستندات اعلامی و مجاز برای دسترسی عمومی"));
const ul=el("ul");for(const ev of p.evidence||[]){const li=el("li");const a=el("a","",ev.title);a.href=ev.url;a.rel="noopener noreferrer";a.target="_blank";li.append(a,el("small",""," · SHA-256: "+ev.sha256));ul.append(li);}e.append(ul);card.append(e);
card.append(el("small","","اطلاعات به اتکای مدارک ارائه‌شده شرکت منتشر شده؛ استقلال داوری یا نتیجه آزمایشگاهی ادعا نمی‌شود."));
root.append(card);
}
}
search.addEventListener("input",render);
status.addEventListener("change",render);
fetch("./projects.json",{cache:"no-store",credentials:"omit"})
.then(r=>{if(!r.ok)throw Error("registry unavailable");return r.json();})
.then(data=>{if(data.schema_version!==1||!Array.isArray(data.projects))throw Error("invalid data");rows=data.projects;count.textContent=String(rows.length).replace(/[0-9]/g,x=>"۰۱۲۳۴۵۶۷۸۹"[Number(x)]);render();})
.catch(()=>{empty("فهرست پژوهش موقتاً بارگذاری نشد؛ دستاورد تأییدشده‌ای نمایش داده نمی‌شود");});
})();
</script>"""
LINK_BLOCK = """<section class="zm-page-section" id="zm-research-registry-link-20261023">
<div class="zm-container"><div class="zm-section-head"><div><span class="zm-eyebrow">RESEARCH RECORDS · PUBLIC REGISTER</span>
<h2>سامانه ثبت و پیگیری طرح‌های پژوهشی</h2></div>
<p>برای تفکیک موضوعات تحقیق از پروژه‌های واقعاً دارای مدارک و مجوز انتشار، شناسنامه‌های پژوهشی در صفحه‌ای مستقل با امکان جست‌وجو، شناسه، وضعیت اجرا و پیوند شواهد ثبت می‌شوند.</p>
</div><p><a class="zm-link" href="/research/projects/">مشاهده فهرست و شرایط ثبت پروژه‌های پژوهشی ←</a></p>
</div></section>
"""
EMPTY_DATA = {
    "schema_version": 1,
    "generated_at": "2026-10-23",
    "verification_notice": "No named scientific project with evidence and publication authorization has yet been verified for the public registry.",
    "projects": [],
}
META = re.compile(r'<meta name="description" content="[^"]*">')
TITLE_RE = re.compile(r"<title>[^<]+</title>")
MAIN = re.compile(r'<main id="main">.*?</main>',re.S)

def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def build(source: bytes) -> tuple[bytes, bytes, bytes]:
    s = source.decode("utf-8")
    assert "zm-research-rd-focus-20261023" in s, "research focus baseline missing"
    assert MARKER not in s and PAGE_MARKER not in s, "already deployed"
    assert s.count('<main id="main">') == 1 and s.count("</main>") == 1
    assert s.count('<section class="zm-next">') == 1
    assert len(META.findall(s)) == 1 and len(TITLE_RE.findall(s)) == 1
    assert s.count("</head>") == 1 and s.count("</body>") == 1
    linked = s.replace('<section class="zm-next">',LINK_BLOCK+'\n<section class="zm-next">',1)
    page = MAIN.sub(lambda _:PAGE_MAIN, s, count=1)
    page = META.sub('<meta name="description" content="'+DESCRIPTION+'">',page,count=1)
    page = TITLE_RE.sub("<title>"+TITLE+"</title>",page,count=1)
    page = page.replace("</head>",STYLES+"\n</head>",1)
    page = page.replace("</body>",SCRIPT+"\n</body>",1)
    assert linked.count('id="'+MARKER+'"') == 1
    assert page.count('id="'+PAGE_MARKER+'"') == 1
    assert '<a class="zm-link" href="/research/projects/">' in linked
    assert '<meta name="viewport"' in page
    assert "zm-registry-results" in page and "projects.json" in page
    assert "/static/site/heroes/research.webp" in page
    return linked.encode("utf-8"),page.encode("utf-8"),(json.dumps(EMPTY_DATA,ensure_ascii=False,separators=(",",":"))+"\n").encode("utf-8")

def paths() -> tuple[Path,Path,Path]:
    home=Path.home()
    root=home/"public_html"
    landing=root/"research"/"index.html"
    target=root/"research"/"projects"
    assert root.is_dir() and not root.is_symlink()
    assert landing.is_file() and not landing.is_symlink()
    return root,landing,target

def archive_path(raw: str,root:Path) -> Path:
    value=Path(raw)
    assert value.is_absolute() and not value.is_symlink()
    assert value.resolve().is_relative_to(Path.home().resolve())
    assert not value.resolve().is_relative_to(root.resolve())
    return value

def updater_path(raw: str,root:Path) -> Path:
    return archive_path(raw,root)

def atomic_replace(path: Path,data:bytes):
    temp=path.with_name(".index.registry-next-20261023")
    assert not temp.exists() and not temp.is_symlink()
    with temp.open("xb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(temp,0o644)
    os.replace(temp,path)

def publish(raw:str,updater:str):
    root,landing,target=paths()
    archive=archive_path(raw,root)
    cli=updater_path(updater,root)
    assert cli.is_file() and not cli.is_symlink() and cli.stat().st_size>1000
    assert not archive.exists() and not target.exists() and not target.is_symlink()
    old=landing.read_bytes()
    new,html,data=build(old)
    archive.mkdir(parents=True,mode=0o700)
    (archive/"previous-research-index.html").write_bytes(old)
    staged=archive/"staged-projects"
    staged.mkdir(mode=0o700)
    (staged/"index.html").write_bytes(html)
    (staged/"projects.json").write_bytes(data)
    os.chmod(staged/"index.html",0o644)
    os.chmod(staged/"projects.json",0o644)
    os.chmod(staged,0o755)
    manifest={"landing_old":sha(old),"landing_new":sha(new),
              "page":sha(html),"data":sha(data)}
    (archive/"manifest.json").write_text(json.dumps(manifest),encoding="utf-8")
    private=Path.home()/".private"/"zomorod-research-registry"
    private.mkdir(parents=True,exist_ok=True,mode=0o700)
    installed_cli=private/"registry_updater.py"
    assert not installed_cli.exists() and not installed_cli.is_symlink(),"existing updater; refusing replacement"
    shutil.copyfile(cli,installed_cli)
    os.chmod(installed_cli,0o700)
    try:
        os.replace(staged,target)
        assert sha(landing.read_bytes())==manifest["landing_old"],"concurrent research homepage edit"
        atomic_replace(landing,new)
        verify(raw)
    except BaseException:
        if sha(landing.read_bytes())==manifest["landing_new"]:
            atomic_replace(landing,old)
        if target.is_dir() and not target.is_symlink():
            os.replace(target,archive/"rolled-back-projects")
        raise
    print("RESEARCH_REGISTRY_PUBLICATION=published")
    print("PRIVATE_UPDATER_INSTALLED=yes")

def verify(raw:str):
    root,landing,target=paths()
    archive=archive_path(raw,root)
    manifest=json.loads((archive/"manifest.json").read_text(encoding="utf-8"))
    assert target.is_dir() and not target.is_symlink()
    for path,key in [(landing,"landing_new"),(target/"index.html","page"),(target/"projects.json","data")]:
        assert path.is_file() and not path.is_symlink()
        assert sha(path.read_bytes())==manifest[key],f"unexpected change: {path}"
    data=json.loads((target/"projects.json").read_text(encoding="utf-8"))
    assert data["schema_version"]==1 and data["projects"]==[]
    assert MARKER.encode() in landing.read_bytes()
    assert PAGE_MARKER.encode() in (target/"index.html").read_bytes()
    print("RESEARCH_REGISTRY_VERIFY=success")

def rollback(raw:str):
    root,landing,target=paths()
    archive=archive_path(raw,root)
    manifest=json.loads((archive/"manifest.json").read_text(encoding="utf-8"))
    old=(archive/"previous-research-index.html").read_bytes()
    assert sha(old)==manifest["landing_old"]
    assert sha(landing.read_bytes())==manifest["landing_new"],"concurrent homepage edit; no rollback"
    assert sha((target/"index.html").read_bytes())==manifest["page"],"concurrent registry edit; no rollback"
    assert sha((target/"projects.json").read_bytes())==manifest["data"],"concurrent registry edit; no rollback"
    os.replace(target,archive/"rolled-back-projects")
    atomic_replace(landing,old)
    assert sha(landing.read_bytes())==manifest["landing_old"]
    print("RESEARCH_REGISTRY_ROLLBACK=success; page preserved privately")

def selftest():
    fixture=('<html lang="fa" dir="rtl"><head><title>پژوهش و توسعه | زمرد ملل</title>'
             '<meta name="viewport" content="width=device-width,initial-scale=1">'
             '<meta name="description" content="old"></head><body><header>original header</header>'
             '<main id="main"><section class="zm-hero">hero</section>'
             '<section class="zm-next">next</section><section id="zm-research-rd-focus-20261023">baseline</section>'
             '</main><footer>original footer</footer></body></html>').encode()
    linked,page,data=build(fixture)
    assert b"original header" in page and b"original footer" in page
    assert b"original header" in linked and b"original footer" in linked
    assert "شناسنامه".encode() in page
    assert b"original research" not in page
    assert len(page)>len(fixture)
    assert json.loads(data)["projects"]==[]
    try:
        build(linked)
        raise AssertionError("duplicate patch accepted")
    except AssertionError as exc:
        assert "already deployed" in str(exc)
    print("RESEARCH_REGISTRY_INSTALLER_SELFTEST=passed")

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=["selftest","publish","verify","rollback"])
    p.add_argument("--backup",default="")
    p.add_argument("--updater",default="")
    a=p.parse_args()
    if a.action=="selftest":
        selftest()
    elif a.action=="publish":
        assert a.backup and a.updater
        publish(a.backup,a.updater)
    elif a.action=="verify":
        assert a.backup
        verify(a.backup)
    else:
        assert a.backup
        rollback(a.backup)
