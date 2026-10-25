#!/usr/bin/env python3
"""Atomic, isolated, owner-authorized publication of six evergreen resource pages and two indexes.
No account/social API, payment, database, app code or existing site file is touched.
"""
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import sys

RELEASE = "organic-resource-pages-20261025-v1"
HOME = Path("/home/zomorod2")
STAGE_PREFIX = ".organic-resource-stage-"
ROOTS = {
    "mpw": HOME / "mojplaywin.com" / "mpw-learning" / "20261025",
    "zm": HOME / "public_html" / "resources" / "20261025",
}
DATA = {
    "mpw": [
        ("chess-baseline", "Chess Training Baseline: A Measurable First Week",
         "Establish a baseline before committing to a long chess training plan.",
         [
          ("Day 1: record, do not guess", "Play two games at your usual time control. Save the PGN, clock times and one critical position per game. Record how many moves were made without checking threats."),
          ("Days 2–3: calculation discipline", "Solve five tactical positions per day without moving pieces. Write candidate moves, forcing replies and your final variation. Compare with the solution only after committing."),
          ("Days 4–5: endgame fundamentals", "Practise king-and-pawn opposition, basic rook activity and conversion of an extra pawn. Record whether you can explain the winning or drawing plan."),
          ("Days 6–7: review and prioritize", "Replay the initial games without an engine, identify your three largest recurring errors, then use an engine only to test the hypotheses. Choose one tactical, one strategic and one time-management priority."),
          ("Progress metric", "Track blunders per game, tactical accuracy on a fixed set of positions, and minutes of focused analysis. Compare like-for-like time controls; a seven-day change is not proof of long-term improvement."),
         ],
         "https://mojplaywin.com/mpw-free-tools/20261025/chess-calendar/",
         "Open the free 84-day calendar builder",
         "https://mojplaywin.com/store/product/72/",
         "Explore the chess digital book"),
        ("family-storytime", "Family Storytime: A 15-Minute Read-Aloud Routine",
         "A simple, low-pressure reading session that encourages conversation and imagination.",
         [
          ("Minutes 0–2: invite prediction", "Look at the cover or a selected illustration together. Ask what might happen next and accept multiple possible answers."),
          ("Minutes 2–8: read interactively", "Read aloud at a comfortable pace. Pause twice to ask about a character's feelings, choices or observations; do not interrupt every sentence."),
          ("Minutes 8–11: retell", "Invite the child to describe the beginning, middle and end using their own words or drawings. Do not require memorized wording."),
          ("Minutes 11–14: creative extension", "Choose one: draw an alternate scene, invent a kind response, or act out a safe moment with household objects."),
          ("Minute 15: reflection", "Ask what was most interesting. Keep the session positive; adjust complexity and duration to the child's age, language and preferences."),
          ("Accessibility and care", "Offer larger text, a quiet environment and alternative communication modes when useful. This is a family activity, not a developmental assessment."),
         ],
         "https://mojplaywin.com/mpw-free-tools/20261025/taniya-storytime/",
         "Try the free storytime studio",
         "https://mojplaywin.com/store/product/225/",
         "Explore the illustrated Taniya book"),
        ("website-client-brief", "Client-Ready Website: Requirements Before Design",
         "A structured project brief reduces avoidable redesigns and ambiguous acceptance criteria.",
         [
          ("Audience and outcome", "Identify the primary visitor, the one action the site should encourage, the languages required and the conversion event to measure."),
          ("Content ownership", "List the approved logo, photography rights, brand colors, legal text, contact information and who can authorize publication."),
          ("Information architecture", "Define the minimum pages, navigation labels, calls to action and a clear path from the landing page to a completed enquiry."),
          ("Accessibility and mobile", "Specify keyboard access, visible focus, meaningful image alternatives, readable text contrast and small-screen acceptance."),
          ("Performance and privacy", "Record page-weight budgets, analytics consent requirements, cookie usage, data retention and the form's destination."),
          ("SEO and measurement", "Define unique titles, descriptions, canonical URLs, structured data only when accurate, a sitemap and measurable enquiry events."),
          ("Acceptance and handover", "Require screenshots at mobile and desktop widths, working forms, owner-controlled credentials, a backup procedure and a written launch sign-off."),
         ],
         "https://mojplaywin.com/mpw-free-tools/20261025/atelier-seo/",
         "Use the free SEO metadata generator",
         "https://mojplaywin.com/store/product/879/",
         "Explore the Atelier Interior website kit"),
        ("research-methods", "Reproducible Research: Evidence-First Project Intake",
         "Turn a research idea into a falsifiable, auditable project specification.",
         [
          ("Research question", "Write a precise question with a defined population or system, intervention or exposure, comparator where relevant, and measurable outcome."),
          ("Prior evidence", "Separate peer-reviewed findings, preprints, industry claims and unpublished observations. Record the retrieval date and source identifiers."),
          ("Design and bias", "State inclusion criteria, sample-size assumptions, confounders, randomization or control strategy and foreseeable limitations."),
          ("Data governance", "Define lawful data access, informed consent where applicable, privacy protections, retention and access controls."),
          ("Analysis plan", "Predefine primary outcomes, exclusion rules, statistical methods, uncertainty estimates and handling of missing data."),
          ("Reproducibility", "Version protocols, datasets and code; record software versions, instrument calibration and independent review gates."),
          ("Responsible communication", "Distinguish hypotheses from results and submitted manuscripts from accepted publications. Do not imply independent validation without evidence."),
         ],
         "https://mojplaywin.com/mpw-free-tools/20261025/research-evidence/",
         "Open the free evidence appraisal worksheet",
         "https://mojplaywin.com/mojtaba.roozegar/resume/",
         "View the professional research profile"),
    ],
    "zm": [
        ("trade-rfq", "چک‌لیست استعلام قیمت بین‌المللی (RFQ)",
         "برای دریافت پیشنهاد قابل‌مقایسه از تأمین‌کنندگان، درخواست را با مشخصات دقیق و قابل‌راستی‌آزمایی ارسال کنید.",
         [
          ("مشخصات کالا", "نام دقیق، استاندارد فنی، مدل، ظرفیت، کاربرد، کشور مبدأ و محدودیت‌های مجاز بودن واردات را روشن کنید."),
          ("حجم و کیفیت", "مقدار سفارش، حداقل سفارش، روش نمونه‌گیری، گواهی‌های آزمون، ضمانت و روش پذیرش یا رد محموله را مشخص کنید."),
          ("قیمت و ارز", "ارز پیشنهادی، اعتبار زمانی قیمت، هزینه بسته‌بندی، هزینه قطعات یدکی و شرایط تعدیل قیمت را جداگانه درخواست کنید."),
          ("تحویل و حمل", "اینکوترمز ۲۰۲۰ همراه با مکان نام‌گذاری‌شده، زمان تولید، روش حمل، بیمه و مدارک حمل را صریح بنویسید."),
          ("پرداخت و تطبیق", "روش پرداخت قانونی، تطبیق هویت و ذی‌نفع نهایی، محدودیت‌های بانکی و تحریمی و مسئولیت ترخیص را پیش از قرارداد بررسی کنید."),
          ("مقایسه پیشنهادها", "برای هر پیشنهاد یک جدول مستقل از قیمت پایه، حمل، بیمه، عوارض احتمالی، ریسک تأخیر و خدمات پس از فروش بسازید؛ برآورد، نرخ رسمی گمرکی نیست."),
          ("پرسش نمونه به انگلیسی", "Please quote the specified product with technical datasheet, MOQ, production lead time, Incoterms 2020 and named place, payment terms, warranty, and country of origin."),
         ],
         "https://zomorodmelal.ir/agriculture/free-tools/20261025/import-landed-cost/",
         "محاسبه سناریوهای هزینه واردات",
         "https://zomorodmelal.ir/contact/",
         "تماس و همکاری با شرکت"),
        ("farm-risk", "مدیریت ریسک آب، انرژی و سودآوری مزرعه",
         "تصمیم اقتصادی مزرعه باید بر اساس داده‌های اندازه‌گیری‌شده و چند سناریوی واقعی باشد.",
         [
          ("ثبت خط مبنا", "سطح زیر کشت، حجم آب مصرفی، ساعت پمپاژ، انرژی مصرفی، عملکرد محصول و قیمت فروش واقعی را در یک دوره مشخص ثبت کنید."),
          ("هزینه متغیر", "بذر، کود، سم، آب، برق یا سوخت، دستمزد و حمل را به تفکیک هر هکتار و هر کیلوگرم محصول محاسبه کنید."),
          ("سناریوی خشکسالی", "با فرض افت عملکرد ۱۰، ۲۰ و ۳۰ درصدی، حاشیه مشارکت را دوباره حساب کنید؛ این درصدها صرفاً سناریوی فرضی‌اند."),
          ("سناریوی انرژی", "اثر افزایش هزینه پمپاژ و توقف برق بر عملکرد و زمان آبیاری را جداگانه بررسی کنید."),
          ("اولویت اصلاح", "اقدامات را بر اساس صرفه‌جویی قابل‌اندازه‌گیری، هزینه سرمایه‌گذاری، دوره بازگشت و خطر عملیاتی رتبه‌بندی کنید."),
          ("محدودیت", "هیچ عدد فرضی را جایگزین داده مزرعه نکنید. تصمیم‌های فنی آبیاری باید با نظر متخصص محلی و شرایط خاک و محصول سازگار باشند."),
         ],
         "https://zomorodmelal.ir/agriculture/free-tools/20261025/farm-break-even/",
         "محاسبه‌گر رایگان نقطه سربه‌سر مزرعه",
         "https://zomorodmelal.ir/contact/",
         "ارتباط با زمرد ملل"),
    ],
}
def sha(data): return hashlib.sha256(data).hexdigest()
def checked(path):
    if path.is_symlink(): raise RuntimeError("SYMLINK_REFUSED:"+str(path))
def render(site, slug, title, summary, sections, free_url, free_label, action_url, action_label):
    fa=site=="zm"
    lang="fa" if fa else "en"
    direction="rtl" if fa else "ltr"
    base=("https://mojplaywin.com/mpw-learning/20261025/" if site=="mpw" else "https://zomorodmelal.ir/resources/20261025/")
    canonical=base+slug+"/"
    section_html="\n".join("<section><h2>"+html.escape(h)+"</h2><p>"+html.escape(p)+"</p></section>" for h,p in sections)
    linksep="&" if "?" in action_url else "?"
    tracking=linksep+"utm_source=onsite_resource&amp;utm_medium=organic&amp;utm_campaign=evergreen_guides_20261025&amp;utm_content="+slug
    return ('<!doctype html><html lang="'+lang+'" dir="'+direction+'"><head><meta charset="utf-8">'
      '<meta name="viewport" content="width=device-width,initial-scale=1">'
      '<meta name="robots" content="index,follow,max-image-preview:large">'
      '<link rel="canonical" href="'+canonical+'"><title>'+html.escape(title)+'</title>'
      '<meta name="description" content="'+html.escape(summary,quote=True)+'">'
      '<meta property="og:type" content="article"><meta property="og:title" content="'+html.escape(title,quote=True)+'">'
      '<meta property="og:description" content="'+html.escape(summary,quote=True)+'">'
      '<meta property="og:url" content="'+canonical+'">'
      '<style>body{margin:0;background:#f2f6f9;color:#182f42;font:17px/1.85 system-ui,sans-serif}'
      'main{max-width:850px;margin:2.5rem auto;padding:clamp(1rem,4vw,3rem);background:white;border:1px solid #d5e0e8;border-radius:18px}'
      'h1{font-size:clamp(1.6rem,4vw,2.4rem);line-height:1.3}h2{font-size:1.2rem;margin-top:1.8rem}'
      'a{color:#075d89}a:focus-visible{outline:3px solid #ef9a1d}'
      '.cta{padding:1rem;background:#edf7fb;border-inline-start:4px solid #0877a8;border-radius:7px}'
      'nav a{margin-inline-end:1rem}</style></head><body><main><nav><a href="'+base+'">'
      +('همه راهنماها' if fa else 'All free guides')+'</a></nav><h1>'+html.escape(title)+'</h1>'
      '<p>'+html.escape(summary)+'</p>'+section_html+'<aside class="cta"><p><a href="'+free_url+'">'+html.escape(free_label)+'</a></p>'
      '<p><a href="'+action_url+tracking+'">'+html.escape(action_label)+'</a></p></aside>'
      '<p><small>'+('این مطلب آموزشی است و جایگزین بررسی تخصصی، حقوقی یا مالی نیست.' if fa else 'Educational resource only. Verify current product details and terms on the official destination.')+'</small></p>'
      '</main></body></html>')
def build(out):
    if out.exists(): raise RuntimeError("BUILD_PATH_EXISTS")
    out.mkdir(parents=True)
    manifest={"release":RELEASE,"files":{"mpw":{},"zm":{}}}
    for site, rows in DATA.items():
        base=("https://mojplaywin.com/mpw-learning/20261025/" if site=="mpw" else "https://zomorodmelal.ir/resources/20261025/")
        items=[]
        for row in rows:
            slug=row[0]
            body=render(site,*row)
            if any(x in body for x in ("dr.mojtaba.rozegar","7317306")):
                raise RuntimeError("PROHIBITED_DESTINATION")
            rel=slug+"/index.html"
            target=out/site/rel
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(body,encoding="utf8")
            manifest["files"][site][rel]=sha(target.read_bytes())
            items.append('<li><a href="./'+slug+'/">'+html.escape(row[1])+'</a> — '+html.escape(row[2])+'</li>')
        fa=site=="zm"
        title="راهنماهای تخصصی رایگان زمرد ملل" if fa else "Free practical learning guides | MojPlayWin"
        desc="راهنماهای رایگان برای کشاورزی و تجارت قانونی." if fa else "Original practical resources for learning, digital products and evidence-based research."
        index=('<!doctype html><html lang="'+('fa' if fa else 'en')+'" dir="'+('rtl' if fa else 'ltr')+'"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="index,follow">'
            '<link rel="canonical" href="'+base+'"><title>'+title+'</title><meta name="description" content="'+desc+'">'
            '<style>body{font:17px/1.8 system-ui,sans-serif;background:#f4f8fb;color:#183449;max-width:850px;margin:3rem auto;padding:1rem}'
            'main{background:white;border-radius:16px;padding:2rem}li{margin:1.2rem 0}a{color:#075d89}</style></head><body>'
            '<main><h1>'+title+'</h1><p>'+desc+'</p><ul>'+"\n".join(items)+'</ul></main></body></html>')
        dest=out/site/"index.html"
        dest.write_text(index,encoding="utf8")
        manifest["files"][site]["index.html"]=sha(dest.read_bytes())
    # MPW static directory routing is isolated from the Passenger app.
    ht=b"PassengerEnabled off\nDirectoryIndex index.html\nOptions -Indexes\n"
    htpath=out/"mpw"/".htaccess"
    htpath.write_bytes(ht)
    manifest["files"]["mpw"][".htaccess"]=sha(ht)
    (out/"release.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf8")
    assert len(manifest["files"]["mpw"])==6 and len(manifest["files"]["zm"])==3
    print("NINE_FILES_EIGHT_PUBLIC_PAGES_READY")
def stage_path(run_id):
    if not re.fullmatch(r"[0-9]{6,20}",run_id): raise RuntimeError("BAD_RUN_ID")
    return HOME/(STAGE_PREFIX+run_id)
def verify_tree(root, hashes):
    checked(root)
    if not root.is_dir(): raise RuntimeError("TREE_MISSING:"+str(root))
    actual={str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}
    if actual!=set(hashes): raise RuntimeError("FILE_SET_MISMATCH:"+str(root))
    for rel,expected in hashes.items():
        p=root/rel
        checked(p)
        if sha(p.read_bytes())!=expected: raise RuntimeError("HASH_MISMATCH:"+str(p))
def install(action,run_id):
    mpw=HOME/"mojplaywin.com"
    zm=HOME/"public_html"
    for p in (HOME,mpw,zm):
        checked(p)
        if not p.is_dir(): raise RuntimeError("SITE_ROOT_MISSING")
    wsgi=mpw/"passenger_wsgi.py"
    checked(wsgi)
    if not wsgi.is_file() or "APP='/home/zomorod2/Saeit-staging'" not in wsgi.read_text("utf8","replace"):
        raise RuntimeError("PASSENGER_IDENTITY_MISMATCH")
    stage=stage_path(run_id)
    checked(stage)
    mfile=stage/"release.json"
    if not mfile.is_file() or mfile.is_symlink(): raise RuntimeError("STAGE_MANIFEST_MISSING")
    m=json.loads(mfile.read_text("utf8"))
    if m.get("release")!=RELEASE or set(m.get("files",{}))!=set(ROOTS):
        raise RuntimeError("MANIFEST_MISMATCH")
    if action=="apply":
        for site,dest in ROOTS.items():
            verify_tree(stage/site,m["files"][site])
            checked(dest)
            if dest.exists(): raise RuntimeError("EXISTING_RELEASE_NO_OVERWRITE:"+str(dest))
            checked(dest.parent)
            checked(dest.parent.parent)
        installed=[]
        try:
            for site,dest in ROOTS.items():
                dest.parent.mkdir(parents=True,exist_ok=True)
                checked(dest.parent)
                os.rename(stage/site,dest)
                installed.append(site)
                verify_tree(dest,m["files"][site])
                print("ISOLATED_SITE_INSTALLED",dest)
        except BaseException:
            for site in reversed(installed):
                dest=ROOTS[site]
                verify_tree(dest,m["files"][site])
                shutil.rmtree(dest)
            raise
    elif action=="rollback":
        for site,dest in ROOTS.items():
            if dest.exists() or dest.is_symlink():
                verify_tree(dest,m["files"][site])
                shutil.rmtree(dest)
                print("OWNED_RELEASE_ROLLED_BACK",dest)
    else: raise RuntimeError("UNKNOWN_ACTION")
if __name__=="__main__":
    if len(sys.argv)!=3: raise SystemExit("usage: build OUT | apply|rollback RUN_ID")
    if sys.argv[1]=="build": build(Path(sys.argv[2]))
    elif sys.argv[1] in ("apply","rollback"): install(sys.argv[1],sys.argv[2])
    else: raise SystemExit("UNKNOWN_MODE")
