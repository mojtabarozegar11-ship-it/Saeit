# کارخانه خاموش — انتقال دو بکاپ موجود ۵ نوامبر از cPanel به دو Google Drive

**وضعیت:** مسیر انتقال واقعی با رمزنگاری و خواندن مجدد هر قطعه ساخته شد؛ **هیچ بایتی از دو فایل هنوز آپلود نشده** و هیچ فایلی حذف نشده است. اجرای واقعی مشروط به OAuth سرور، سهمیه گوگل و کلید عمومی قابل‌بازیابی مالک است. کارخانه، Cron، MySQL، سایت و عوامل معامله‌گر خاموش/بدون تغییر می‌مانند.

## فایل‌های از قبل موجود — نه بکاپ تازه

| شناسه امن | نسخه منبع cPanel | حجم و SHA-256 از قبل ثبت‌شده |
|---|---|---|
| `nov5-a` | `restore-staging/factory/master-before-20261105T154953Z.sqlite3` | 1,408,634,880 بایت؛ `a9fd2175f9ace1a81d67cf7145e54b8621fd44cc06b0b2739bdc9345e21750e2` |
| `nov5-b` | `restore-staging/factory/master-before-20261105T210434Z.sqlite3` | 1,408,634,880 بایت؛ `402c16b67d430132701435eb4b3f79de88cd5c2479bb07c741c6674708a931be` |

این‌ها کپی تاریخی SQLite از VPS هستند، نه فایل MariaDB فعلی cPanel و نه آرشیو F-01 مورخ ۳۰ اکتبر. موجود بودن دوباره کپی در VPS به‌تنهایی به معنی داشتن دو نسخه مستقل در Google Drive نیست.

## مقصدهای واقعی ساخته‌شده و تأیید خصوصی‌بودن آن‌ها

پوشه `historical-nov5-snapshots` جدا از `current-backups` ایجاد شد:

- Google Drive A مالک اول: ID `1JBlaLNJP6BkpLcOWdLMISb451dKWHKUB`، زیر ریشه خصوصی `191sAkv4A01S9o6zhx-vM5xM7WO31qHPn`.
- Google Drive B مالک دوم: ID `1hVsGWr_lctO1VidDOIXnr6is2UYt5FBW`، زیر ریشه خصوصی `1e6D3Ek4k-4JT_oyEoiY_JejErZFssrC_`.

Google Drive connector در هر حساب جداگانه برگشت `shared=false`، `role=owner` و اتصال به Parent صحیح را تأیید کرده است. هر دو پوشه در لحظه ایجاد **خالی** بوده‌اند. این احراز اتصال ChatGPT، دسترسی `rclone` سرور نیست.

## اجرای امن روی Runner مورد اعتماد

در Runner خود مالک با **حساب غیردسترسی-root واقعی GitHub Actions** (که لزوماً `githubops` نیست)، همان تنظیم SSH قدیمی و احرازشده (پورت ۱۳۹۶ cPanel، SSH ProxyJump از VPS، اثر انگشت پین‌شده) و بدون روشن‌کردن کارخانه:

```bash
# فقط فراداده: اثبات وجود دو فایل قدیمی روی cPanel، بدون خواندن محتوای بکاپ
python3 -B -m scripts.factory_cpanel_existing_nov5_two_drive \
  --mode probe --snapshot nov5-a \
  --ssh-config /ABSOLUTE/OWNER_ONLY/ssh_config \
  --known-hosts /ABSOLUTE/OWNER_ONLY/cpanel_known_hosts
python3 -B -m scripts.factory_cpanel_existing_nov5_two_drive \
  --mode probe --snapshot nov5-b \
  --ssh-config /ABSOLUTE/OWNER_ONLY/ssh_config \
  --known-hosts /ABSOLUTE/OWNER_ONLY/cpanel_known_hosts
```

برای انتقال واقعی، ابتدا اتصال مستقل `factory_a` و `factory_b` و quota از طریق `scripts/factory_owner_drive_setup.py --configure` انجام شود (راهنمای PR #2686). Credential، `rclone.conf`، رمز یا private PEM **هرگز** وارد issue عمومی، Actions log، ChatGPT یا فایل عمومی نشود. حساب سیستم‌عامل باید همان مالک و فایل‌های SSH، known-hosts، کلید عمومی و rclone config مالک-تنها `0600` و غیر symlink باشند.

پارامتر `--rclone-exe` اختیاری است و در نبود آن، تنها پس از احراز OAuth، نسخهٔ موقت و بررسی‌شدهٔ rclone استفاده می‌شود. دستور زیر عمداً بدون comment در وسط ادامهٔ خط نوشته شده تا در Shell قابل‌اجرا بماند.

بعد از احراز دو هویت و دو سهمیه، اجرای تک‌فایلی با کلید عمومی رسمیِ دارای fingerprint تأییدشده (فایلِ کلید خصوصی و گذرواژه به Runner نیاید):

```bash
python3 -B -m scripts.factory_cpanel_existing_nov5_two_drive \
  --mode transfer --snapshot nov5-a \
  --ssh-config /ABSOLUTE/OWNER_ONLY/ssh_config \
  --known-hosts /ABSOLUTE/OWNER_ONLY/cpanel_known_hosts \
  --rclone-config /ABSOLUTE/OWNER_ONLY/rclone.conf \
  --public-pem /ABSOLUTE/OWNER_ONLY/verified-recovery-public.pem \
  --trusted-public-spki-sha256 64_CHARACTER_OWNER_VERIFIED_SHA256
# فایل دوم: فقط snapshot را به nov5-b تغییر دهید.
```

برنامه قبل از بازکردن محتوای بکاپ، وجود فایل cPanel را با `lstat` و نبود sidecar بررسی می‌کند، و مالکیت دو Remote خصوصی، خواندن proof موجود F-01 و فضای آزاد **هر دو** Google Drive را از ارائه‌دهنده تأیید می‌کند. اگر یکی fail شود، فایل حجیم باز نمی‌شود و انتقال متوقف می‌گردد.

سپس Python فقط‌خواندنی روی cPanel داده یکی از دو فایل ثابت و از پیش شناخته‌شده را با SSH رمزنگاری‌شده به Runner ارسال می‌کند؛ SHA-256، اندازه و تغییرنکردن inode/mtime/ctime در هر دو سمت بررسی می‌شود. هسته F01V2 روی Runner با RSA-3072-OAEP و AES-256-GCM هر قطعه را رمز می‌کند، در هر حساب جداگانه با rclone آپلود و از همان حساب دوباره دانلود و hash-check می‌کند، و فقط پس از پایان معتبر stream، manifest کامل را در هر دو مقصد ثبت می‌کند. از `tar`، `mysqldump`، `sync`، `rm`، `systemctl`، `crontab` و تغییر فایل‌های اصلی استفاده نمی‌شود. فضای scratch چندگیگابایتی روی VPS یا cPanel مصرف نمی‌شود. نام انتقال `factory-historical-<random>` است و هرگز `current-backups` را افزایش نمی‌دهد.

## پاک‌سازی هاست: هنوز مجاز نیست

موفقیت انتقال و hash-readback در دو Drive شرط لازم، اما **به‌تنهایی کافی نیست**. قبل از حذف هر کپی cPanel باید دریافت یک نسخه واقعی در محیط ایزوله با private key مالک، `PRAGMA integrity_check` SQLite، منطبق بودن با source hash و تفکیک واضح از سایر بکاپ‌های تنها موجود محرز شود. بعد از آن، مجوز موردی حذف **همان نام، اندازه و هش** از مالک گرفته شود؛ برای حذف گروهی یا فایل‌های ناشناس هیچ مجوزی استنتاج نشود.

اگر هر کدام از موانع برقرار نیست، نتیجه صحیح `HOLD` است، نه ادعای انتقال/پاک‌سازی. دو پوشه Google Drive جدید، جایگزین OAuth سرور نمی‌شوند.

**آخرین وضعیت**: `historical-nov5-snapshots` A/B = ۰ فایل فعلی، Upload=۰، Source deletion=۰، Fact​ory activation=۰، Space reclaimed=۰؛ تا زمانی که رسید واقعی چیز دیگری ثابت نکرده است.

### تفاوت مهم حساب محلی Runner و SSH مقصد

در اجرای واقعی [#44177089787](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44177089787)، آزمون‌های ۴۲+۷۹ در اولین چرخه موفق شدند اما بررسی ریموت به‌دلیل فرض اشتباه «کاربر Runner محلی = githubops» پیش از تماس با هاست متوقف شد. حساب `githubops` نام SSH روی VPS است، نه الزاماً اکانت سرویس GitHub Actions. شرط به اجرای **غیرروت**، فایل‌های SSH با مالکیت همان Runner و مجوز 0600، و اثرانگشت دقیق هر دو مقصد تغییر یافت. این اصلاح مجوز دسترسی اضافی ایجاد نمی‌کند، کاربر SSH مقصد را تغییر نمی‌دهد و کارخانه را روشن نمی‌کند. نتیجه اجرای اصلاح‌شده باید جداگانه با رسید دقیق HEAD بررسی شود؛ موفقیت تست‌ها جایگزین رسید اتصال cPanel نیست.


### رفع مشکل واردکردن ماژول در CLI

در [CI #44178162335](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44178162335) پس از موفقیت ۱۲۱ آزمون آفلاین، فراخوانی فایل با مسیر `python3 -B scripts/...py`، واردکردن package `scripts` را از بین برد و پیش از خواندن فایل‌های cPanel خطای `ModuleNotFoundError` داد. فراخوانی از ریشه مخزن به شکل `python3 -B -m scripts.factory_cpanel_existing_nov5_two_drive` اصلاح شد. این تغییر صرفاً روش اجرای کد است و هیچ مجوز، عملیات انتقال یا حذف تازه‌ای انجام نمی‌دهد.

### صفرنصب دائمیِ rclone و توقف امن جریان SSH

کدِ انتقالِ همین PR اکنون اگر `--rclone-exe` ارائه نشده باشد، **ابتدا** وجود فایلِ امن `rclone.conf` متعلق به کاربر Runner را بررسی می‌کند؛ در نبود OAuth پیش از هر دانلود ابزار یا خواندن داده، با `OWNER_RCLONE_OAUTH_CONFIG_NOT_PRESENT` توقف می‌کند. تنها پس از اثبات پیکربندی OAuth و وجود مسیر مطلق امن `RUNNER_TEMP`، ابزار رایگان `rclone v1.76.0` از Release رسمی با **SHA-256 و طول دقیق از پیش پین‌شده** به پوشهٔ موقت `0700` دریافت، بررسی و فقط برای همان اجرای انتقال فعال می‌شود؛ پس از اتمام یا خطا پوشهٔ اجرایی موقت حذف می‌شود. نصب دائمی روی VPS یا روشن‌کردن کارخانه لازم نیست. اگر از قبل باینری مورد اعتماد وجود دارد، پارامتر `--rclone-exe /ABSOLUTE/PINNED/rclone` همچنان پشتیبانی می‌شود.

خواندن لولهٔ SSH نیز **مهلت سکون ۱۵۰ ثانیه** و درخواست `os.read` با سقف ۱ مگابایت دارد؛ هنگ‌کردن SSH باعث انتظار نامحدود یا صدور مانیفست پایانِ کاذب نمی‌شود. این زمان‌سنج برای خواندن بلوک است، نه تضمین سرعت انتقال دو حساب Google Drive.

**مانع باقی‌مانده و غیرقابل دورزدن با کد:** OAuth دو حساب Google روی خود محیط مالک هنوز برقرار/تأیید نشده است و سهمیهٔ آزاد هر حساب باید از خود Google اثبات شود. اتصال ChatGPT به Google Drive به Runner منتقل نمی‌شود. هیچ هزینه‌ای، توکنِ منتشرشده یا دسترسی عمومیِ مقصد مجاز نیست.

## تصمیم عملی پاک‌سازی پس از ممیزی دو میزبان (۱۸ نوامبر ۲۰۲۶)

رسید VPS [#44185195584](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44185195584) دو فایل موجود را **واقعاً از دیسک VPS** در مجموع ۲٬۸۱۷٬۲۶۹٬۷۶۰ بایت خواند و SHA هر کدام را با نسخه‌های همان شناسه روی cPanel در [#44180075526](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44180075526) تطبیق داد: A=`a9fd2175…e21750e2`؛ B=`402c16b6…8708a931be`. بین A و B نباید dedup انجام شود، زیرا **هش دو زمان متفاوت با هم برابر نیست**.

پوشهٔ `restore-staging` در اندازه‌گیری واقعی cPanel دقیقاً **۲٬۸۱۷٬۲۶۹٬۷۶۰ بایت allocated** مصرف می‌کند. در صورت **حذف موردی فقط همین دو فایل**، با فرض احتساب کامل در سهمیه، فضای آزاد هاست ممکن است از ۱٬۰۵۹٫۹۸ MiB به حدود **۳٬۷۴۶٫۷۴ MiB** برسد. این عدد صرفاً برآورد پیش از حذف است؛ مقیاس actual تنها با cPanel UAPI بعد از حذف اثبات می‌شود.

**دو مسیر کاملاً متفاوت و نباید خلط شوند:**
- نگهداری **VPS-only**: یک نسخه از هر بکاپ روی VPS باقی می‌ماند، ولی نسخه مستقل در Google Drive هنوز وجود ندارد. فقط با **آگاهی و تأیید صریح مالک دربارهٔ کاهش سطح افزونگی**، بررسی مستقل `PRAGMA integrity_check`، و مجوز حذف مشخص cPanel قابل بررسی است؛ هیچ مجوز حذف تاکنون داده نشده.
- حفظ حفاظت سخت‌گیرانهٔ دو Drive: بکاپ‌ها ابتدا در دو حساب خصوصی جداگانه با رمزنگاری و بازیابی مستقل تأیید می‌شوند؛ بعد از آن می‌توان کپی‌های cPanel را با مجوز موردی حذف کرد. این راه به احراز OAuth دو حساب روی Runner یا یک مسیر تضمین‌شدهٔ بدون هزینه/عمومی‌نشدن داده نیاز دارد.

اسکریپت جدید `scripts/factory_cpanel_nov5_sqlite_integrity_readonly_20261118.py` (فقط‌خواندنی) صحت کامل هر دو SQLite را روی cPanel بررسی می‌کند. اجرای جدید workflow مستلزم رسید نهایی GitHub Actions است؛ اضافه‌شدن اسکریپت به PR اثبات نتیجه اجرا نیست.

**وضعیت واقعی هنگام ثبت:** هیچ فایل بزرگ جدیدی به Google Drive منتقل نشده؛ فایل cPanel حذف نشده؛ فضای هاست آزاد نشده؛ کارخانه همچنان خاموش است. فقط نتیجهٔ واقعی مقایسهٔ هش دو میزبان ۲/۲ موفق است. 

## اثبات مستقل سلامت نسخه‌های اصلی VPS (۱۸ نوامبر ۲۰۲۶)

ابزار `scripts/factory_vps_nov5_sqlite_integrity_readonly_20261118.py` و workflow `.github/workflows/factory-off-vps-nov5-integrity-readonly.yml` در همین PR ثبت شد. اتصال فقط‌خواندنی با هویت `githubops` و fingerprint پین‌شده، هش ثابت کد، و SQLite `mode=ro&immutable=1` اجرا می‌شود. این گیت مستقل از سلامت cPanel است و بکاپ در دو Drive را ثابت نمی‌کند.

رسید اجرای جدید: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44222230595 . تا زمانی که job موفق نشده، نتیجهٔ سلامت کامل SQLite روی نسخه‌های VPS را `NOT YET PROVEN` تلقی کنید. حذف cPanel همچنان HOLD است.


## رفع ابهام فایل اثبات مقصد — ۱۸ نوامبر ۲۰۲۶

در حساب دوم دو object مستقل با نام `manifest.json` در آرشیو تاریخی وجود دارد. هیچ فایل حذف یا تغییر داده نشده است. برای جلوگیری از ابهام این مسیر، تنظیم OAuth و انتقال تاریخی اکنون هر دو قطعه یکتای `F-01 Factory VPS encrypted recovery 2026-10-30/factory-runtime-001.f01enc.seg-21` را با SHA256 ثابت `06098cc64e9f1ac23670ac8d2f71e4402e668940b9a00c77a3184b1aec0e5b30` و اندازه 712 bytes استفاده می‌کنند. دو قطعه مستقل از خود Drive خوانده شدند؛ SHA و تمام بایت‌ها برابر بودند. این تغییر صرفاً یک نقص preflight را رفع می‌کند؛ OAuth مستقل سرور، ظرفیت واقعی و انتقال داده هنوز اثبات نشده‌اند. شاخه اصلاحی برای جلوگیری از اجرای دوباره گردش‌های پاکسازی به‌صورت مستقل نگهداری می‌شود.


## به‌روزرسانی انتقال پس از تبدیل تاریخی به gzip — ۱۸ نوامبر ۲۰۲۶

رسید [44254316705](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44254316705) نشان داد فایل‌های raw cPanel دیگر موجود نیستند و دو gzip معتبر با اندازه‌های 279659980 و 279659148 بایت باقی مانده‌اند؛ SHA gzip و SHA اصل بازسازی‌شده و CRC هر دو موفق، هر دو اصل SQLite در VPS سالم و فضای آزاد سهمیه cPanel برابر 3208.98 MiB گزارش شد. مقدار تاریخی پیشین جایگزین وضعیت جدید نیست؛ این بررسی مجوز حذف تازه یا استقرار ایجاد نمی‌کند.

در شاخه اصلاح مستقل، اسکریپت انتقال اکنون raw را اگر وجود دارد و معتبر است می‌پذیرد؛ فقط در صورت عدم وجود raw، gzip خصوصی 0600/بدون hardlink/با اندازه و SHA دقیق allowlist را انتخاب می‌کند. فایل raw نامعتبر باعث fallback نمی‌شود. با zlib محدود (حداکثر بلوک 1 MiB)، بدون ساخت فایل بازسازی روی cPanel، همان بایت‌های raw از مسیر SSH تحویل Runner می‌شوند. کنترل SHA gzip، CRC، عدم وجود داده trailing/عضو gzip اضافی، هدر SQLite و SHA/اندازه raw و inode/mtime/ctime پیش و پس از جریان الزامی است. قالب خروجی و قرارداد بازیابی قدیمی F01V2 تغییر نکرده؛ عدد probe size همچنان اندازه منطقی SQLite اصلی است، نه اندازه gzip روی دیسک. بنابراین سهمیه cloud محافظه‌کارانه بر پایه raw و حداقل ذخیره محاسبه می‌شود.

آزمون‌های انتقال gzip-only و رد خرابی و مجوز ناامن اضافه شدند. این شاخه هنوز ادغام نشده و آزمون جدید CI یا انتقال واقعی اجرا/تأیید نشده است. مانع اصلی همچنان OAuth مالک در Runner و ظرفیت تأییدشده دو Drive است. هیچ گردش cleanup جدیدی از این شاخه فعال نشده است.


## تأیید نسخه اصلاح‌شده روی Runner

گردش مستقل صرفاً خواندنی [44256935787](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44256935787) با 51/51 آزمون موفق و probe واقعی هر دو منبع روی cPanel موفق شد. source_contents_read=false, backup_uploaded=false, source_deleted=false. این گردش صرفاً دسترسی و فراداده را اثبات می‌کند، نه انتقال کامل.

ابزار `python3 -B scripts/factory_owner_drive_setup.py --configure` فقط در ترمینال تعاملی مورد اعتماد و حساب non-root مالک قابل اجرا است. نباید در CI، لاگ، گفت‌وگو یا از طریق ارسال token اجرا شود. نسخه جدید پس از OAuth، سهمیه هر دو حساب را از provider می‌خواند و مجموع دو آرشیو raw منطقی با سربار محافظه‌کارانه، دو manifest و ذخیره 1GiB را بررسی می‌کند: 3,895,227,392 bytes در هر حساب. حداقل اتصال 1GiB دیگر به معنی ظرفیت کافی دو بکاپ نیست. خروجی `historical_pair_capacity_screen_passed` و مقدار required در رسید v2 جدا هستند؛ در کمبود ظرفیت exit=2. این کنترل جدید هنوز با OAuth واقعی اجرا نشده است. ظرفیت MariaDB جاری جداگانه باید احراز شود.


## مجوز پایدار و اختصاصی Google Drive

مستند رسمی https://rclone.org/drive/#making-your-own-client-id اعلام می‌کند شناسه مشترک rclone در سال ۲۰۲۶ بازنشسته می‌شود. از Client ID اختصاصی نوع Desktop app که در پروژه Google Cloud متعلق به مالک ایجاد شده استفاده شود؛ Drive API باید فعال باشد. راهنمای رسمی احراز هویت سرور بدون مرورگر: https://rclone.org/remote_setup/ . برای اتصال SSH تعاملی از روش رسمی loopback tunnel پورت 53682 استفاده شود؛ احراز هویت در مرورگر مالک انجام می‌گیرد. توکن یا گذرواژه در GitHub، Actions log یا پیام عمومی وارد نشود.

طبق https://developers.google.com/identity/protocols/oauth2 ، وضعیت Testing برای برنامه خارجی معمولاً Refresh Token هفت‌روزه می‌دهد؛ مالک باید وضعیت برنامه و الزامات انتشار را در Google Auth Platform بررسی کند و هر مانع تأیید Google را از مسیر رسمی رفع نماید. وضعیت انتشار از شکل config قابل اثبات نیست. ابزار جدید Client ID اختصاصی، client_secret موجود، مجوز drive، Refresh Token مستقل دو remote و root صحیح را بررسی می‌کند و در صورت عدم احراز توقف دارد؛ این کنترل اثبات OAuth واقعی یا دائمی نیست. مالک باید در صفحه رسمی گوگل مجوزها را بررسی و رضایت دهد. هر دو حساب باید در محیط همان کاربر غیردسترسی-root انتقال مجاز شوند؛ اجرای تنظیمات در CI ممنوع است.

پس از اتصال، ابزار setup با config مالک-تنها و هش قطعه خصوصی و quota واقعی هر دو مقصد بررسی می‌شود. نیاز دو بکاپ تاریخی در هر حساب 3895227392 bytes است؛ این عدد ظرفیت لازم برای MariaDB جاری نیست. سازوکار دیگری که هزینه یا انتشار اطلاعات ایجاد کند فعال نشده است.


## مسیر اختیاری نگهداری gzip اصلی، بدون بازگردانی به حجم خام در انتقال

مسیر جدید `PYTHONPATH=scripts python3 -B -m scripts.factory_nov5_gzip_direct_dual_drive` به‌صورت مستقل و fail-closed نگهداری می‌شود. هر دو نسخه فشرده تاریخی دقیق از cPanel شناخته‌شده‌اند: 279659980 و 279659148 bytes؛ مجموع 559319128 bytes، در مقابل 2817269760 bytes خام. مسیر مستقیم، قبل از خواندن منبع مجوز اختصاصی OAuth و سهمیه هر مقصد را بررسی می‌کند و سپس gzip دقیق را از SSH پین‌شده، با کنترل SHA فشرده، SHA SQLite بازسازی‌شده، CRC، EOF و عدم تغییر metadata، داخل قالب قدیمی F01V2 رمزنگاری می‌کند. هیچ فایل raw روی cPanel یا VPS ساخته نمی‌شود. سقف ظرفیت محافظه‌کارانه زوج فشرده در هر Drive، با احتساب دو manifest و سربار و reserve یک GiB، 1637259608 bytes است. این عدد فقط نیاز محاسباتی است، نه quota واقعی. مسیر raw قبلی و گیت ظرفیت آن دست‌نخورده‌اند.

در محیط واقعی مالک ابتدا OAuth را با ابزار setup اختصاصی برقرار کنید. اگر اتصال و هویت موفق ولی گیت ظرفیت raw قدیمی ناموفق باشد، این به معنی رد ظرفیت مسیر فشرده نیست. پیش از انتقال هر نسخه، ابزار جدید دوباره quota لازم همان نسخه را از هر دو Drive می‌گیرد. پس از احراز ظرفیت زوج فشرده (حداقل 1637259608 bytes در هر مقصد پیش از اولین انتقال)، run را برای هر شناسه جدا انجام دهید:

```bash
PYTHONPATH=scripts python3 -B -m scripts.factory_nov5_gzip_direct_dual_drive \
  --snapshot nov5-a \
  --ssh-config /ABSOLUTE/OWNER_ONLY/ssh_config \
  --known-hosts /ABSOLUTE/OWNER_ONLY/cpanel_known_hosts \
  --rclone-config /ABSOLUTE/OWNER_ONLY/rclone.conf \
  --public-pem /ABSOLUTE/OWNER_ONLY/verified-recovery-public.pem \
  --trusted-public-spki-sha256 OWNER_VERIFIED_64_HEX_DIGEST
# سپس با snapshot nov5-b تکرار شود.
```

رسید موفق هر انتقال شامل namespace، ID زمان تاریخی، gzip_sha256 و original_sqlite_sha256 و manifest_sha256 است و باید در دفتر خصوصی نگهداری شود. برای restore: مانیفست و قطعه‌های رمز شده همان namespace را در محیط مستقل دریافت و با decrypt_to_isolated_file در فایل جدید .sqlite3.gz رمزگشایی کنید؛ SHA و اندازه gzip را با catalog پین‌شده تطبیق دهید، سپس به فایل SQLite جدید و ایزوله باز کنید و SHA خام، CRC و PRAGMA integrity_check را کنترل کنید. هرگز gzip را مستقیماً به SQLite یا دیتابیس جاری معرفی نکنید. بازیابی عملی این مسیر هنوز انجام نشده و انتقال واقعی نیز انجام نشده است؛ نه اجازه حذف، نه بکاپ MariaDB جاری.


## بازیابی مستقل نسخه فشرده تاریخی (نه MariaDB جاری)

ابزار `scripts/factory_nov5_gzip_isolated_restore.py` برای کامپیوتر مستقل و مورد اعتماد مالک ساخته شده است. پس از انتقال موفق و ثبت هش واقعی manifest در دفتر خصوصی، تمام قطعه‌های همان namespace را از یک Drive به پوشه خصوصی مستقل دانلود کنید. پوشه ورودی و پوشه خروجی باید مطلق، جدا، تحت مالکیت همان کاربر و 0700 باشند؛ فایل‌های رمز شده و کلید 0600. حداقل فضای لازم برای هر بازیابی شامل gzip، SQLite اصلی و ذخیره یک GiB است. کلید خصوصی و گذرواژه فقط روی کامپیوتر مالک باقی بماند؛ هیچ‌گاه CI، VPS انتقال یا گوگل درایو نیست.

```bash
PYTHONPATH=scripts python3 -B -m scripts.factory_nov5_gzip_isolated_restore \
  --snapshot nov5-a \
  --manifest /OWNER_PRIVATE_INPUT/f01v2-ACTUAL_RUN_ID-manifest.json \
  --manifest-sha256 ACTUAL_PIN_FROM_PRIVATE_RECEIPT \
  --input-dir /OWNER_PRIVATE_INPUT \
  --output-parent /OWNER_PRIVATE_ISOLATED_OUTPUT \
  --private-pem /OWNER_ONLY/RECOVERY_PRIVATE_KEY.pem --encrypted-key
```

این دستور مثال است؛ مقادیر واقعی باید از رسید انتقال موفق گرفته شوند. ابزار به کلید عمومی تثبیت‌شده مالک، هش manifest، AES-GCM تک‌تک قطعه‌ها، SHA و CRC gzip، اندازه و SHA فایل raw، SQLite quick_check/integrity_check در حالت immutable/read-only، و هش نهایی فایل روی دیسک مقید است. خروجی موفق در یک فایل جدید بدون overwrite منتشر می‌شود. فضای موقت ساخته‌شده همین فرایند پاک می‌شود؛ هیچ بکاپ قبلی حذف نمی‌شود. آزمون گردش مستقل از کلید مصنوعی استفاده می‌کند، نه کلید یا داده واقعی مالک. تا انتقال واقعی و رسید بازیابی واقعی در محیط مستقل، وضعیت cloud restore=not proven و safe_to_delete=false است. بازیابی هر دو حساب جداگانه لازم است.
