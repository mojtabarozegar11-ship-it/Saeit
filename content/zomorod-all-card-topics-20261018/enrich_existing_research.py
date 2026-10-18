#!/usr/bin/env python3
"""Enrich original 60 Zomorod research-directory pages, preserving their content.

Only edits a staging COPY of the full /research/directory directory.
SEO enhancements include Open Graph, Twitter and WebPage/BreadcrumbList JSON-LD.
Adds substantive scientific methodology and measurement sections to every page.
Never claims that a lab is accredited or that a service actually exists.
"""
from pathlib import Path
import argparse
import html
import json
import re
import importlib.util

MARK="zm-existing-research-expert-enrichment-20261018"
BASE="https://zomorodmelal.ir"
FAMILIES={
"units":(
  "مسئله پژوهشی باید با متغیر وابسته قابل سنجش و زمینه زیستی یا صنعتی مشخص تعریف شود. در مطالعه ژنتیک و زیست‌فناوری باید طراحی نمونه‌گیری، آزمون کنترل و تفسیر اثرات ژنتیکی و محیطی مشخص باشند.",
  "انتخاب روش آزمایش، تحلیل آماری با کنترل چندگانگی در صورت لزوم، ارزیابی تکرارپذیری و گزارش اندازه اثر پیش از توسعه فناوری ضرورت دارد.",
  "نشانگرهای مولکولی، داده‌های فنوتیپی، پارامترهای فیزیولوژیکی، کیفیت نمونه یا شاخص‌های اعتبار مدل با توجه به سؤال علمی انتخاب می‌شوند. هیچ مجموعه ثابتی از شاخص‌ها برای تمام زیررشته‌ها معتبر نیست.",
  "در انتقال نتیجه به مزرعه، صنعت یا محیط انسانی باید دامنه تعمیم، عوامل مخدوش‌گر، عدم‌قطعیت و ملاحظات اخلاقی و ایمنی جداگانه بررسی شوند.",
),
"laboratories":(
  "فعالیت آزمایشگاهی با شناسایی نمونه، تعریف ماتریس سنجش و تشخیص محدوده کاربرد روش آغاز می‌شود. انتخاب روش باید بر اساس ماده مورد آزمون، حد تشخیص و هدف گزارش صورت گیرد.",
  "اعتبارسنجی روش، نمونه شاهد، کالیبراسیون و ثبت شرایط محیطی برای کنترل صحت و دقت ضروری است. عدم‌قطعیت، تکرارپذیری و زنجیره ردیابی باید متناسب با نوع آزمون گزارش شوند.",
  "شاخص‌های تحلیلی می‌توانند شامل صحت، دقت، حساسیت، ویژگی، حد تشخیص و بازیابی باشند؛ کاربرد هر شاخص به ماهیت روش و نمونه بستگی دارد.",
  "اشاره به ISO/IEC 17025 به‌عنوان مرجع شناخت اصول مدیریت کیفیت است و هیچ‌گونه ادعای دریافت تأییدیه یا اعتباربخشی برای آزمایشگاه‌های شرکت ایجاد نمی‌کند.",
),
"centers":(
  "برنامه یک مرکز پژوهشی با شناسایی پرسش‌های علمی اولویت‌دار، نقشه راه پژوهش و بررسی شکاف دانشی قابل تعریف است.",
  "برای هر طرح باید فرضیه قابل آزمون، روش گردآوری داده، طراحی آزمایش، اخلاق پژوهش و معیار تصمیم‌گیری از پیش تدوین شود.",
  "پیشرفت علمی تنها با شمار پروژه‌ها قابل ارزیابی نیست؛ کیفیت داده، قابلیت بازتولید نتایج، انتقال دانش و اعتبارسنجی مستقل شاخص‌های اصلی‌اند.",
  "کاربرد احتمالی نتایج باید با امکان‌سنجی اقتصادی، ایمنی، اثر محیطی و انطباق قانونی همراه شود؛ برنامه آینده معادل دستاورد تحقق‌یافته نیست.",
)
}
def esc(v):return html.escape(str(v),quote=True)
def load_group_catalog(path):
    sp=importlib.util.spec_from_file_location("zm_research_catalog",path)
    module=importlib.util.module_from_spec(sp);sp.loader.exec_module(module)
    groups={}
    for rid,title,kind,description,raw in module.GROUPS:
        groups[kind]=(title,{slug:(name,summary) for name,slug,summary in module.items(raw)})
    assert {k:len(v[1]) for k,v in groups.items()} == {"units":20,"laboratories":20,"centers":20}
    return groups
def make_detail(kind,title,summary):
    question={
     "units":f"در حوزه «{title}»، کدام مکانیسم زیستی یا رابطه فنی با شواهد و طراحی آزمایش قابل تمایز از عوامل محیطی است؟",
     "laboratories":f"در ارزیابی تخصصی «{title}»، روش آزمون در چه ماتریس، محدوده سنجش و سطح عدم‌قطعیت معتبر خواهد بود؟",
     "centers":f"برای برنامه مطالعاتی «{title}»، اولویت مسئله، فرضیه علمی و معیار تصمیم برای ادامه پژوهش چیست؟",
    }[kind]
    return question,summary
def enrich(page,kind,slug,title,summary):
    a=page.read_text(encoding="utf-8")
    if MARK in a:raise ValueError("Already enriched: "+str(page))
    if a.count("</head>")!=1 or a.count("</main>")!=1 or a.count("<h1>")!=1:
        raise ValueError("Unexpected page markup: "+str(page))
    if title not in a:raise ValueError("Topic title mismatch")
    source_url=f"/research/directory/{kind}/{slug}/"
    canon=BASE+source_url
    family=FAMILIES[kind]
    desc=f"{title} در مرکز تحقیقات زمرد ملل؛ معرفی تخصصی، چارچوب علمی، روش‌شناسی، شاخص‌های ارزیابی، الزامات کیفیت و مرزهای اعتبار نتایج."
    desc=desc[:182]
    struct=[{"@context":"https://schema.org","@type":"WebPage","inLanguage":"fa-IR","url":canon,
      "name":f"{title} | {kind} | زمرد ملل","description":desc,
      "publisher":{"@type":"Organization","name":"شرکت کشت و صنعت زمرد ملل","url":BASE+"/"}},
      {"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[
      {"@type":"ListItem","position":1,"name":"خانه","item":BASE+"/"},
      {"@type":"ListItem","position":2,"name":"مراکز و واحدهای تحقیقات","item":BASE+"/topics/"},
      {"@type":"ListItem","position":3,"name":title,"item":canon}]}]
    schema_text=json.dumps(struct,ensure_ascii=False).replace("</", "<\\/")
    head=(f'<meta property="og:type" content="article">'
      f'<meta property="og:site_name" content="زمرد ملل">'
      f'<meta property="og:title" content="{esc(title)} | زمرد ملل">'
      f'<meta property="og:description" content="{esc(desc)}">'
      f'<meta property="og:url" content="{esc(canon)}">'
      f'<meta property="og:image" content="{BASE}/static/site/zomorod-v7/company-logo.webp">'
      f'<meta name="twitter:card" content="summary">'
      f'<meta name="twitter:title" content="{esc(title)}">'
      f'<script type="application/ld+json">{schema_text}</script>')
    question,scope=make_detail(kind,title,summary)
    blocks=[
      ("پرسش محوری و دامنه تخصص",f"{question} موضوع محوری این صفحه، {scope} است. برای پاسخ معتبر، تعریف جمعیت مطالعه، شرایط آزمون و محدوده تعمیم باید دقیق باشد."),
      ("رویکرد روش‌شناختی",family[0]+" "+family[1]),
      ("شاخص‌های سنجش و تحلیل نتایج",family[2]+f" در موضوع «{title}» گزارش صرف میانگین بدون ارزیابی پراکندگی و منشأ خطا برای نتیجه‌گیری کفایت نمی‌کند."),
      ("ملاحظات کیفیت، ایمنی و اخلاق",family[3]),
      ("کاربرد و همکاری پژوهشی",f"کاربرد احتمالی دانش مربوط به «{title}» در قالب طرح مشخص، پس از ارزیابی نیاز واقعی، امکانات و صلاحیت‌ها، بودجه و خطرپذیری سنجیده می‌شود. این معرفی به معنای ارائه خدمت، ظرفیت عملیاتی یا نتیجه پژوهشی تأییدشده نیست.")
    ]
    sections="".join(f'<section class="panel"><h2>{esc(t)}</h2><p>{esc(txt)}</p></section>' for t,txt in blocks)
    extra=f'''<!-- {MARK} --><section class="zm-scientific-extension" aria-label="راهنمای تخصصی {esc(title)}">
<h2>چارچوب تخصصی، روش ارزیابی و مرزهای اعتبار علمی</h2>
{sections}
<p><a href="/topics/">بازگشت به فهرست کامل موضوعات تخصصی زمرد ملل</a></p>
</section>'''
    b=a.replace("</head>",head+"\n</head>",1)
    b=b.replace("</main>",extra+"\n</main>",1)
    assert b.count(MARK)==1 and b.count("application/ld+json")==1
    assert b.count('property="og:title"')==1
    assert b.replace(head+"\n","",1).replace(extra+"\n","",1)==a
    page.write_text(b,encoding="utf-8")

def main():
    arg=argparse.ArgumentParser()
    arg.add_argument("--pages-root",type=Path,required=True)
    arg.add_argument("--definitions",type=Path,required=True)
    opt=arg.parse_args()
    groups=load_group_catalog(opt.definitions)
    count=0
    for kind,(family_title,items) in groups.items():
        for slug,(name,summary) in items.items():
            page=opt.pages_root/kind/slug/"index.html"
            if not page.is_file():raise FileNotFoundError(str(page))
            enrich(page,kind,slug,name,summary)
            count+=1
    if count!=60 or len(list(opt.pages_root.rglob("index.html")))!=60:
        raise ValueError("Research directory is unexpected")
    print("RESEARCH_PAGE_EXPERT_EXTENSIONS=60")
    print("PREEXISTING_RESEARCH_CONTENT_PRESERVED=yes")
    print("ALL_RESEARCH_OPEN_GRAPH_AND_JSONLD=yes")
if __name__=="__main__":main()
