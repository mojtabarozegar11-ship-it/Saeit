# درگاه واحد TRON — تحویل نسخه خریداری‌شده، امنیت فایل خصوصی و حفظ حقوق خریدار
تاریخ: ۱۴ نوامبر ۲۰۲۶
**تنها ربات سازمانی مجاز: mojtaba.bot.ai**

## وضع واقعی و تغییر نسبت به چرخه قبلی
PR مادر #2299 یک مسیر جدید واحد TRON برای سایت فارسی ZomorodMelal.ir و سایت انگلیسی MojPlayWin.com دارد. در همان PR مادر طی توسعه هم‌زمان، فیلدهای **asset_relpath_snapshot**، **asset_sha256_snapshot**، **rights_document_sha256_snapshot** و **fulfillment_kind** به فاکتور اضافه شد تا تغییر قیمت و نسخه کاتالوگ خریدهای قدیمی را بی‌اعتبار نکند. این شاخه، آن فیلدها را **حفظ کرده** و امنیت واقعی فایل و تطبیق سند پرداخت را بر آنها اضافه می‌کند. کد تولیدی سایت هنوز deploy نشده است.

## 45 اقدام و کنترل قابل‌ردیابی در سورس
01. حفظ مسیر واحد درگاه TRON زمرد ملل و MojPlayWin؛ بدون عامل سازمانی جدید
02. بازسازی شاخه اصلاح روی نسخه دارای snapshot ثابتِ خرید قبلی به‌جای بازنویسی آن
03. تطبیق دقیق source_host فاکتور با هاست خریدار
04. تطبیق شناسه Order و PaymentIntent با همان فاکتور
05. تطبیق status=paid در هر سه مدل Invoice، Intent و Order
06. الزام timestamp مربوط به verified_at برای دریافت فایل
07. الزام receiver رسمی TRON برای همان فاکتور
08. تطبیق amount و currency در Intent و Order
09. الزام amount_sun صحیح مثبت و TXID پایین‌نویسی ۶۴ هگز
10. الزام proof_digest و fingerprint با ۶۴ نویسه هگز
11. الزام رویداد tron_finalized پردازش‌شده با پردازش‌زمان ثبت‌شده
12. الزام یک Credit از همان TXID، فاکتور و ارز و مبلغ
13. رد هر Credit اضافه برای همان سفارش برای جلوگیری از دوباره‌پرداخت
14. رد Order دارای refund، reversal یا chargeback
15. بررسی metadata سند Credit شامل network=tron-mainnet و asset=TRX
16. تطبیق amount_sun و receiver سند Credit با فاکتور
17. تطبیق proof_digest و webhook_event_id سند Credit با رویداد نهایی
18. الزام فقط یک قلم سفارش و quantity=1
19. تطبیق قیمت قلم با کل سفارش و ارز قلم با ارز سفارش
20. تحویل از asset_relpath_snapshot ثابت در فاکتور به‌جای آدرس فعلی کاتالوگ
21. تطبیق asset_sha256_snapshot ثابت با بایت واقعی سند خریداری‌شده
22. الزام rights_document_sha256_snapshot معتبر برای نسخه خریداری‌شده
23. حفظ حق خریدار پس از تغییر قیمت یا غیر فعال شدن آگهی محصول
24. حفظ حق خریدار پس از انتشار نسخه جدید فایل کاتالوگ بدون جایگزینی نسخه خریداری‌شده
25. رد تحویل پس از اعلام صریح rights_revoked=True
26. رد تحویل پس از اعلام صریح delivery_suspended=True
27. اعتبارسنجی مسیر دارایی به‌صورت رشته ASCII، عمق حداکثر ۸ و طول جزء حداکثر ۹۶
28. رد path traversal، URL، مسیر مطلق، قطعه خالی و backslash
29. محدودسازی فایل قابل‌دانلود به PDF/EPUB/ZIP
30. رد ریشه ذخیره‌سازی بدون پیکربندی یا با symlink در هر یک از اجداد
31. الزام root و زیرپوشه‌ها به مالک فعلی و عدم دسترسی گروه/دیگران
32. گشودن root/زیرپوشه و فایل با O_NOFOLLOW و dir_fd
33. رد فایل symlink، hardlink و FIFO و نوع غیرregular
34. رد فایل با دسترسی عمومی یا مالک نامعتبر
35. محدودسازی حداکثر فایل دیجیتال به ۱۲۸ MiB
36. محاسبه SHA256 در قطعات حداکثر ۶۴KiB از descriptor اصلی
37. کنترل پایداری file inode، اندازه، mode، mtime و ctime قبل و بعد از خواندن
38. کنترل امضای اولیه %PDF- و ZIP/EPUB PK سرآیند فایل
39. ارسال FileResponse از همان فایل بررسی‌شده و بستن descriptor در همه مسیرها
40. افزودن no-store/no-sniff و CSP sandbox به پاسخ دانلود
41. پوشش ۵۰ آزمون مستقل filesystem و تلاش برای فرار از مسیر خصوصی
42. پوشش ۵۰ آزمون Django برای receipt، entitlement تاریخی، chargeback، ownership و missing asset
43. حفظ ۱۳ آزمون قبلی receipt TRON بدون استفاده از شبکه واقعی
44. گردش‌کار GitHub read-only با فایل و پایگاه تست مصنوعی؛ عدم تماس با مالک/درگاه
45. ثبت دقیق محدودیت‌های حقوقی، تسویه و استقرار تولیدی به‌عنوان NO-GO

## جزئیات محدودیت تجاری
- تضمین حقوق خریدار نسبت به نسخه قبلی فقط وقتی فایل خصوصی تاریخی هنوز با همان SHA موجود باشد؛ اگر فایل حذف شده، با نسخه جدید جایگزین نمی‌شود و مسیر بازیابی خصوصی لازم است.
- SHA فایل، به‌تنهایی گواهی تأیید محتوای PDF/EPUB، قانونی بودن نشر، مالکیت خریدار یا وصول TRX نیست.
- تست‌های CI هیچ انتقال پول/شبکه، ارسال ایمیل، کد OTP، حذف فایل، تغییر تنظیمات حیات مشتری یا Deployment انجام نمی‌دهند.
- فعال‌سازی در تولید منوط به اثبات root واقعی Passenger، ارز و merchant قانونی، تأیید ایمیل خریدار، موجودی محصول، حقوق نشر و گواه مستقل chain finality است.
- parent PR #2299 در حال توسعه هم‌زمان است؛ هر نوع تعارض ادغام باید قبل از انتشار روی snapshot آخر آن حل شود. ادغام به main و اجرا روی VPS/cPanel انجام نشده.

## اسناد
- [PR این نسخه #2303](https://github.com/mojtabarozegar11-ship-it/Saeit/pull/2303): `fix/tron-private-asset-snapshot-20261114`، stacked روی `feature/tron-unified-multi-site-20261114`، Draft.
- `core/tron_gateway_delivery.py` — محل اصلی source fix.
- `tests/test_tron_private_paid_asset_20261114.py` — ۵۰ تست pure.
- `core/tests/test_tron_buyer_paid_delivery_20261114.py` — ۵۰ تست Django.
- `.github/workflows/tron-private-buyer-delivery-20261114.yml` — آزمون منبع، ۱۲۸ مورد شامل ۵۰ تست فایل، ۵۰ تست Django و ۲۸ تست TRON RPC موجود.

## شواهد نهایی آزمایش و migration
- [GitHub Actions scoped #43576590800](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43576590800)، job `132392052492`: **SUCCESS، 50/50 unittest + 78/78 pytest = 128/128 PASS**.
- `python manage.py check`: بدون خطا؛ `python manage.py makemigrations --check --dry-run`: **No changes detected**.
- مانع واقعی کشف‌شده حین تست: فیلدهای snapshot و reconcile در مدل در یک snapshot اولیه migration وجود نداشت؛ نسخه والد #2299 طی توسعه آن‌ها را به `0041_trongatewayinvoice` اضافه کرد. اصلاح این شاخه migration اصلی را با نسخه والد یکسان کرد و migration افزایشی موقتِ تکراریِ ایجادشده در همین چرخه کنار گذاشته شد؛ **هیچ data/schema واقعی از سرور حذف نشده است**.
- کد انتشار فقط روی branch Draft است؛ schema production اجرا/مهاجرت داده نشده، انتقال TRX یا فروش واقعی انجام نشده است.
