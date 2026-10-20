# ممیزی مستند دو سایت و کارخانه؛ انتقال انتخابی قابلیت‌ها — ۲۰ اکتبر ۲۰۲۶

## قاعده شمارش و شواهد
«وجود در کد»، «ثبت در Cron»، «بارگذاری ماژول»، «اجرای موفق»، «محصول فنی» و «محصول تجاری منتشرشده» شش وضعیت متفاوت‌اند. هیچ‌کدام جانشین دیگری نیستند. نسخه‌های Master Gen64، Evolution Gen65 و Factory Evolution 50 در یک تبار نرم‌افزاری مشترک نیستند و از روی عدد نسل نمی‌توان برتری را نتیجه گرفت.

منابع: [اجرای ۱۱ ایجنت زمرد](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39347243214)، [وضعیت خصوصی اکوسیستم](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39336664267)، [ممیزی عمیق رجیستری و کارها](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39336874327)، [کنترلر ۴۰ خانواده](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39347866929)، [پل خصوصی فروشگاه](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39348032748).

## ۱. زمرد ملل — ۱۱ ایجنت PHP مستقل سایت
هر یازده نقش در ۲۰۲۶-۱۰-۲۰ ۰۰:۲۲ UTC با status=ok و HTTP 200 مشاهده شد؛ این فقط سلامت URL است.

| code | مأموریت در رجیستری | مسیر آزمون | آخرین شاهد |
|---|---|---|---|
| master | هماهنگی و پایش سلامت عمومی | / | HTTP 200 |
| content | پایش دانشنامه و مقالات | /knowledge/ | HTTP 200 |
| seo | بررسی مسیر جست‌وجو | /search/ | HTTP 200 |
| commerce | نظارت بر فروشگاه | /store/ | HTTP 200 |
| agriculture | صفحه کشاورزی و راهنمای فنی | /agriculture/ | HTTP 200 |
| research | پایش تحقیقات و یادداشت‌های علمی | /research/ | HTTP 200 |
| economic | محتوای اقتصادی و مدیریت تولید | /economy/ | HTTP 200 |
| weather | مسیر راهنمای هواشناسی، نه داده زنده | /weather/ | HTTP 200 |
| quality | وضعیت درباره ما و لینک‌ها | /about/ | HTTP 200 |
| media | اخبار شرکت و انتشار مستند | /news/ | HTTP 200 |
| security | پاسخ صفحه ورود پنل خصوصی، بدون ورود | /business/ | HTTP 200 |

منابع: `content/zomorod-v11/site_agents.php` و `content/zomorod-v11/site_agent_workforce.php`.
در پایگاه داده خصوصی، ممیزی ۱۹ اکتبر تعداد ۶۵۰ اجرای پایش (۶۴۴ موفق، ۶ خطا)، ۹۰ خروجی بررسی (۸۰ review، ۱۰ blocked) و **صفر** رسید تأیید ارتقای نسل را نشان داده است. تست «۱۰۰ نسل» فقط شبیه‌سازی و آزمون ممانعت از ارتقای جعلی بوده، نه صد نسل واقعی.

## ۲. MojPlayWin — رجیستری و گزارش خصوصی
| نوع | شناسه یا نام | مأموریت مشخص از رجیستری / شرح | نتیجه شواهد |
|---|---|---|---|
| Master | master_gen64 | هماهنگی و heartbeat مستر اصلی | گزارش active_private در ۱۹ اکتبر |
| Evolution | agent_gen65 | پیش‌نویس، پایش و ارتقای کنترل‌شده خصوصی | گزارش gen65_operational_private |
| Site health | agriculture, commerce, content, economic, master, media, quality, research, security, seo, weather | ۱۱ نقش بررسی وضعیت مسیرهای سایت | فایل site_health_v11_port_20261018/last_scan.json در ممیزی ۱۹ اکتبر مفقود |
| Robots 5 | main_route_observer, editorial_integrity, draft_fingerprint, editorial_review_queue, agent_runtime_watch | مسیرهای اصلی، یکپارچگی و اثرانگشت پیش‌نویس، صف بازبینی و سلامت عامل‌ها | Cron ثبت‌شده؛ گزارش اجرای ۵ ربات در ممیزی ۱۹ اکتبر مفقود |
| Robots 6 | seo_metadata, reference_origin, release_reconciliation, public_content_security, disk_capacity, publication_worklist | فراداده سئو، منشأ منبع، تطبیق انتشار، امنیت محتوا، ظرفیت دیسک، فهرست انتشار | Cron ثبت‌شده؛ گزارش اجرای ۶ ربات در ممیزی ۱۹ اکتبر مفقود |
| 77 modules | ۷۷ جایگاه `module_1…module_77` در تله‌متری، نام اصلی وابسته به گزارش خصوصی | ماژول‌های بارگذاری/قابلیت؛ کارگر مستقل نیستند | ۷۷ hash و import در گزارش خصوصی تأیید؛ اجرای کاربردی هر ماژول اثبات نشده |
| Additional workers | worker_quality, worker_management | بازبینی کیفیت و هوش مدیریت اقتصادی | وجود زمان‌بندی؛ وضعیت اجرای دقیق نامعلوم |

منبع کد: `command_center/mpw_private_telemetry.py`؛ در آن TTL و برچسب‌های `healthy/stale/unknown/loaded_only/failed` از ادعاهای کاذب فعال‌بودن جلوگیری می‌کنند.

در گزارش خصوصی ۱۹ اکتبر: ۱۸ رکورد Agent فعال در Django، ۹۷۷۴ وظیفه completed، ۳۴ queued، ۱ blocked؛ این رکوردها **لزوماً** معادل ۱۸ کارگر مستقل سایت نیستند و در همان اکوسیستم کد کارخانه و خبرنامه نیز قرار دارند. دو محصول دیجیتال فعال در دیتابیس، فروش و تسویه موفقِ قابل استناد ندارند.

### ۱۸ کد Agent ثبت‌شده در Django (ممکن است میان سایت و کارخانه مشترک باشند)
`core_research`,
`factory-independent-qa-agent`,
`factory-independent-security-agent`,
`factory-independent-test-agent`,
`factory-launch-candidate-agent`,
`factory-localization-agent`,
`factory-market-eligibility-agent`,
`factory-market-research-agent`,
`factory-master-agent`,
`factory-opportunity-scoring-agent`,
`factory-opportunity-validation-agent`,
`factory-packaging-pricing-agent`,
`factory-product-builder-agent`,
`factory-product-strategist-agent`,
`newsletter-company-news`,
`newsletter-specialist`,
`newsletter-unit-reports`,
`newsletter-world-watch`.

## ۳. کارخانه — واقعیت تولید
در اجرای کنترلر ۲۰ اکتبر ۰۰:۳۱ UTC:
- ۴۰ خانواده ثبت‌شده؛ ۹ خانواده با سند فنی ۵۰ مرحله؛ ۷ خانواده با پایلوت فنی فقط؛ ۲۴ خانواده فاقد پایلوت/مجری معتبر.
- انبار فنی ۲۰ نسخه؛ ۳۲ نسخه در انتظار اصلاح. **صفر محصول جدید منتشرشده تجاری.**
- کنترلر خصوصی پنج‌دقیقه‌ای و پل خصوصی فروشگاه اجرا شده‌اند. ۳۶ رسید خصوصی در پل گزارش شده‌اند، اما نباید آن‌ها را فروش عمومی شمرد.
- مستر اقتصادی VPS در ممیزی قبلی فعال و دارای ۷ قابلیت و ۷۱۹ وظیفه completed بوده؛ این شاهد زمان خاص خود را دارد و اجرای زنده همین دقیقه را تضمین نمی‌کند.
- حلقه تحقیق عمومی کارخانه در ممیزی قبلی در مرحله ۴ به محدودیت ظرفیت/بودجه مستند برخورد داشت، هرچند بخش‌های جدید فنی از آن مستقل بهبود یافته‌اند.

## ۴. مقایسه بر اساس *قابلیت*، نه شماره نسل
| قابلیت در دو سایت | قابلیت متناظر کارخانه | نتیجه |
|---|---|---|
| سایت زمرد: `site_agent_workforce.php` — QA ساختاری HTML، title/H1/meta/link | QA محصول/ZIP و مجوز؛ فاقد آداپتور هم‌ارز مستقل HTML در لیست کنترل قبلی | **انتقال انتخابی انجام شد**: اصل PHP حفظ و منطق بدون شبکه به Python پورت شد |
| سایت زمرد: `site_agents.php` — رجیستری دقیق نقش و HTTP monitoring | رجیستری Django و factory agent audit جداگانه | **کپی منبع فقط**؛ اجرای PHP سایت در کارخانه مجاز نیست |
| MojPlayWin: `mpw_private_telemetry.py` — دقت در تازگی اجرای ماژول‌ها و `loaded_only` | ممیزی موجودی کد کارخانه، فاقد تفسیر برچسب‌های سلامت خصوصی MojPlayWin | **انتقال انتخابی انجام شد**: منبع حفظ و تابع TTL بدون وابستگی به cPanel منتقل شد |
| MojPlayWin: ۷۷ ماژول خصوصی / Gen65 | ۴۰ خانواده + Evolution 50 + Agent Registry | نیازمند دریافت ۷۷ فایل واقعی و هش نسخه از cPanel؛ **کپی نشده‌اند** |
| MojPlayWin: ۱۱ ربات اجرایی خصوصی | تولیدکننده‌ها و نظارت کارخانه | اجرای سایت‌محور و کارخانه‌محور قابل جایگزینی مستقیم نیست؛ **کپی اجرایی نشده** |
| مستر Gen64/Gen65 سایت‌ها | مستر اقتصادی VPS و پروتکل ۵۰نسلی | نسخه/هدف ناسازگار برای مقایسه عددی؛ ادعای نسل بالاتر رد می‌شود |

## ۵. تغییر کد ثبت‌شده و محدودیت
سه فایل منبع با محتوای **دقیقاً یکسان** از سایت‌ها به `ops/factory-site-capabilities/` منتقل شدند، بدون حذف اصل:
- `zomorod/site_agents.php`
- `zomorod/site_agent_workforce.php`
- `mojplaywin/mpw_private_telemetry.py`

آداپتور `scripts/factory_cross_site_capabilities.py` دو قابلیت مفید را برای کارخانه به‌صورت آفلاین بازاستفاده می‌کند: امتیازدهی ساختاری به قالب/پیش‌نمایش HTML محصولات، و ممیزی تازگی/سلامت گزارش ایجنت‌ها. ابزار `--repo` برابری بایت‌ها و تعداد واقعی نقش‌ها را بررسی می‌کند؛ `--html-file` آزمون کیفیت فایل محلی دارد. کد جدید هیچ اتصال شبکه‌ای، کلید، Cron، مجوز پرداخت یا انتشار سایت ندارد. هیچ ماژولِ وارده خودکار فعال یا به نسل بالاتر ارتقا اعلام نشده است.

**مرحله سروری نامشخص:** تا آزمایش سازگاری و استقرار واقعی بر VPS، کپی GitHub را «فعال در کارخانه زنده» اعلام نکنید. برای انتقال ۷۷ فایل خصوصی یا اجزای بدون منبع GitHub، مشاهده مستقیم فایل‌های cPanel و قیاس SHA پیش از جایگزینی لازم است. نباید بدون سند منبع به‌جای ماژول واقعی، پوسته ساختگی ساخته شود.
