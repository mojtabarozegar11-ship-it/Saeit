# Mojtaba.bot.ai | Format-aware fulfillment readiness — 2026-11-14

## Scope: remove unjustified cross-format locks, preserve payment and buyer safety
Current `core/fulfillment_preflight.py` applied PDF-style artifact SHA256, manifest and private file reference requirements even when `delivery_format` was `license_key` or `in_game_cosmetic`. These are **not necessarily downloadable binary files**; manufacturing a fake SHA string is not a legitimate way to make them pass. This branch creates a diagnostic-only, source-level contract for the five existing formats. It neither sends a license nor grants an in-game item.

The sole canonical executor identity stays `mojtaba.bot.ai`. All changes are on a stacked Draft branch; no production/site/DB migration, payments, emails, trading, tokens, costs or deployment.

## Product-specific source evidence (never independent payment or delivery proof)

| Format | Required source evidence | Explicitly not required | Still unverified |
|---|---|---|---|
| PDF/EPUB/ZIP | Rights, QC, terms, version, license, *separate* file and manifest SHA256, safe private asset ref | — | actual file bytes, customer download, settlement |
| `license_key` | Rights, QC, terms, version, license code, private license inventory ref, reviewed issuance, `buyer_account` binding | PDF/ZIP file hashes | real inventory existence, individual key issuance, buyer confirmation, settlement |
| `in_game_cosmetic` | Rights, QC, terms, version, allowed Crown SKU, verified checkout source, private entitlement ref, reviewed entitlement, `buyer_account` binding | PDF/ZIP file hashes and legal license code | on-chain confirmation, authenticated entitlement grant, client-side acceptance |

**Important:** Metadata boolean flags and SHA-looking strings are self-asserted. They are source-gate hints, not proof of real product bytes, lawful license inventory or paid entitlement.

## 38 distinct implemented checks (code + regressions)
01. حداقل یک شناسه سفارش مثبت و با نوع integer؛ داده معیوب موجب انتشار نمی‌شود
02. کنترل وضعیت سفارش paid؛ سایر وضعیت‌ها بلاک می‌شوند
03. سقف پذیرش مبلغ: Decimal متناهی و مثبت
04. کد ارز سفارش با الگوی استاندارد uppercase؛ USD/IRR/TRX مجاز
05. خریدار باید فعال باشد؛ فعال‌بودن با مقدار صریح True سنجیده می‌شود
06. حساب کارکنان یا superuser به‌عنوان خریدار معمولی پذیرفته نمی‌شود
07. آدرس ایمیل خریدار فقط از نظر ساختار اولیه بررسی می‌شود؛ مالکیت آن اثبات‌نشده می‌ماند
08. تعداد اقلام سفارش دقیقاً یک؛ سفارش چندقلمی نیازمند چند رسید است
09. تعداد نسخه/quantity دقیقاً یک، بدون صدور چندگانه
10. یکسانی ارز قلم سفارش با سفارش
11. یکسانی ارز محصول فهرست‌شده با سفارش، مستقل از ارز قلم
12. قیمت قلم و line_total با مبلغ واقعی سفارش تطبیق داده می‌شود
13. محصول باید فعال باشد
14. عنوان محصول غیرخالی و بدون whitespace اضافه و کاراکتر کنترلی باشد
15. فروشندهٔ مالک محصول باید فعال، staff و superuser باشد
16. فراداده محصول حتماً شیء JSON باشد؛ سایر انواع به‌جای استفاده خام، بلاک می‌شوند
17. تأیید حقوق انتشار/مالکیت، مستقل از فرمت، اجباری می‌ماند
18. تأیید QC مستقل، مستقل از فرمت، اجباری می‌ماند
19. تأیید شرایط خریدار، مستقل از فرمت، اجباری می‌ماند
20. فرمت محصول فقط pdf/epub/zip/license_key/in_game_cosmetic پذیرفته می‌شود
21. فرمت نامعتبر array/dict/bool بدون TypeError و HTTP 500 رد می‌شود
22. product_type بازی با فرمت فایل یا لایسنس قابل جا زدن نیست
23. product_type معمولی با فرمت آیتم درون‌بازی قابل جا زدن نیست
24. شماره نسخهٔ تحویل باید ساختار سه‌بخشی معتبر داشته باشد
25. برای PDF/EPUB/ZIP فقط اثرانگشت SHA256 فایل خصوصی لازم است
26. برای PDF/EPUB/ZIP اثرانگشت SHA256 manifest خصوصی جدا لازم است
27. فایل و manifest نمی‌توانند یک SHA256 مشترک داشته باشند
28. مرجع فایل باید شناسهٔ داخلی محدود باشد؛ URL و مسیر مطلق ممنوع
29. برنامه مجوز نرم‌افزار به‌جای فایل ساختگی نیازمند license inventory ref خصوصی است
30. صدور مجوز نرم‌افزار نیازمند تأیید دستی issuance است
31. مجوز نرم‌افزار باید به حساب خریدار bind شود
32. آیتم درون‌بازی به SKU معتبر پنج‌گانه Crown محدود است
33. آیتم درون‌بازی نیازمند crown_checkout_verified صریح است
34. آیتم درون‌بازی باید ref داخلیِ entitlement داشته باشد
35. حق درون‌بازی باید به حساب خریدار bind شود
36. حق درون‌بازی نیازمند entitlement reviewed صریح است
37. تمام گواه‌های پرداخت مستقل، حق دانلود، تحویل و ایمیل خریدار همچنان false می‌مانند
38. خروجی ممیزی هیچ token، asset_ref یا هویت خریدار را منتشر نمی‌کند

## Acceptance and mandatory control evidence
- [Stacked Draft PR #2290](https://github.com/mojtabarozegar11-ship-it/Saeit/pull/2290) on the existing buyer-delivery recovery [#2289](https://github.com/mojtabarozegar11-ship-it/Saeit/pull/2289).
- Source: `core/fulfillment_preflight.py`, no new bot, downloader, wallet, gateway or order schema.
- 42 synthetic Django cases in `core/tests/test_mojtaba_fulfillment_formats_20261114.py`, plus 55 prior buyer-delivery/Crown tests in CI; actual PASS must be read from exact head before any claim.
- CI: `.github/workflows/mojtaba-format-aware-fulfillment-ci.yml`, owner-approved source-only isolated test DB and locmem email, no customer records.
- Input and output are checked as *observed source*, no actual delivery: `delivery_allowed=false`, `delivery_verified=false`, `independent_settlement_verified=false`, `buyer_email_verified=false`, `private_file_bytes_verified=false`, `customer_download_receipt_verified=false`.
- No sales, cash, approved quote, settlement provider callback, real order or delivery receipt is asserted.
- Explicit separate approval, immutable backup, account identity, rights/quality evidence, payment finality, private delivery and service-owner acceptance are required prior to publication.

## Commercial service opportunity without spending
1. A licensed software/educational product can be inspected against a **license** evidence contract instead of fake PDF-style hashes.
2. A digital educational book can be inspected against an actual **file** evidence contract.
3. Crown Defender virtual cosmetics can be inspected against an **account entitlement** source contract.
4. No quote, purchase or notification is generated until the legal offer, approved live checkout and irreversible settlement gates are demonstrated.

**NO GO: production**. Green GitHub Actions = verified source behavior only. Current cPanel registered Passenger root and exact runtime template are still not independently attested.
