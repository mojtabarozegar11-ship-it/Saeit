#!/usr/bin/env python3
"""Register 200 women-focused home-based business training orders for Iran.

Private P0 work orders only; no completed books, licensed businesses, stock or sales.
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
ORIGIN = "owner_requested_women_home200_iran_p0"
INDEX_SCHEMA = "saeit.factory.owner-women-home200-ir-p0-index.v1"
ORDER_RE = re.compile(r"WO-[0-9]{8}\.json\Z")
PRODUCT_RE = re.compile(r"HOME-IR-[0-9]{3}\Z")
HEX = re.compile(r"[a-f0-9]{64}\Z")
MIN_WORDS = 100_000
CHAPTER_COUNT = 20

# Ten practical and distinct home-based entrepreneurship sectors:
# 20 distinct trades in each. No official licensing/market demand is asserted.
SECTORS = [
  [
    "دوخت و طراحی محصولات پارچه‌ای",
    [
      "دوخت سیسمونی پارچه‌ای نوزاد",
      "دوخت مانتو سایزبزرگ سفارشی",
      "دوخت لباس عروسک پارچه‌ای",
      "دوخت چادر نماز و سجاده پارچه‌ای",
      "دوخت پیش‌بند آشپزخانه سفارشی",
      "دوخت روتختی و ست خواب",
      "دوخت روبالشی تزیینی",
      "دوخت کاور مبل پارچه‌ای",
      "دوخت کاور لوازم خانگی",
      "دوخت کیف خرید پارچه‌ای",
      "دوخت کیف لوازم آرایشی پارچه‌ای",
      "دوخت دستمال سفره پارچه‌ای",
      "گلدوزی نام و نشان روی حوله",
      "وصله‌دوزی هنری لباس",
      "دوخت رومیزی مناسبتی",
      "دوخت لباس حیوانات خانگی",
      "دوخت عروسک نمدی ایمن",
      "دوخت پاپوش نمدی خانگی",
      "دوخت پوشش پارچه‌ای غیرپزشکی",
      "تولید بسته‌بندی هدیه پارچه‌ای"
    ]
  ],
  [
    "بافتنی و هنرهای الیاف",
    [
      "بافت کیف قلاب‌بافی",
      "بافت عروسک آمیگورومی",
      "بافت شال دست‌ساز",
      "بافت کلاه زمستانی",
      "بافت دستکش زمستانی",
      "بافت پتوی نوزاد",
      "بافت زیرلیوانی قلابی",
      "ساخت آویز گلدان مکرومه",
      "ساخت دیوارکوب مکرومه",
      "بافت فرشینه کوچک",
      "بافت سبد تریکو",
      "بافت کیف تریکو",
      "بافت رومیزی قلاب‌بافی",
      "ساخت زیورآلات بافتنی",
      "بافت تابلو نخ و میخ",
      "بافت اسکاچ دست‌ساز",
      "بافت پادری خانگی",
      "بافت روکش صندلی",
      "بافت بند عینک تزیینی",
      "ساخت اکسسوری مو با نخ"
    ]
  ],
  [
    "خوراکی‌های خانگی با مجوز و بهداشت",
    [
      "تهیه لواشک میوه‌ای استاندارد",
      "تهیه گرانولای صبحانه",
      "تهیه کره بادام‌زمینی بسته‌بندی",
      "تهیه خرمای شکلاتی",
      "تهیه کراکر سبوس‌دار",
      "تهیه کوکی بدون گلوتن با کنترل آلرژن",
      "تهیه دمنوش ترکیبی با مجوز",
      "تهیه سمنوی سفارشی",
      "تهیه حلواهای مناسبتی",
      "تهیه شیرینی مخصوص دیابتی بدون ادعای درمانی",
      "تهیه بسته‌های صبحانه شرکتی",
      "تهیه نان خشک طعم‌دار",
      "تهیه میوه‌های روکش شکلاتی",
      "تهیه شیرینی سنتی منطقه‌ای",
      "تهیه پاستیل خانگی مجاز",
      "تهیه شربت گیاهی خوراکی بدون ادعای درمان",
      "تهیه سس خانگی ماندگار با آزمون ایمنی",
      "تهیه چاشنی سالاد خشک",
      "تهیه اسنک‌های غلات حجیم‌شده",
      "تهیه بسته‌های پذیرایی مراسم کوچک"
    ]
  ],
  [
    "هنرهای تزیینی و هدیه‌سازی",
    [
      "ساخت کارت پستال دست‌ساز",
      "ساخت جعبه هدیه سفارشی",
      "ساخت گل کاغذی تزیینی",
      "ساخت گل فومی تزیینی",
      "ساخت استیکرهای سفارشی",
      "ساخت دفترچه یادبود",
      "ساخت آلبوم اسکرپ‌بوک",
      "ساخت قاب عکس کاغذی",
      "ساخت نشانگر کتاب هنری",
      "ساخت آویز چوبی سبک",
      "نقاشی روی سنگ تزیینی",
      "نقاشی روی شیشه با مواد ایمن",
      "ساخت تابلو کالیگرافی",
      "طراحی کارت دعوت مناسبتی",
      "ساخت تاج جشن کودک ایمن",
      "ساخت اکسسوری جشن تولد",
      "تولید بسته‌های ساخت کاردستی کودک",
      "ساخت جعبه جواهر پارچه‌ای",
      "تولید هدیه سازمانی کم‌تیراژ",
      "ساخت آویز دیواری کاغذی"
    ]
  ],
  [
    "گیاه و باغبانی در محیط خانه",
    [
      "ساخت تراریوم گیاهان آپارتمانی",
      "ساخت باغ شیشه‌ای خزه",
      "پرورش ساکولنت‌های مینیاتوری",
      "تکثیر قلمه بونسای",
      "تولید گلدان‌های گیاه معطر کوچک",
      "فروش بسته کاشت بذر خانگی",
      "طراحی کیت آموزشی جوانه‌زنی بذر غیرخوراکی",
      "ساخت استندهای کوچک گلدان",
      "طراحی دیوار سبز خانگی کوچک",
      "تولید برچسب نگهداری گیاه",
      "ساخت بسته هدیه گیاه زنده",
      "پرورش گیاهان هوازی تیلاندسیا",
      "تولید خاک ترکیبی گلدانی",
      "ساخت کیت آبیاری خودکار کوچک",
      "پرورش گل‌های فصلی در تراس",
      "تکثیر کاکتوس زینتی مجاز",
      "آموزش آنلاین نگهداری گیاه خانگی",
      "طراحی تقویم آبیاری شخصی",
      "ساخت دفترچه ثبت رشد گیاه",
      "تولید جعبه ابزار نگهداری گیاه"
    ]
  ],
  [
    "تولید محتوای دیجیتال در خانه",
    [
      "ساخت قالب رزومه فارسی قابل‌ویرایش",
      "طراحی قالب ارائه آموزشی",
      "تولید زیرنویس ویدئو فارسی",
      "ویرایش صوت مصاحبه",
      "طراحی اینفوگرافیک کسب‌وکار",
      "صفحه‌آرایی کتاب الکترونیکی کودک",
      "طراحی خبرنامه ایمیلی",
      "ساخت الگوی پست شبکه اجتماعی",
      "طراحی جلد پادکست",
      "تولید موشن‌گرافیک کوتاه آموزشی",
      "ویرایش و رتوش عکس محصول",
      "طراحی آیکون و پیکتوگرام",
      "تولید فایل تمرین اکسل",
      "ساخت الگوی بودجه خانوار",
      "ساخت تقویم محتوایی اصناف",
      "تولید فلش‌کارت دیجیتال",
      "ساخت آزمون تعاملی آنلاین",
      "ساخت برگه برنامه‌ریزی روزانه",
      "تهیه متن معرفی محصول با راستی‌آزمایی",
      "طراحی قالب فاکتور کسب‌وکار کوچک"
    ]
  ],
  [
    "آموزش آنلاین مهارت‌های خانگی",
    [
      "آموزش آنلاین دوخت دکمه و ترمیم لباس",
      "آموزش آنلاین گلدوزی مقدماتی",
      "آموزش آنلاین بافت عروسک",
      "آموزش آنلاین کار با اکسل خانگی",
      "آموزش آنلاین تایپ ده‌انگشتی",
      "آموزش آنلاین برنامه‌ریزی هفتگی",
      "آموزش آنلاین عکاسی با موبایل",
      "آموزش آنلاین صفحه‌آرایی فارسی",
      "آموزش آنلاین نقاشی آبرنگ",
      "آموزش آنلاین ساخت جعبه هدیه",
      "آموزش آنلاین مدیریت فایل‌های شخصی",
      "آموزش آنلاین امنیت حساب‌های اینترنتی",
      "آموزش آنلاین نوشتن متن تبلیغاتی",
      "آموزش آنلاین بودجه‌بندی خانواده",
      "آموزش آنلاین کاشت گیاهان آپارتمانی",
      "آموزش آنلاین تدوین ویدئو موبایلی",
      "آموزش آنلاین طراحی پوستر مناسبتی",
      "آموزش آنلاین کاردستی بازیافتی",
      "آموزش آنلاین ساخت دفتر برنامه‌ریزی",
      "آموزش آنلاین مهارت ارائه در جلسات"
    ]
  ],
  [
    "فروش تخصصی خانگی و شبکه‌های سفارش",
    [
      "فروش اینترنتی بسته‌های سیسمونی دست‌دوز",
      "فروش خانگی لوازم سفر کودک",
      "فروش بسته‌های هدیه معلمان",
      "فروش بسته‌های مناسبتی سازمانی",
      "فروش لوازم بایگانی خانگی",
      "فروش اشتراکی گل و گلدان",
      "فروش بسته‌های کاردستی فصلی",
      "فروش فایل‌های چاپی برنامه‌ریزی",
      "فروش آنلاین مجموعه فلش‌کارت",
      "فروش اشتراکی نمونه‌کار هنری",
      "فروش آنلاین زیورآلات بافتنی",
      "فروش بسته‌های شروع بافتنی",
      "فروش بسته‌های تعمیر لباس",
      "فروش دفترهای سفارشی هدیه",
      "فروش بسته آموزش خیاطی مبتدی",
      "فروش جعبه‌های جشن خانوادگی",
      "فروش بسته‌های نگهداری گیاه",
      "فروش آنلاین کارت دعوت سفارشی",
      "فروش بسته‌های طراحی دفتر کودک",
      "فروش سرویس شخصی‌سازی هدیه"
    ]
  ],
  [
    "خدمات دورکاری و اداری خانگی",
    [
      "پاک‌سازی داده‌های اکسل کسب‌وکار",
      "ورود اطلاعات کاتالوگ فروشگاه",
      "طبقه‌بندی اسناد دیجیتال مشتری",
      "زمان‌بندی جلسات آنلاین مشتری",
      "تهیه صورت‌جلسه از فایل صوتی",
      "برچسب‌گذاری محتوای وب مجاز",
      "کنترل نگارشی متن فارسی",
      "استانداردسازی فهرست منابع متنی",
      "تنظیم قالب نامه‌های اداری",
      "گردآوری قیمت‌های قابل استناد عمومی",
      "کنترل کیفیت فایل‌های PDF",
      "آزمون دستی فرم‌های وب",
      "تنظیم تقویم قرارهای مشتری",
      "پاسخگویی نوشتاری پشتیبانی فروش",
      "طراحی فرم نظرسنجی مشتریان",
      "تهیه فهرست موجودی از فاکتورهای مجاز",
      "سامان‌دهی ایمیل کاری با مجوز",
      "مستندسازی فرایندهای تکراری",
      "تهیه چک‌لیست تحویل سفارش",
      "تنظیم کتابخانه فایل‌های آموزشی"
    ]
  ],
  [
    "محصولات آموزشی و بازی‌های خانوادگی",
    [
      "ساخت بازی رومیزی شناخت رنگ کودک",
      "ساخت کارت آموزشی حروف فارسی",
      "ساخت پازل کاغذی نقشه ایران",
      "ساخت دفتر تمرین خوش‌خطی",
      "ساخت بسته قصه‌گویی خانوادگی",
      "ساخت کتابچه کاردستی با کاغذ",
      "ساخت برگه تمرین شمارش کودک",
      "ساخت الگوی آموزش ساعت برای کودک",
      "ساخت دفتر ثبت مطالعه نوجوان",
      "ساخت بسته بازی حافظه تصویری",
      "ساخت دفتر تمرین زبان انگلیسی خانواده",
      "ساخت پوستر آموزشی ایمنی خانه",
      "ساخت کارت پرسش و پاسخ تاریخ ایران",
      "ساخت دفترچه مهارت گفت‌وگو خانواده",
      "ساخت کیت علمی بدون مواد خطرناک",
      "ساخت بازی کلمات فارسی",
      "ساخت برگه تمرین هندسه ابتدایی",
      "ساخت کتابچه قصه تصویری اصیل",
      "ساخت کارت آموزشی مشاغل ایران",
      "ساخت بسته آموزش تفکیک پسماند کودک"
    ]
  ]
]


def canonical(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def digest(value: dict) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def catalog() -> list[dict]:
    if len(SECTORS) != 10 or any(len(items) != 20 for _, items in SECTORS):
        raise ValueError("HOME200_NOT_10_SECTORS_X_20_PROFESSIONS")
    unique = [name for _, items in SECTORS for name in items]
    if len(set(unique)) != 200:
        raise ValueError("HOME200_DUPLICATE_JOB")
    rows = []
    for sector, professions in SECTORS:
        for trade in professions:
            n = len(rows) + 1
            rows.append({
                "id": "HOME-IR-%03d" % n,
                "sector": sector,
                "trade": trade,
                "title": "راهنمای راه‌اندازی کسب‌وکار خانگی بانوان: " + trade + " در ایران",
                "selling_locale": "fa-IR",
                "country": "Iran",
                "storefront": "zomorodmelal.ir",
                "store_section": "education",
            })
    assert len(rows) == 200
    assert all(PRODUCT_RE.fullmatch(row["id"]) for row in rows)
    return rows


def order_for(spec: dict, rank: int) -> dict:
    book = {
        "schema": SCHEMA, "origin": ORIGIN,
        "source_product_id": spec["id"], "source_sha256": digest(spec),
        "priority": "P0", "priority_rank": rank,
        "priority_group": "OWNER_WOMEN_HOME200",
        "priority_reason": "OWNER_DIRECTIVE_2026_10_24",
        "family_id": "F07", "related_business_family": "F01",
        "phase": "original_iran_women_homebusiness_training_manual",
        "slot": 1, "subject": spec["title"],
        "home_business_scope": spec,
        "instruction": (
            "Write one fully original, realistic Persian training handbook "
            "for this specific home-based microbusiness, designed for "
            "women entrepreneurs in Iran without limiting their career options. "
            "Analyze real customer demand, current legal home-work eligibility, "
            "Iranian permits, safety and hygiene, limited household workspace, "
            "privacy, caregiving schedules, low-risk pilots, supplier vetting, "
            "equipment and sourcing, cashflow and working capital, operations, "
            "digital sales, payment, packaging and customer support. Verify "
            "each regulation with dated primary sources; no income guarantees, "
            "false endorsements, unlicensed food or child products, clinical "
            "claims or unauthorized copyrighted reproductions. Author at least "
            "100000 meaningful, nonduplicated original Persian prose words "
            "across 20 substantial chapters with real worked examples, "
            "costing assumptions, editable templates, exercises and answer keys. "
            "Require independent trade expert review, local-language editing, "
            "QC1000 and genuine payment plus delivery tests before publication."
        ),
        "editions": [{
            "locale": "fa-IR", "site": "zomorodmelal.ir",
            "education_page": "education", "title": spec["title"],
            "currency": "IRR", "audience": "Women entrepreneurs in Iran; home-compatible microbusiness",
        }],
        "minimum_original_prose_words": MIN_WORDS,
        "authoring_target_original_words": 105_000,
        "chapter_count_required": CHAPTER_COUNT,
        "actual_authored_chapters": 0,
        "home_business_field_review_verified": False,
        "regulatory_authorities_verified": False,
        "primary_sources_verified": False,
        "independent_qc1000_verified": False,
        "real_buyer_checkout_and_delivery_verified": False,
        "discount_authority": "OWNER_ONLY", "discount_percent": 0,
        "base_price_policy": "REAL_FAIR_IRR_UNDER_REVIEW",
        "acceptance": [
            "Document distinct household-scale business model and real Iranian buyer demand; no income promises",
            "Verify actual Iranian home-business permit eligibility with dated official primary sources",
            "Check food hygiene, child-product safety, household space and other regulated constraints as applicable",
            "Produce at least 100000 original useful Persian instructional prose words with 20 developed chapters",
            "Include sourced case studies, transparent cost and cashflow examples, templates and practical assessments",
            "Verify originality, copyright, readability, local editing, file rendering and accessible final PDF",
            "Obtain independent specialist and QC1000 approval without self-certification",
            "Verify real buyer checkout, invoice, protected download and email delivery before storefront release",
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
        raise ValueError("HOME200_SYMLINK_DIRECTORY")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir() or path.is_symlink():
        raise ValueError("HOME200_UNSAFE_DIRECTORY")


def read_json(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 200_000:
        raise ValueError("HOME200_UNSAFE_EXISTING_JSON")
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError("HOME200_JSON_OBJECT_REQUIRED")
    return doc


def save_new(path: Path, doc: dict) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError("HOME200_WOULD_OVERWRITE_ORDER")
    private_dir(path.parent)
    fd, temporary = tempfile.mkstemp(prefix=".home200-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(json.dumps(doc, ensure_ascii=False, sort_keys=True,
                               indent=2).encode("utf-8") + b"\n")
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temporary, 0o600)
        if path.exists() or path.is_symlink():
            raise ValueError("HOME200_DESTINATION_COLLISION")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def install(root_path: Path) -> dict:
    root = Path(root_path).resolve()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("HOME200_FACTORY_ROOT_INVALID")
    rows = catalog()
    area = root / "production-instructions"
    directory = area / "orders"
    private_dir(area)
    private_dir(directory)
    mutex = area / ".orders.lock"
    if mutex.is_symlink():
        raise ValueError("HOME200_LOCK_SYMLINK")
    with mutex.open("a+b") as lock:
        os.chmod(mutex, 0o600)
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        old = []
        for path in sorted(directory.iterdir()):
            if path.is_symlink() or not path.is_file() or not ORDER_RE.fullmatch(path.name):
                raise ValueError("HOME200_UNEXPECTED_QUEUE_ENTRY")
            item = read_json(path)
            if (item.get("schema") != SCHEMA or item.get("id") != path.stem
                    or item.get("public_distribution_allowed") is not False
                    or item.get("status") not in
                        ("issued", "in_engineering", "blocked_rework", "completed_verified")
                    or not HEX.fullmatch(str(item.get("fingerprint", "")))):
                raise ValueError("HOME200_UNSAFE_EXISTING_WORK_ORDER")
            old.append(item)
        if len(old) + 200 > 15_000:
            raise ValueError("HOME200_STORAGE_CAPACITY")
        existing = {}
        for item in old:
            if item.get("origin") == ORIGIN:
                key = item.get("source_product_id")
                if key in existing:
                    raise ValueError("HOME200_DUPLICATE_PRIOR_ID")
                existing[key] = item
        expected = {
            s["id"]: order_for(s, i) for i, s in enumerate(rows, 1)
        }
        for key, record in existing.items():
            if key not in expected or any(
                record.get(field) != value for field, value in expected[key].items()
                if field not in ("id", "created_utc", "status")
            ):
                raise ValueError("HOME200_EXISTING_ORDER_FINGERPRINT_CONFLICT:" + str(key))
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
            "book_goal_count": 200, "sector_count": 10,
            "minimum_total_original_prose_words": 20_000_000,
            "storefront": "zomorodmelal.ir", "section": "education",
            "locale": "fa-IR", "currency": "IRR",
            "origin": ORIGIN, "catalog_sha256": digest({"specs": rows}),
            "order_ids_ranked": ids,
            "published_books": 0, "fully_authored_books": 0,
            "independently_approved_books": 0,
            "discounts_approved": 0, "websites_modified": False,
        }
        index_path = area / "owner-women-home200-ir-p0-index.json"
        if index_path.exists():
            if read_json(index_path) != index:
                raise ValueError("HOME200_EXISTING_INDEX_CONFLICT")
        else:
            save_new(index_path, index)
    return {
        "registered": len(ids), "new_orders": created, "sectors": 10,
        "target_words": 20_000_000, "completed_books": 0, "published": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--factory-private")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        rows = catalog()
        assert len(rows) == len({x["title"] for x in rows}) == 200
        assert all(order_for(x, i)["publication_approved"] is False
                   for i, x in enumerate(rows, 1))
        print("HOME200_P0_SELFTEST=PASS")
        return
    if not args.factory_private:
        parser.error("--factory-private required except for --selftest")
    print(json.dumps(install(Path(args.factory_private)), ensure_ascii=False))


if __name__ == "__main__":
    main()
