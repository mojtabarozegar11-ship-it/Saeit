#!/usr/bin/env python3
"""Register 300 real, Iran-specific business and jobs training production orders.

P0 factory instructions only: no written books, approved certificates or stock.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

SCHEMA = "saeit.factory.production-instructions.v1"
ORIGIN = "owner_requested_jobs300_iran_p0"
INDEX_SCHEMA = "saeit.factory.owner-jobs300-iran-p0-index.v1"
ORDER_RE = re.compile(r"WO-[0-9]{8}\.json\Z")
PRODUCT_RE = re.compile(r"JOB-IR-[0-9]{3}\Z")
HEX = re.compile(r"[a-f0-9]{64}\Z")
MIN_WORDS = 100_000
CHAPTER_COUNT = 20

# Fifteen non-overlapping practical employment and microenterprise families:
# 20 distinct trades in each. No official licensing/market demand is asserted.
SECTORS = [
  [
    "کشاورزی و باغبانی",
    [
      "پرورش سبزی و صیفی گلخانه‌ای",
      "تولید ریزسبزی خوراکی",
      "تولید نشا و نهال",
      "پرورش گیاهان آپارتمانی",
      "خدمات طراحی باغچه شهری",
      "احداث و مدیریت باغ پسته",
      "کشت و فروش زعفران",
      "پرورش و برداشت زیتون",
      "بسته‌بندی خرمای صادراتی",
      "کشت گیاهان دارویی مجاز",
      "پرورش قارچ خوراکی",
      "راه‌اندازی گلخانه هیدروپونیک",
      "نصب سامانه آبیاری قطره‌ای",
      "تأمین نهاده کشاورزی",
      "نمونه‌برداری خاک برای آزمایشگاه مجاز",
      "تولید کمپوست گیاهی",
      "خشک‌کردن سبزی‌های معطر",
      "خدمات هرس درختان میوه",
      "تولید سبزی سالم با ردیابی مزرعه",
      "مشاوره ثبت سوابق مزرعه"
    ]
  ],
  [
    "دامپروری و آبزی‌پروری",
    [
      "زنبورداری و فروش عسل",
      "پرورش مرغ بومی",
      "پرورش بوقلمون",
      "پرورش بلدرچین",
      "واحد مرغ تخم‌گذار",
      "واحد مرغ گوشتی",
      "گاوداری شیری کوچک",
      "پرورش گوساله پرواری",
      "پرورش گوسفند",
      "پرورش بز شیری",
      "پرورش شترمرغ",
      "پرورش ماهی قزل‌آلا",
      "پرورش ماهیان گرمابی",
      "تولید خوراک دام",
      "جمع‌آوری و بسته‌بندی تخم‌مرغ",
      "خدمات اصلاح و نگهداری سم دام با صلاحیت",
      "تولید علوفه هیدروپونیک",
      "تکثیر ماهیان زینتی",
      "مرکز جمع‌آوری شیر خام مجاز",
      "مدیریت زنجیره سرد محصولات دامی"
    ]
  ],
  [
    "صنایع غذایی و نوشیدنی",
    [
      "تولید نان فانتزی",
      "نانوایی سنتی",
      "تولید شیرینی خشک",
      "کارگاه کیک سفارشی",
      "تولید شکلات دست‌ساز",
      "تولید مربا و مارمالاد",
      "کارگاه ترشی و شور",
      "تولید رب گوجه‌فرنگی",
      "آسیاب و بسته‌بندی ادویه",
      "فرآوری و بسته‌بندی خشکبار",
      "تولید میوه خشک",
      "بسته‌بندی حبوبات",
      "رست و بسته‌بندی قهوه",
      "آشپزخانه غذای خانگی دارای مجوز",
      "ساندویچی محلی",
      "کترینگ مجالس",
      "فروش تخصصی آش و سوپ",
      "آبمیوه و اسموتی",
      "تولید بستنی سنتی",
      "تأمین غذای شرکت‌ها"
    ]
  ],
  [
    "خرده‌فروشی و تجارت",
    [
      "سوپرمارکت محلی",
      "لوازم‌التحریرفروشی",
      "ابزارفروشی",
      "فروشگاه یراق‌آلات",
      "فروشگاه گوشی موبایل",
      "فروش قطعات رایانه",
      "فروشگاه قطعات خودرو",
      "گل‌فروشی",
      "فروشگاه ملزومات حیوانات خانگی",
      "فروشگاه پوشاک کودک",
      "فروش پوشاک ورزشی",
      "فروش کیف و کفش",
      "لوازم خانگی سبک",
      "فروش تجهیزات گلخانه",
      "فروش صنایع دستی ایران",
      "فروش لوازم سفر",
      "فروش محصولات خوراکی محلی",
      "فروشگاه اینترنتی تخصصی",
      "تأمین کالا برای کسب‌وکارهای کوچک",
      "صادرات قانونی محصولات غذایی"
    ]
  ],
  [
    "ساختمان و تأسیسات",
    [
      "خدمات برق‌کشی ساختمان با صلاحیت",
      "لوله‌کشی آب ساختمان",
      "نصب و تعمیر پکیج گرمایشی مجاز",
      "سرویس کولر آبی",
      "نصب کولر گازی با صلاحیت",
      "کاشی‌کاری و سرامیک",
      "نقاشی ساختمان",
      "کناف و سقف کاذب",
      "کابینت‌سازی ام‌دی‌اف",
      "نجاری دکوراسیون داخلی",
      "نصب کف‌پوش",
      "عایق‌کاری رطوبتی",
      "خدمات در و پنجره دوجداره",
      "آهنگری درب و حفاظ",
      "تعمیر قفل و یراق درب",
      "آجرچینی و بنایی سبک",
      "نصب پرده و کرکره",
      "باغبانی و نگهداری فضای سبز مجتمع",
      "نظافت تخصصی پس از ساخت",
      "برآورد مصالح و متره مقدماتی"
    ]
  ],
  [
    "خودرو و حمل‌ونقل",
    [
      "تعمیرگاه خودروهای سواری مجاز",
      "تعویض روغن و فیلتر",
      "خدمات لاستیک و آپارات",
      "تنظیم فرمان و جلوبندی",
      "برق خودرو",
      "دیاگ و عیب‌یابی خودرو",
      "صافکاری بدنه",
      "نقاشی خودرو",
      "کارواش خودرو",
      "دیتیلینگ و پولیش خودرو",
      "فروش لوازم جانبی خودرو",
      "تعمیر موتورسیکلت",
      "سرویس دوچرخه",
      "تعمیر باتری خودرو",
      "خدمات کولر خودرو",
      "تعویض شیشه خودرو",
      "مدیریت ناوگان پیک شهری",
      "کرایه خودرو با مجوز",
      "حمل بار سبک شهری",
      "لجستیک قطعات خودرو"
    ]
  ],
  [
    "فناوری اطلاعات و دیجیتال",
    [
      "طراحی وب‌سایت شرکتی",
      "فروش خدمات سئو اصولی",
      "مدیریت محتوای شبکه‌های اجتماعی",
      "طراحی گرافیک تبلیغاتی",
      "تدوین ویدئوی کسب‌وکار",
      "تولید پادکست آموزشی",
      "برنامه‌نویسی وب",
      "توسعه اپلیکیشن موبایل",
      "آزمایش کیفیت نرم‌افزار",
      "راه‌اندازی فروشگاه اینترنتی",
      "پشتیبانی فنی رایانه",
      "تعمیر رایانه و لپ‌تاپ",
      "نصب شبکه محلی کسب‌وکار",
      "پشتیبان‌گیری امن اطلاعات",
      "آموزش سواد دیجیتال",
      "مدیریت تبلیغات آنلاین",
      "تحلیل داده فروش",
      "ساخت داشبورد مدیریتی",
      "طراحی رابط کاربری",
      "خدمات عکاسی محصول"
    ]
  ],
  [
    "اداری و خدمات حرفه‌ای",
    [
      "خدمات دفترداری کسب‌وکار کوچک",
      "تنظیم فاکتور و انبارداری",
      "مدیریت اسناد اداری",
      "خدمات تایپ و صفحه‌آرایی",
      "خدمات ترجمه عمومی",
      "طراحی رزومه حرفه‌ای",
      "آموزش مهارت مصاحبه شغلی",
      "امور دبیرخانه و بایگانی",
      "پیاده‌سازی مدیریت ارتباط مشتری",
      "طراحی فرآیند فروش",
      "مشاوره مدیریت عملیات عمومی",
      "تحلیل هزینه و بودجه بنگاه",
      "خدمات ثبت داده و ورود اطلاعات",
      "برگزاری رویداد تجاری",
      "هماهنگی جلسات و سفر کاری",
      "خدمات دستیار مجازی",
      "تهیه کاتالوگ تجاری",
      "خدمات چاپ دیجیتال",
      "مدیریت خرید و تدارکات",
      "خدمات تحقیقات بازار اولیه"
    ]
  ],
  [
    "آموزش و صنایع فرهنگی",
    [
      "آموزش خصوصی ریاضی",
      "آموزش خصوصی زبان انگلیسی",
      "آموزش خوش‌نویسی",
      "آموزش نقاشی کودک",
      "آموزش موسیقی با مجوز لازم",
      "تولید محتوای کمک‌درسی",
      "طراحی کتاب کار آموزشی",
      "کلاس رباتیک نوجوانان",
      "کلاس مهارت رایانه",
      "آموزش فن بیان",
      "کلاس عکاسی مبتدی",
      "آموزش نویسندگی کاربردی",
      "تدریس برنامه‌نویسی کودکان",
      "کارگاه صنایع دستی",
      "انتشار کتاب الکترونیکی",
      "طراحی بازی آموزشی رومیزی",
      "آموزش سواد مالی نوجوانان",
      "برگزاری کارگاه مهارت شغلی",
      "تولید ویدئوی آموزشی",
      "راه‌اندازی مرکز آموزشی با مجوز"
    ]
  ],
  [
    "پوشاک و زیبایی",
    [
      "خیاطی لباس زنانه",
      "خیاطی لباس مردانه",
      "دوخت پوشاک کودک",
      "تعمیر و تغییر سایز لباس",
      "طراحی الگوی پوشاک",
      "گلدوزی و تزیین لباس",
      "چاپ روی تی‌شرت",
      "تولید لباس کار",
      "تولید مانتو و پوشاک اداری",
      "فروش اینترنتی پوشاک تولیدی",
      "تولید کیف پارچه‌ای",
      "تعمیر کیف و کفش",
      "کفاشی سفارشی",
      "پیرایش مردانه مجاز",
      "آرایشگری زنانه مجاز",
      "خدمات ناخن با رعایت بهداشت",
      "تولید زیورآلات دست‌ساز",
      "ساخت اکسسوری مو",
      "تولید پارچه دست‌باف",
      "عکاسی پوشاک و مد"
    ]
  ],
  [
    "گردشگری و مهمان‌نوازی",
    [
      "اقامتگاه بوم‌گردی دارای مجوز",
      "مدیریت مهمان‌پذیر",
      "خدمات خانه‌داری هتل",
      "راهنمای گردشگری دارای مجوز",
      "طراحی تور شهری",
      "رزرو و هماهنگی سفر",
      "رستوران غذاهای محلی",
      "کافه کوچک محلی",
      "خدمات صبحانه سازمانی",
      "تشریفات مراسم",
      "برنامه‌ریزی سفر خانوادگی",
      "اجاره تجهیزات کمپینگ",
      "فروش سوغات محلی",
      "عکاسی گردشگری",
      "تولید راهنمای دیجیتال سفر",
      "راه‌اندازی غرفه خوراکی گردشگری",
      "خدمات پذیرایی نمایشگاهی",
      "مدیریت رویداد محلی",
      "بازاریابی اقامتگاه",
      "راهنمای بازدید موزه با مجوز"
    ]
  ],
  [
    "خدمات خانواده و رفاه",
    [
      "مراقبت غیرپزشکی از سالمند با مجوز",
      "نگهداری کودک با مجوز",
      "خدمات نظافت منزل",
      "خشکشویی و اتوشویی",
      "تعمیر لوازم خانگی",
      "خدمات تعمیر چرخ خیاطی",
      "آموزش آشپزی خانگی",
      "خدمات اسباب‌کشی منزل",
      "شست‌وشوی فرش و موکت",
      "خدمات باغچه منزل",
      "دستیار خرید خانوار",
      "خدمات بسته‌بندی هدیه",
      "نظم‌دهی و چیدمان منزل",
      "خدمات تعمیر مبلمان",
      "خدمات بازسازی و رویه‌کوبی مبل",
      "نگهداری مجاز حیوانات خانگی",
      "آموزش مهارت‌های خانه‌داری",
      "تعمیر اسباب‌بازی",
      "خدمات شست‌وشوی پنجره",
      "خدمات نصب تجهیزات کمکی منزل با صلاحیت"
    ]
  ],
  [
    "تولید کارگاهی و صنایع دستی",
    [
      "کارگاه نجاری مصنوعات چوبی",
      "تولید شمع تزیینی",
      "تولید صابون مجاز",
      "ساخت سفال و سرامیک هنری",
      "بافت فرش دستباف",
      "بافت گلیم",
      "حکاکی و چاپ لیزری مجاز",
      "ساخت مصنوعات فلزی سبک",
      "تولید بسته‌بندی مقوایی",
      "تولید کارتن سفارشی",
      "کارگاه چاپ سیلک",
      "ساخت مبلمان کوچک",
      "تولید لوازم چوبی آشپزخانه",
      "ساخت لوستر دست‌ساز",
      "تولید چرم‌دوزی",
      "ساخت ظروف بتنی تزیینی",
      "تولید عروسک پارچه‌ای",
      "کارگاه خراطی چوب",
      "تولید لوازم دکوری رزینی ایمن",
      "ساخت سازه‌های نمایشگاهی سبک"
    ]
  ],
  [
    "انرژی و محیط زیست",
    [
      "نصب پنل خورشیدی با صلاحیت",
      "پایش مصرف برق واحد تجاری",
      "بهینه‌سازی روشنایی ساختمان",
      "فروش تجهیزات صرفه‌جویی آب",
      "تعمیر تجهیزات آبیاری",
      "جمع‌آوری و تفکیک پسماند خشک",
      "بازیافت کاغذ و مقوا",
      "تعمیر و بازاستفاده مبلمان",
      "خدمات نگهداری فضای سبز کم‌آب",
      "تولید کیسه چندبارمصرف",
      "پایش مصرف آب واحد صنعتی",
      "خدمات عایق حرارتی ساختمان",
      "طراحی باغچه کم‌مصرف آب",
      "فروش تجهیزات خورشیدی خانگی",
      "نگهداری سامانه خورشیدی با صلاحیت",
      "بازاریابی محصولات قابل‌بازیافت",
      "خدمات تعمیر به‌جای تعویض وسایل",
      "تولید لوازم آموزشی محیط‌زیستی",
      "بازسازی دوچرخه دست دوم",
      "ممیزی مقدماتی پسماند کسب‌وکار"
    ]
  ],
  [
    "پست، انبار و خدمات شهری",
    [
      "خدمات بسته‌بندی مرسوله",
      "مدیریت انبار خرد",
      "تحویل سفارش فروشگاه آنلاین",
      "راه‌اندازی خدمات پیک محلی",
      "مرکز جمع‌آوری سفارش اینترنتی",
      "مدیریت موجودی فروشگاهی",
      "خدمات چیدمان قفسه فروشگاه",
      "بسته‌بندی صادراتی غیرخطرناک",
      "حمل تجهیزات نمایشگاهی",
      "مدیریت مرجوعی فروشگاه",
      "خدمات کنترل کیفیت بسته‌بندی",
      "خدمات برچسب‌زنی کالا",
      "آموزش اپراتوری لیفتراک با صلاحیت",
      "خدمات نظافت اداری",
      "خدمات نگهداری مجتمع تجاری",
      "برنامه‌ریزی مسیر توزیع شهری",
      "تأمین لوازم مصرفی ادارات",
      "خدمات پشتیبانی غرفه نمایشگاه",
      "اجاره تجهیزات انبارداری",
      "عملیات مرکز تماس فروشگاهی"
    ]
  ]
]


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def digest(value: dict) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def catalog() -> list[dict]:
    if len(SECTORS) != 15 or any(len(items) != 20 for _, items in SECTORS):
        raise ValueError("JOBS300_NOT_15_SECTORS_X_20_PROFESSIONS")
    unique = [name for _, items in SECTORS for name in items]
    if len(set(unique)) != 300:
        raise ValueError("JOBS300_DUPLICATE_JOB")
    rows = []
    for sector, professions in SECTORS:
        for trade in professions:
            n = len(rows) + 1
            rows.append({
                "id": "JOB-IR-%03d" % n,
                "sector": sector,
                "trade": trade,
                "title": "راهنمای فوق‌حرفه‌ای راه‌اندازی و مدیریت " + trade + " در ایران",
                "selling_locale": "fa-IR",
                "country": "Iran",
                "storefront": "zomorodmelal.ir",
                "store_section": "education",
            })
    assert len(rows) == 300
    assert all(PRODUCT_RE.fullmatch(row["id"]) for row in rows)
    return rows


def order_for(spec: dict, rank: int) -> dict:
    book = {
        "schema": SCHEMA, "origin": ORIGIN,
        "source_product_id": spec["id"], "source_sha256": digest(spec),
        "priority": "P0", "priority_rank": rank,
        "priority_group": "OWNER_IRAN_JOBS300",
        "priority_reason": "OWNER_DIRECTIVE_2026_10_24",
        "family_id": "F07", "related_business_family": "F01",
        "phase": "original_iran_business_profession_training_manual",
        "slot": 1, "subject": spec["title"],
        "profession_scope": spec,
        "instruction": (
            "Write a complete original, practical, Iran-specific and current "
            "professional training handbook on this ONE named trade. Include "
            "learner prerequisites, realistic setup workflow, customer discovery, "
            "legal permit research, workplace safety, ethics, stepwise daily "
            "operations, market testing, procurement, cost and cashflow models, "
            "pricing options, sales, customer support, quality checks, risk "
            "scenarios, accounting and detailed assessed case studies. Verify "
            "every asserted official regulation and local license with dated "
            "primary sources; do not assert guaranteed revenue, qualifications, "
            "licensing, exemptions or endorsements. Author at least 100000 "
            "genuinely distinct and useful Persian prose words across 20 mature "
            "chapters, annotated worked projects, answer keys and instructor "
            "guidance; do not pad, invent evidence or copy copyrighted training "
            "materials. Correctly distinguish certified regulated professions "
            "from unlicensed activities. Do not publish before external science/"
            "trade review, independent QC1000 and proven customer delivery."
        ),
        "editions": [{
            "locale": "fa-IR", "site": "zomorodmelal.ir",
            "education_page": "education", "title": spec["title"],
            "currency": "IRR", "audience": "Iran; occupation-specific",
        }],
        "minimum_original_prose_words": MIN_WORDS,
        "authoring_target_original_words": 105_000,
        "chapter_count_required": CHAPTER_COUNT,
        "actual_authored_chapters": 0,
        "tradespeople_field_review_verified": False,
        "regulatory_authorities_verified": False,
        "primary_sources_verified": False,
        "independent_qc1000_verified": False,
        "real_buyer_checkout_and_delivery_verified": False,
        "discount_authority": "OWNER_ONLY", "discount_percent": 0,
        "base_price_policy": "REAL_FAIR_IRR_UNDER_REVIEW",
        "acceptance": [
            "Verify market scope, buyers, competitors and realistic value with dated independent evidence",
            "Verify any required trade, food, safety or professional license through the applicable Iranian authority",
            "Author 100000 original non-repetitive Persian prose words with 20 independently useful chapters",
            "Include worked cost and cashflow scenarios labelled assumptions, not earnings promises",
            "Provide practical operations checklists, sourced safety procedures, templates, exercises and answer keys",
            "Verify originality, local Persian editing, copyright, accessible PDF rendering and provenance",
            "Obtain trade-specialist judgement and independent QC1000 without self-certifying",
            "Prove paid checkout, buyer identity, invoice, protected file download and email delivery before sales",
        ],
        "product_goal_count": 1, "status": "issued",
        "instruction_kind": "private_factory_work_order",
        "independent_of_websites": True,
        "requires_customer_order": False, "api_required": False,
        "technical_product_release": False, "manufacturing_qa_passed": False,
        "publication_approved": False, "public_distribution_allowed": False,
        "warehouse_goods_created": False, "commercial_release": False,
    }
    book["fingerprint"] = digest({
        k: v for k, v in book.items()
        if k not in ("schema", "status", "instruction_kind", "fingerprint")
    })
    return book


def private_dir(path: Path) -> None:
    if path.is_symlink():
        raise ValueError("JOBS300_SYMLINK_DIRECTORY")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir() or path.is_symlink():
        raise ValueError("JOBS300_UNSAFE_DIRECTORY")


def read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 200_000:
        raise ValueError("JOBS300_UNSAFE_EXISTING_JSON")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("JOBS300_JSON_OBJECT_REQUIRED")
    return doc


def save_new(path: Path, doc: dict) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError("JOBS300_WOULD_OVERWRITE_ORDER")
    private_dir(path.parent)
    fd, temporary = tempfile.mkstemp(prefix=".jobs300-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(json.dumps(doc, ensure_ascii=False, sort_keys=True,
                               indent=2).encode("utf-8") + b"\n")
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temporary, 0o600)
        if path.exists() or path.is_symlink():
            raise ValueError("JOBS300_DESTINATION_COLLISION")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def install(root_path: Path) -> dict:
    root = Path(root_path).resolve()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("JOBS300_FACTORY_ROOT_INVALID")
    rows = catalog()
    area = root / "production-instructions"
    directory = area / "orders"
    private_dir(area)
    private_dir(directory)
    mutex = area / ".orders.lock"
    if mutex.is_symlink():
        raise ValueError("JOBS300_LOCK_SYMLINK")
    with mutex.open("a+b") as lock:
        os.chmod(mutex, 0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        old = []
        for path in sorted(directory.iterdir()):
            if path.is_symlink() or not path.is_file() or not ORDER_RE.fullmatch(path.name):
                raise ValueError("JOBS300_UNEXPECTED_QUEUE_ENTRY")
            item = read_json(path)
            if (item.get("schema") != SCHEMA or item.get("id") != path.stem
                    or item.get("public_distribution_allowed") is not False
                    or item.get("status") not in
                        ("issued", "in_engineering", "blocked_rework", "completed_verified")
                    or not HEX.fullmatch(str(item.get("fingerprint", "")))):
                raise ValueError("JOBS300_UNSAFE_EXISTING_WORK_ORDER")
            old.append(item)
        if len(old) + 300 > 15_000:
            raise ValueError("JOBS300_STORAGE_CAPACITY")
        existing = {}
        for item in old:
            if item.get("origin") == ORIGIN:
                key = item.get("source_product_id")
                if key in existing:
                    raise ValueError("JOBS300_DUPLICATE_PRIOR_ID")
                existing[key] = item
        expected = {
            s["id"]: order_for(s, i) for i, s in enumerate(rows, 1)
        }
        for key, record in existing.items():
            if key not in expected or any(
                record.get(field) != value for field, value in expected[key].items()
                if field not in ("id", "created_utc", "status")
            ):
                raise ValueError("JOBS300_EXISTING_ORDER_FINGERPRINT_CONFLICT:" + str(key))
        serial = max((int(item["id"][3:]) for item in old), default=0)
        created = 0
        for spec in rows:
            ident = spec["id"]
            if ident in existing:
                continue
            serial += 1
            record = dict(expected[ident], id="WO-%08d" % serial)
            save_new(directory / (record["id"] + ".json"), record)
            existing[ident] = record
            created += 1
        ids = [existing[spec["id"]]["id"] for spec in rows]
        index = {
            "schema": INDEX_SCHEMA, "owner_priority": "P0",
            "status": "REGISTERED_AWAITING_REAL_ORIGINAL_AUTHORING",
            "book_goal_count": 300, "sector_count": 15,
            "minimum_total_original_prose_words": 30_000_000,
            "storefront": "zomorodmelal.ir", "section": "education",
            "locale": "fa-IR", "currency": "IRR",
            "origin": ORIGIN, "catalog_sha256": digest({"specs": rows}),
            "order_ids_ranked": ids,
            "published_books": 0, "fully_authored_books": 0,
            "independently_approved_books": 0,
            "discounts_approved": 0, "websites_modified": False,
        }
        index_path = area / "owner-jobs300-ir-p0-index.json"
        if index_path.exists():
            if read_json(index_path) != index:
                raise ValueError("JOBS300_EXISTING_INDEX_CONFLICT")
        else:
            save_new(index_path, index)
    return {
        "registered": len(ids), "new_orders": created, "sectors": 15,
        "target_words": 30_000_000, "completed_books": 0, "published": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-private")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        rows = catalog()
        assert len(rows) == len({x["title"] for x in rows}) == 300
        assert all(order_for(x, i)["publication_approved"] is False
                   for i, x in enumerate(rows, 1))
        print("JOBS300_P0_SELFTEST=PASS")
        return
    if not args.factory_private:
        parser.error("--factory-private required except for --selftest")
    print(json.dumps(install(Path(args.factory_private)), ensure_ascii=False))


if __name__ == "__main__":
    main()
