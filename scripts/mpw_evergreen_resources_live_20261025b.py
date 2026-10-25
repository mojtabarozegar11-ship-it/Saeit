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

RELEASE = "organic-resource-pages-20261025b-v1"
HOME = Path("/home/zomorod2")
STAGE_PREFIX = ".organic-resource-b-stage-"
ROOTS = {
    "mpw": HOME / "mojplaywin.com" / "mpw-learning" / "20261025b",
    "zm": HOME / "public_html" / "resources" / "20261025b",
}
DATA = {
  "mpw": [
    [
      "chess-error-review",
      "Chess Post-Game Error Review: A Repeatable Six-Step Method",
      "A practical evidence-led method for reviewing your own chess games without mistaking engine evaluations for learning.",
      [
        [
          "Preserve the original game",
          "Save the PGN, time control, opening, result and remaining clock time at each critical decision. Keep the unedited record before consulting an engine so that later annotations cannot rewrite what you originally saw."
        ],
        [
          "Identify decision points",
          "Mark at least three moments when you considered alternatives, felt uncertainty or spent unusual time. Record the candidate moves and the opponent's forcing replies as you remember them; explicitly mark any missing recollection."
        ],
        [
          "Classify the error",
          "Separate tactical oversight, calculation truncation, strategic plan mismatch, endgame technique and clock management. A bad outcome is not automatically a bad decision: compare the information available at the time, not only the eventual result."
        ],
        [
          "Test one hypothesis",
          "Write a falsifiable statement such as 'I missed checks after move 18 because I did not scan forcing replies.' Use independent analysis and, only afterward, an engine to test whether that explanation fits the position."
        ],
        [
          "Assign one corrective drill",
          "For each recurring category choose a specific exercise with a time limit and success measure. Example: analyze five forcing-move positions in 12 minutes, write full variations, and score the number of correct candidate lists."
        ],
        [
          "Review after seven days",
          "Repeat the same measurement with games at a comparable time control. Compare error counts per game and the proportion of decisions with recorded candidates; small samples are noisy and do not establish long-term improvement."
        ]
      ],
      "https://mojplaywin.com/mpw-free-tools/20261025/chess-calendar/",
      "Build a free 84-day practice calendar",
      "https://mojplaywin.com/store/product/72/",
      "Explore the optional chess training book"
    ],
    [
      "taniya-creative-retelling",
      "Six Creative Retelling Games for Shared Picture-Book Reading",
      "Age-flexible family reading activities that build conversation and imagination without grading children or claiming developmental outcomes.",
      [
        [
          "Picture detective",
          "Before reading a page, invite the child to notice three details in the illustration. Ask which detail might matter later; accept different answers and revisit the guesses after the story."
        ],
        [
          "Character choices",
          "Ask what a character wanted, what choices were available and what a kind alternative might be. Use 'What makes you think that?' rather than labeling an answer wrong."
        ],
        [
          "Three-scene retell",
          "After reading, draw or describe the beginning, a turning point and the ending. For children who prefer movement, use three objects or gestures instead of writing."
        ],
        [
          "Change one ingredient",
          "Invent a new safe object, setting or character and imagine how one scene would change. Distinguish the original story from the invented version to support playful comprehension."
        ],
        [
          "Sound and rhythm",
          "Choose repeated words or sounds and invite clapping or soft tapping. Let the child choose whether to join; rhythm should remain an optional activity, not a performance test."
        ],
        [
          "Close with a choice",
          "Offer the child a choice to reread, draw, discuss or stop. Keep sessions brief and positive, adapt to language and accessibility needs, and avoid using these activities as a diagnostic assessment."
        ]
      ],
      "https://mojplaywin.com/mpw-free-tools/20261025/taniya-storytime/",
      "Open the free storytime activity studio",
      "https://mojplaywin.com/store/product/225/",
      "View the optional Taniya picture book"
    ],
    [
      "atelier-accessibility-acceptance",
      "Accessibility Acceptance Tests for a Small Business Website",
      "A client-facing acceptance method for keyboard access, readable content and practical website handover.",
      [
        [
          "Define a realistic user journey",
          "Write three representative tasks: find services, contact the business and view the portfolio. State the expected start page, destination and success condition before testing."
        ],
        [
          "Keyboard-only path",
          "Using Tab, Shift+Tab, Enter, Space and Escape, complete every task without a mouse. Record missing focus indicators, inaccessible menus, traps and elements that require hover."
        ],
        [
          "Text and contrast",
          "Measure actual foreground and background colors for normal and large text. WCAG AA contrast thresholds are generally 4.5:1 and 3:1 respectively, subject to applicable exceptions; do not rely on visual judgment alone."
        ],
        [
          "Responsive zoom",
          "Test at 200% zoom and a narrow viewport. Check that navigation, forms and essential content remain usable without obscured controls or horizontal scrolling where reflow is required."
        ],
        [
          "Forms and feedback",
          "Verify that every field has an accessible name, required fields are clear, errors identify the affected input, and submission produces an understandable confirmation. Do not collect real personal data during acceptance tests."
        ],
        [
          "Evidence and sign-off",
          "Save viewport size, browser version, test date, screenshots, defects and retest outcome. Mark untested criteria as untested; a checklist does not by itself certify WCAG conformance."
        ]
      ],
      "https://mojplaywin.com/mpw-free-tools/20261025/atelier-contrast/",
      "Use the free WCAG contrast calculator",
      "https://mojplaywin.com/store/product/879/",
      "Review the optional editable website kit"
    ],
    [
      "browser-game-retention-diagnostics",
      "How to Diagnose Day-1 and Day-7 Game Retention Without Misleading Metrics",
      "A practical measurement framework for game teams to separate onboarding friction from content fatigue and technical failures.",
      [
        [
          "Define a cohort consistently",
          "Choose installation date or first meaningful play as cohort entry and keep that definition stable. Exclude bots and internal testers using documented rules, never ad-hoc exclusions designed to improve the metric."
        ],
        [
          "Use explicit retention formulas",
          "D1 retention equals unique eligible cohort players returning on day 1 divided by eligible cohort size. D7 uses the same denominator and a return on day 7; calendar-day and rolling-24-hour definitions produce different results."
        ],
        [
          "Segment by first-session outcome",
          "Compare cohorts that finished the tutorial, abandoned before first success, encountered a crash or exited after a difficult level. Differences are diagnostic signals, not proof of causality."
        ],
        [
          "Separate reliability from design",
          "Record crash-free sessions, load time, input latency and device class alongside retention. A poor network experience can look like a weak game loop if technical signals are ignored."
        ],
        [
          "Use privacy-respecting events",
          "Collect only necessary events such as tutorial_started, tutorial_completed, level_failed and session_end. Avoid recording chat content or sensitive identifiers; document consent and regional privacy requirements."
        ],
        [
          "Choose one measurable experiment",
          "Change one onboarding variable at a time, define the primary metric and guardrails in advance, and observe enough eligible players before interpreting results. Do not promise a retention lift from a small or biased sample."
        ]
      ],
      "https://mojplaywin.com/mpw-free-tools/20261025/browser-game-qa/",
      "Open the free game quality evidence worksheet",
      "https://mojplaywin.com/store/",
      "Browse MojPlayWin digital products"
    ],
    [
      "digital-product-license-check",
      "Digital Product License Checklist Before You Buy",
      "Understand what a downloadable template or digital file permits, what is delivered and what remains your responsibility.",
      [
        [
          "Identify the delivered artifact",
          "Confirm whether the purchase includes PDF, ZIP, source code, assets, updates or support. Compare the item description with the checkout receipt rather than assuming all preview images are licensed."
        ],
        [
          "Check permitted usage",
          "Read whether the license covers one website, multiple clients, redistribution, commercial modification and derivative work. Non-exclusive access does not imply ownership of copyright."
        ],
        [
          "Audit third-party assets",
          "List photographs, fonts, icons, libraries and external services separately. A preview asset may require its own license even when the website template code is included."
        ],
        [
          "Record technical requirements",
          "Verify supported browsers, hosting requirements, dependencies and whether an account or wallet is required. Budget for hosting and transaction network fees separately from the listed product price."
        ],
        [
          "Check delivery and recovery",
          "Understand the order-specific invoice, payment confirmation, private download access and customer support process. Never send wallet seed phrases, private keys or sensitive account credentials to a seller."
        ],
        [
          "Keep an evidence folder",
          "Store the product page, version, license text, invoice, payment transaction ID and downloaded file hash when available. Report discrepancies promptly and do not treat an untested checkout as a guaranteed delivery."
        ]
      ],
      "https://mojplaywin.com/mpw-free-tools/20261025/atelier-seo/",
      "Try a free SEO metadata tool",
      "https://mojplaywin.com/store/product/879/",
      "Read the Atelier kit license and listing"
    ],
    [
      "research-data-audit-trail",
      "Research Data Audit Trail: From Field Observation to Reproducible Result",
      "An evidence-first field research protocol for the independent scientific profile of Mojtaba Roozegar.",
      [
        [
          "Register a precise question",
          "Define the study unit, intervention, comparator, primary outcome, time window and relevant uncertainty before collecting data. Distinguish exploratory observations from preregistered confirmatory hypotheses."
        ],
        [
          "Version instruments and forms",
          "Record sensor models, calibration dates, sampling frames, measurement units and any changes to field forms. Keep a change log explaining why each revision was necessary."
        ],
        [
          "Separate raw and processed data",
          "Preserve immutable raw observations with timestamps and source identifiers. Create reproducible transformations with scripts or documented steps rather than manually overwriting original values."
        ],
        [
          "Document missingness",
          "Use explicit codes for not measured, sensor failure, inapplicable and withheld. Do not silently convert missing values to zero or remove inconvenient observations."
        ],
        [
          "Review quality independently",
          "Check ranges, units, duplicates, anomalous readings and potential confounding. Require a second review for changes that alter the primary outcome; record unresolved limitations."
        ],
        [
          "Publish claims proportionately",
          "Share methods, anonymized aggregates and analysis code where lawful. Separate hypotheses, internal reports, submitted manuscripts and peer-reviewed publications; do not claim validation or publication without independent evidence."
        ]
      ],
      "https://mojplaywin.com/mpw-free-tools/20261025/research-evidence/",
      "Use the free scientific evidence appraisal worksheet",
      "https://mojplaywin.com/mojtaba.roozegar/resume/",
      "View the independent research profile"
    ]
  ],
  "zm": [
    [
      "cold-chain-acceptance",
      "چک‌لیست عملیاتی پذیرش محموله در زنجیره سرد محصولات کشاورزی",
      "راهنمای ثبت شواهد دما، کیفیت، ردیابی و تصمیم پذیرش یا قرنطینه محموله فسادپذیر.",
      [
        [
          "تعریف دامنه و حدود",
          "نوع محصول، رقم، درجه رسیدگی، بسته‌بندی، دمای هدف و حدود مجاز را بر اساس استاندارد اختصاصی محصول و قرارداد تعیین کنید؛ یک عدد دما برای همه محصولات معتبر نیست."
        ],
        [
          "ثبت داده پیش از تخلیه",
          "شماره بچ، مبدا، زمان بارگیری، شماره وسیله حمل، مدت مسیر، وضعیت پلمب و شناسه دیتالاگر را ثبت کنید. اطلاعات شفاهی را جایگزین سند قابل پیگیری نکنید."
        ],
        [
          "نمونه‌گیری نماینده",
          "از نقاط مختلف بار طبق طرح نمونه‌گیری از پیش تعریف‌شده نمونه بردارید. دمای مغز محصول، آسیب فیزیکی، رطوبت و نشانه‌های فساد را با ابزار کالیبره ثبت کنید."
        ],
        [
          "کنترل گسست دما",
          "گزارش دیتالاگر را با آستانه قراردادی و مدت خروج از محدوده مقایسه کنید. یک قرائت لحظه‌ای مناسب، گسست چندساعته دما را منتفی نمی‌کند."
        ],
        [
          "تصمیم آزادسازی",
          "قبول، قبول مشروط، قرنطینه یا رد را با معیار روشن و امضای مسئول مجاز ثبت کنید. در موارد ایمنی غذا، نظر کارشناس و الزامات قانونی بر محاسبه اقتصادی مقدم است."
        ],
        [
          "تحلیل ریشه‌ای و پیشگیری",
          "برای هر مغایرت، زمان، عامل احتمالی، اقدام اصلاحی، مسئول، مهلت و آزمون اثربخشی تعیین کنید. نرخ ضایعات را بر حسب وزن ورودی و وزن قابل فروش گزارش کنید."
        ]
      ],
      "https://zomorodmelal.ir/agriculture/free-tools/20261025/farm-break-even/",
      "محاسبه‌گر رایگان اقتصاد مزرعه",
      "https://zomorodmelal.ir/contact/",
      "درخواست همکاری تخصصی با زمرد ملل"
    ],
    [
      "supplier-technical-comparison",
      "روش امتیازدهی فنی و اقتصادی پیشنهادهای تأمین‌کنندگان تجهیزات کشاورزی",
      "چارچوب مقایسه شفاف استعلام‌ها، خدمات پس از فروش، هزینه مالکیت و ریسک معامله.",
      [
        [
          "تعیین نیاز قابل سنجش",
          "پیش از درخواست قیمت، ظرفیت واقعی، ساعات کار، مصرف انرژی، کیفیت خروجی، شرایط محیطی، استانداردهای ایمنی و محدودیت زیرساخت را با واحدهای یکسان بنویسید."
        ],
        [
          "جداسازی شروط الزامی",
          "الزامات قانونی، ایمنی، اصالت شرکت و حداقل مشخصات فنی را شروط رد یا قبول قرار دهید؛ امتیاز قیمت پایین نباید نقص الزامی را جبران کند."
        ],
        [
          "محاسبه هزینه مالکیت",
          "قیمت خرید، حمل، بیمه، عوارض احتمالی، نصب، آموزش، مصرف انرژی، قطعات، توقف تولید و تعمیرات را برای دوره یکسان مقایسه کنید. نرخ ارز و مالیات را به‌صورت فرض‌های تاریخ‌دار ثبت کنید."
        ],
        [
          "اعتبارسنجی شواهد",
          "کاتالوگ، شماره مدل، آزمون کارخانه، گواهی اصالت، نمونه کار واقعی، خدمات محلی و هویت ذی‌نفع نهایی را جداگانه بررسی کنید؛ ادعای فروشنده به‌تنهایی شاهد مستقل نیست."
        ],
        [
          "وزن‌دهی از پیش تعیین‌شده",
          "مثلاً ۴۰ درصد کارایی فنی، ۲۵ درصد هزینه مالکیت، ۲۰ درصد خدمات و ۱۵ درصد زمان تحویل را پیش از بازکردن پیشنهادها تصویب کنید. این اعداد صرفاً نمونه‌اند و باید با نیاز پروژه تطبیق یابند."
        ],
        [
          "کنترل معامله قانونی",
          "اینکوترمز با محل دقیق، تحریم‌ها، مقررات صادرات و واردات، روش پرداخت مجاز، اسناد گمرکی و حق بازرسی پیش از حمل را با متخصص حقوقی و تجاری بررسی کنید. هیچ تامین‌کننده‌ای صرفاً با این چک‌لیست تأیید نمی‌شود."
        ]
      ],
      "https://zomorodmelal.ir/agriculture/free-tools/20261025/import-landed-cost/",
      "محاسبه‌گر رایگان بهای تمام‌شده واردات",
      "https://zomorodmelal.ir/contact/",
      "تماس برای همکاری و ارزیابی تأمین‌کننده"
    ]
  ]
}

def sha(data): return hashlib.sha256(data).hexdigest()
def checked(path):
    if path.is_symlink(): raise RuntimeError("SYMLINK_REFUSED:"+str(path))
def render(site, slug, title, summary, sections, free_url, free_label, action_url, action_label):
    fa=site=="zm"
    lang="fa" if fa else "en"
    direction="rtl" if fa else "ltr"
    base=("https://mojplaywin.com/mpw-learning/20261025b/" if site=="mpw" else "https://zomorodmelal.ir/resources/20261025b/")
    canonical=base+slug+"/"
    section_html="\n".join("<section><h2>"+html.escape(h)+"</h2><p>"+html.escape(p)+"</p></section>" for h,p in sections)
    linksep="&" if "?" in action_url else "?"
    tracking=linksep+"utm_source=onsite_resource&amp;utm_medium=organic&amp;utm_campaign=evergreen_guides_20261025b&amp;utm_content="+slug
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
        base=("https://mojplaywin.com/mpw-learning/20261025b/" if site=="mpw" else "https://zomorodmelal.ir/resources/20261025b/")
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
    assert len(manifest["files"]["mpw"])==8 and len(manifest["files"]["zm"])==3
    print("ELEVEN_FILES_TEN_PUBLIC_PAGES_READY")
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
