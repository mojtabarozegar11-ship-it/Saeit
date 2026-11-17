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

بعد از احراز دو هویت و دو سهمیه، اجرای تک‌فایلی با کلید عمومی رسمیِ دارای fingerprint تأییدشده (فایلِ کلید خصوصی و گذرواژه به Runner نیاید):

```bash
python3 -B -m scripts.factory_cpanel_existing_nov5_two_drive \
  --mode transfer --snapshot nov5-a \
  --ssh-config /ABSOLUTE/OWNER_ONLY/ssh_config \
  --known-hosts /ABSOLUTE/OWNER_ONLY/cpanel_known_hosts \
  --rclone-config /ABSOLUTE/OWNER_ONLY/rclone.conf \
  # --rclone-exe is optional: verified temporary client will be downloaded only after secure owner OAuth config exists.\n  --public-pem /ABSOLUTE/OWNER_ONLY/verified-recovery-public.pem \
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
