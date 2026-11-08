# کنترل محدودهٔ انتشار مدیریت و حسابداری زمرد ملل

این سند برای PR #2127 در شاخهٔ `feature/management-ledger-autopilot-safe-20261107` است. **هیچ انتشار تولیدی را مجاز نمی‌کند.**

## کنترل انجام‌پذیر بدون دسترسی تولیدی

```sh
python3 deploy/management_accounting_scope_gate.py --root . --manifest deploy/management_accounting_scope.json
python3 -m unittest -v scripts.tests.test_management_accounting_scope_gate
```

فرمان نخست فقط محتوای **هفت فایل مشخص‌شده در manifest** را با Git blob SHA-1 و SHA-256 تطبیق می‌دهد. `source_scope_verified: true` یعنی این هفت محتوای خوانده‌شده با snapshot بازبینی‌شده منطبق‌اند؛ به معنی نصب‌شدن آن‌ها روی هاست، مجازبودن عملیات انتشار، سلامت کل درخت مخزن یا نبود فایل اضافه در یک بستهٔ جدا نیست. خروجی همیشه `production_release_permitted: false` است. فرمان هیچ تغییری در پایگاه داده، Django، crontab، ایمیل، Passenger یا فایل‌های تولیدی ایجاد نمی‌کند.

## محدودهٔ دقیق تغییرات قابل‌بررسی

- `accounting/admin.py`
- `accounting/services.py`
- `command_center/integrated_ledger_api.py`
- `command_center/management/__init__.py`
- `command_center/management/commands/__init__.py`
- `command_center/management/commands/audit_management_cycles.py`
- `command_center/templates/command_center/integrated_dashboard.html`

هیچ مسیر دیگری، به‌ویژه `public_html/faremah`، بخش فروشگاه MojPlayWin، WSGI، فایل‌های تنظیمات سراسری، crontab و داده‌های مالی، در این محدوده مجاز نیست.

## گیت‌های باز، پیش از طراحی عملیات واقعی انتشار

### بررسی تکمیلی هویت پردازش Passenger

عملیات خواندنی `management_passenger_process_identity` به پل **موجود** `cpanel-direct-command-bridge.yml` اضافه شده است. این عملیات با حساب غیرمدیر، خروجی `passenger-status --show=xml` را فقط در حافظه تحلیل می‌کند و از گروهی با ریشهٔ دقیق `/home/zomorod2/Saeit`، شناسهٔ پردازش‌های فعال و یکسانی inode اجرایی با تنظیم `options/python` شاهد می‌گیرد؛ XML خام، مسیرهای داخلی، متغیرهای محیط، رمزها یا آرگومان‌های پردازش را چاپ نمی‌کند. ابزار فقط Python استاندارد را برای **خود بررسی** استفاده می‌کند و مفسر مجهول برنامه را اجرا نمی‌کند. آزمون‌های مستقل آن با `python3 -m unittest -v scripts.tests.test_management_passenger_status_attestation` اجرا می‌شوند.

فقط اگر گروه یکتا، پردازش‌های قابل‌خواندن متعلق به همان کاربر و تطبیق اجرایی همگی تأیید شوند، `active_interpreter_binary_attested: true` ثبت می‌شود؛ این مقدار **نسخهٔ محیط مجازی، بسته‌ها، source/runtime یا مجوز انتشار را ثابت نمی‌کند**. نبود ابزار `passenger-status`، نبود پردازش، عدم دسترسی `/proc` یا مسیر Python نسبی همگی نتیجهٔ «تأییدنشده» می‌دهند. این عملیات هنوز روی هاست زنده اجرا و تأیید نشده است. اجرای workflow برای پایش موقت است، نه اجرای دائمی چرخه‌ها.

1. **Passenger:** از منبع معتبر و خواندنی مشخص شود پردازش فعال `zomorodmelal.ir` واقعاً کدام مفسر Python و تنظیمات را استفاده می‌کند؛ وجود سه Python قابل‌اجرا به‌تنهایی اثبات نیست.
2. **Source/runtime:** نسخهٔ هفت فایلِ واقعی در هاست، تنظیمات WSGI و ریشهٔ برنامه با snapshot انتخابی تطبیق شوند. mismatch کنونی چند ماژول باید ثبت و پس از مجوز انتشار رفع شود.
3. **Migration:** صرفاً روی اتصال پایگاه دادهٔ فعال، وضعیت migration و سازگاری طرح بدون اعمال migration بررسی شود.
4. **Backup/restore/rollback:** نمونهٔ معتبر پشتیبان با هش و زمان، آزمایش بازیابی به محیط جدا و نقشهٔ rollback مستقل و قابل‌اجرا برای همین هفت فایل وجود داشته باشد.
5. **استقرار محدود و پایش:** بستهٔ دقیق هفت فایل با بررسی dry-run، امکان بازگشت، تأیید مالک و پایش سلامت ایجاد شود. فعال‌سازی زمان‌بندی مستقل فقط پس از احراز ایمنی مجاز است.

اسکریپت موجود `deploy/cpanel_deploy.sh` و مسیر `.cpanel.yml` برای این انتشار محدود **نباید اجرا شوند**: آن اسکریپت `migrate --noinput`، تغییر crontab، جمع‌آوری static، جایگزینی `public_html/faremah` و تحریک WSGI را انجام می‌دهد.

**مرز اختیار:** تا زمان ثبت شواهد هر پنج گیت، هیچ merge، deploy، restart، migration، تغییر حسابداری، فعال‌سازی cron یا پیام خارجی انجام نشود. GitHub Actions صرفاً برای نگهداری و بررسی کد است؛ اجرای چرخه‌های نهایی باید مستقل از آن طراحی و تأیید شود.
