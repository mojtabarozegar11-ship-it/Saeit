# زمرد ملل — بسته توسعه و آزمون آفلاین نسخه ۲

**وضعیت رسمی: DEVELOPMENT / NOT PRODUCTION READY**

این بسته حاوی کد توسعه است و نباید مستقیماً جایگزین `app.php` زنده شود. نسخه زنده افزونه‌های اختصاصی دارد که در این بسته نیستند. هیچ کلید، رمز، اطلاعات کارمند، داده مالی واقعی یا فایل پایگاه‌داده شرکت در بسته قرار ندارد.

## افزوده‌های این نسخه

- ماژول پرونده‌های عملیاتی زمین، کشت، نمونه آزمایشگاهی، بچ تولید و دارایی ثابت با گردش وضعیت، کنترل کیفیت دومرحله‌ای، عدم خودتأییدی، ثبت شواهد و تاریخچه تغییرناپذیر رویدادها.
- ممیزی فقط‌خواندنی حسابداری: کنترل توازن سند و ارز، ارجاعات نامعتبر، فاکتورهای با تسویه بیش از مبلغ، انبار منفی و سلامت SQLite.
- اصلاح تراکنش پرداخت و حرکت انبار در **نسخه توسعه**؛ تراکنش‌ها در صورت خطای اعتبارسنجی rollback می‌شوند.
- آزمون مستقل بکاپ/ریستور SQLite، تشخیص خطای مانده و عدم دستکاری فایل مبنا، آزمون ساختار SQL صنعتی و ایزولاسیون امنیت پل دستورات.
- اتصال صفحات داخلی به مجوز و CSRF موجود (صرفاً در کد توسعه؛ نه در سایت زنده).

## نتایج محلی قابل اثبات

گزارش دقیق در `OFFLINE_QA_REPORT.json` است. در محیط ساخت این بسته، ۲۰ بررسی (lint و مجموعه آزمون‌های Python) موفق شد. **شش آزمون رفتاری PHP که به PDO_SQLite نیاز دارند در این محیط اجرا نشدند**؛ بنابراین ادعای موفقیت آن‌ها، آمادگی تولید یا ۱۰۰٪ تکمیل تمام ERP وجود ندارد.

در GitHub Actions یا محیطی با PHP 8.3 و افزونه‌های `pdo_sqlite`, `sqlite3`, `mbstring`، دستور زیر تمام آزمون‌ها را اجرا می‌کند و فقط پس از موفقیت آزمون‌های PHP SQLite، چراغ کامل آفلاین را روشن می‌کند:

```bash
python3 scripts/run_all_offline_qa.py
python3 - <<'PY'
import json
r = json.load(open('OFFLINE_QA_REPORT.json'))
assert r['full_offline_database_tests_verified']
PY
```

گردش‌های مالی و حقوقی واقعی، اتصال امضاکننده به همین چت، قوانین اختصاصی مالیات و حقوق و دستمزد، تأیید صحت داده‌های تولیدی، آزمایش با نشست واقعی مدیر، پشتیبان‌گیری و بازیابی cPanel و انطباق مقررات هنوز نیاز به توسعه/تأیید مستقل دارد.

## دستور انتقال امن

1. فایل `MANIFEST.json` در این بسته را با SHA-256 تمام فایل‌ها تطبیق دهید.
2. از کد زنده و پایگاه‌داده‌های خصوصی، snapshot قابل‌بازیابی بگیرید و **بازیابی را در محل جداگانه آزمون کنید**.
3. همهٔ فایل‌های روی میزبان، به‌ویژه `app.php`, `site_store.php`, `site_agents.php` و مسیردهی Passenger را با نسخه منبع مطابقت دهید.
4. ابتدا روی staging مستقل و بدون هیچ پرداخت خارجی نصب کنید؛ روی مسیر عمومی یا پایگاه داده واقعی آزمایش نکنید.
5. همهٔ آزمون‌ها، مجوزهای کاربری، CSRF، XSS، محدودیت‌های پایگاه‌داده و ورود مدیر در staging باید موفق شوند.
6. پس از کنترل امنیتی و تأیید مدیر، با patch کوچک و قابل بازگشت ارتقا دهید؛ جایگزینی کامل فایل زنده ممنوع است.
7. **وظیفهٔ ساعتی ایجاد نکنید** تا کاربر پس از پایان و تأیید پروژه آن را مجاز کند.

هیچ قسمتی از این بسته مجوز صدور وجه، امضای قرارداد، تأیید استاندارد محصول یا انتشار عمومی کالای تولیدشده صادر نمی‌کند.

## Offline V3: accounting period freeze control

Added `period_controls.php` with two-person period close workflow, balance check per currency, fingerprint drift detection, immutable audit history, and SQLite triggers blocking direct writes to pending or closed periods. PHP synthetic suite and Python SQLite DDL/concurrency tests included. This is an incomplete internal accounting control, **not a replacement for tax/statutory close procedures**. The PHP/PDO_SQLite behavioral suite remains unexecuted locally until run in an environment with that extension. No production migration or deployment occurred.
