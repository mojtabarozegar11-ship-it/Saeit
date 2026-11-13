"""Evidence-led 102-page multilingual education copy (no fabricated markets or offers).

17 brand editorial topics x 2 informational page kinds x 3 languages.
This module NEVER produces signals, quotes, prices, offers, checkout or trading commands.
It only supplies copy to the existing finance page template; all CSS is preserved.
"""
BRAND_TOPICS = {
    "saman": ("سواد مالی و دفتر ثبت تصمیم", "financial literacy and decision journals", "الثقافة المالية وسجل القرارات"),
    "zahra": ("تحلیل سناریو و عدم‌قطعیت", "scenario analysis and uncertainty", "تحليل السيناريوهات وعدم اليقين"),
    "zhila": ("اعتبارسنجی داده و خطای اندازه‌گیری", "data validation and measurement error", "التحقق من البيانات وأخطاء القياس"),
    "marzieh": ("اقتصاد تولید کشاورزی", "agricultural production economics", "اقتصاد الإنتاج الزراعي"),
    "maryam": ("بودجه‌بندی و جریان نقدی", "budgeting and cash flow", "إعداد الميزانيات والتدفق النقدي"),
    "marjan": ("موجودی و حاشیه مشارکت", "inventory and contribution margin", "المخزون وهامش المساهمة"),
    "faremah": ("هزینه‌یابی خدمات زیبایی", "beauty-service cost accounting", "محاسبة تكاليف خدمات التجميل"),
    "farnaz": ("اقتصاد محصولات دیجیتال", "digital-product economics", "اقتصاد المنتجات الرقمية"),
    "taniya": ("اقتصاد یادگیری و بازی", "learning and game economics", "اقتصاد التعلم والألعاب"),
    "raham": ("طراحی بازی و تحلیل مشارکت", "game design and engagement analysis", "تصميم الألعاب وتحليل المشاركة"),
    "mojtaba": ("اقتصاد تولید و روش تحقیق", "production economics and research methods", "اقتصاد الإنتاج ومناهج البحث"),
    "mohammad": ("برآورد هزینه و ریسک ساخت‌وساز", "construction cost and risk estimation", "تقدير تكاليف البناء ومخاطره"),
    "mostafa": ("مدیریت ریسک پروژه‌های کوچک", "small-project risk management", "إدارة مخاطر المشروعات الصغيرة"),
    "17": ("تحلیل تقاضا و رفتار مصرف‌کننده", "demand analysis and consumer behavior", "تحليل الطلب وسلوك المستهلك"),
    "21": ("سرمایه در گردش و نقدینگی", "working capital and liquidity", "رأس المال العامل والسيولة"),
    "206": ("هزینه فرصت و مقایسه جایگزین‌ها", "opportunity cost and alternative choices", "تكلفة الفرصة البديلة ومقارنة الخيارات"),
    "108": ("تحلیل حساسیت و آزمون فرض‌ها", "sensitivity analysis and assumption testing", "تحليل الحساسية واختبار الافتراضات"),
}
BRAND_CASES = {
    "saman": ("مثال فرضی سمن: درآمد ۱۲۰۰ و هزینه ۹۰۰ واحد است؛ پس پس‌انداز ۳۰۰ واحد، معادل ۲۵٪ درآمد است.", "SAMAN hypothetical case: income 1,200 less expenses 900 yields savings of 300 units, or 25% of income.", "مثال افتراضي لسمن: دخل ١٢٠٠ ومصروفات ٩٠٠؛ الادخار ٣٠٠ وحدة، أي ٢٥٪ من الدخل."),
    "zahra": ("مثال فرضی زهرا: درآمد سناریوهای ۸۰، ۱۰۰ و ۱۲۰ با وزن‌های ۳۰٪، ۵۰٪ و ۲۰٪ میانگین وزنی ۹۸ واحد می‌دهد.", "ZAHRA hypothetical scenarios: outcomes of 80, 100 and 120 with probabilities 30%, 50% and 20% have weighted mean 98.", "مثال افتراضي لزهرة: نتائج ٨٠ و١٠٠ و١٢٠ بأوزان ٣٠٪ و٥٠٪ و٢٠٪ تعطي متوسطاً مرجحاً ٩٨."),
    "zhila": ("مثال فرضی ژیلا: اگر ۸ مورد از ۲۰۰ ثبت داده ناقص باشد، نرخ خطای ثبت برابر ۴٪ است؛ اعتبار اقتصادی داده باید جداگانه بررسی شود.", "ZHILA hypothetical data check: 8 invalid records in 200 equal a 4% data error rate; economic validity requires separate review.", "مثال افتراضي لجيلا: ٨ سجلات غير صحيحة من ٢٠٠ تعني نسبة خطأ ٤٪، مع ضرورة مراجعة صلاحية البيانات."),
    "marzieh": ("مثال فرضی مرضیه: تولید ۶ تن با درآمد واحد ۵۰۰، درآمد ناخالص ۳۰۰۰ است؛ با هزینه ۲۰۰۰، مازاد قبل از هزینه سرمایه ۱۰۰۰ می‌شود.", "MARZIEH hypothetical farm: 6 tonnes at 500 each yield 3,000 gross; after 2,000 cost, the pre-capital surplus is 1,000.", "مثال افتراضي لمرضية: إنتاج ٦ أطنان بسعر ٥٠٠ يحقق ٣٠٠٠ إجمالي؛ وبعد تكلفة ٢٠٠٠ يبقى فائض ١٠٠٠ قبل تكلفة رأس المال."),
    "maryam": ("مثال فرضی مریم: دریافت نقدی ماهانه ۳۵۰ و پرداخت نقدی ۲۸۰ واحد، جریان نقدی خالص مثبت ۷۰ واحد ایجاد می‌کند؛ سود حسابداری لزوماً برابر نیست.", "MARYAM hypothetical month: cash inflows of 350 minus outflows of 280 produce net cash flow of +70, not necessarily accounting profit.", "مثال افتراضي لمريم: تدفقات نقدية داخلة ٣٥٠ وخارجة ٢٨٠ تنتج صافي تدفق ٧٠، وهو لا يساوي بالضرورة الربح المحاسبي."),
    "marjan": ("مثال فرضی مرجان: قیمت فروش ۳۵، خرید ۲۰ و هزینه متغیر ۵ واحد است؛ حاشیه مشارکت هر کالا ۱۰ واحد پیش از سربار است.", "MARJAN hypothetical item: sale price 35 minus purchase cost 20 minus variable handling 5 leaves contribution of 10 per item.", "مثال افتراضي لمرجان: سعر البيع ٣٥ ناقص شراء ٢٠ ومناولة متغيرة ٥ يترك هامش مساهمة ١٠ لكل وحدة."),
    "faremah": ("مثال فرضی فریماه: دریافت خدمت ۶۰، مواد مصرفی ۱۲ و دستمزد مستقیم ۲۰ واحد باشد؛ حاشیه مشارکت هر جلسه ۲۸ واحد است.", "FAREMAH hypothetical service: receipt 60 less consumables 12 and direct labor 20 leaves a per-session contribution of 28.", "مثال افتراضي لفريماه: إيراد الجلسة ٦٠ ناقص مستهلكات ١٢ وأجر مباشر ٢٠ يعطي مساهمة ٢٨ لكل جلسة."),
    "farnaz": ("مثال فرضی فرناز: محصول آموزشی با قیمت ۲۰، هزینه تحویل ۲ و کارمزد ۱ واحد، حاشیه مشارکت ۱۷ واحد پیش از بازاریابی دارد.", "FARNAZ hypothetical digital guide: price 20 minus fulfillment 2 and payment fee 1 gives contribution 17 before acquisition costs.", "مثال افتراضي لفرناز: منتج تعليمي بسعر ٢٠ ناقص تسليم ٢ ورسم دفع ١ يترك مساهمة ١٧ قبل التسويق."),
    "taniya": ("مثال فرضی تانیا: اگر از ۱۰۰ شروع‌کننده بازی، ۴۰ نفر مرحله آموزشی را تمام کنند، نرخ تکمیل ۴۰٪ است؛ این آمار واقعی کاربران نیست.", "TANIYA hypothetical learning game: 40 completions among 100 starters yield a 40% completion rate; this is not real user data.", "مثال افتراضي لتانيا: إكمال ٤٠ من أصل ١٠٠ لاعب بدأوا يعطي نسبة إكمال ٤٠٪، وليس إحصاءً حقيقياً."),
    "raham": ("مثال فرضی رهام: بازگشت ۱۲۰ بازیکن از ۳۰۰ نفر در روز هفتم، ماندگاری روز هفتم را ۴۰٪ نشان می‌دهد؛ داده واقعی وجود ندارد.", "RAHAM hypothetical game: 120 of 300 players returning on day seven gives 40% D7 retention, not an observed metric.", "مثال افتراضي لرهام: عودة ١٢٠ من أصل ٣٠٠ لاعب في اليوم السابع تعني احتفاظاً بنسبة ٤٠٪، وليس قياساً فعلياً."),
    "mojtaba": ("مثال فرضی مجتبی: اگر ۱۰ واحد تولید اضافه ۳۰۰ واحد هزینه ایجاد کند، هزینه نهایی میانگین این افزایش تولید ۳۰ واحد است.", "MOJTABA hypothetical production: 10 additional units costing 300 imply incremental average cost of 30 per extra unit.", "مثال افتراضي لمجتبى: زيادة الإنتاج ١٠ وحدات بتكلفة ٣٠٠ تعني تكلفة إضافية وسطية ٣٠ لكل وحدة."),
    "mohammad": ("مثال فرضی محمد: برآورد ساخت ۱۰۰٬۰۰۰ و ذخیره احتیاطی ۱۰٪، بودجه برنامه‌ریزی ۱۱۰٬۰۰۰ واحد می‌طلبد؛ قیمت واقعی پروژه نیست.", "MOHAMMAD hypothetical build: estimated construction 100,000 plus a 10% contingency yields a planning budget of 110,000, not a quote.", "مثال افتراضي لمحمد: تقدير بناء ١٠٠٠٠٠ مع احتياطي ١٠٪ ينتج ميزانية تخطيط ١١٠٠٠٠، وليست عرض سعر."),
    "mostafa": ("مثال فرضی مصطفی: احتمال رخداد ریسک ۲۰٪ و خسارت ۲۰۰۰ واحدی، زیان موردانتظار ۴۰۰ واحد دارد؛ این مقدار حداکثر زیان نیست.", "MOSTAFA hypothetical risk: 20% event probability and 2,000 impact imply expected loss 400, not the maximum possible loss.", "مثال افتراضي لمصطفى: احتمال خطر ٢٠٪ وأثر ٢٠٠٠ ينتج خسارة متوقعة ٤٠٠، وليس أقصى خسارة ممكنة."),
    "17": ("مثال فرضی برند ۱۷: افزایش قیمت از ۱۰ به ۱۱ و کاهش تقاضا از ۱۰۰ به ۹۰، کشش تقریبی پایه را ۱- نشان می‌دهد؛ روش میانی نتیجه متفاوتی دارد.", "Brand 17 hypothetical demand: price rising 10 to 11 while quantity falls 100 to 90 suggests baseline approximate elasticity of -1; midpoint elasticity differs.", "مثال افتراضي للعلامة ١٧: السعر من ١٠ إلى ١١ والكمية من ١٠٠ إلى ٩٠ تعطي مرونة تقريبية أساسية سالب ١؛ طريقة المنتصف تختلف."),
    "21": ("مثال فرضی برند ۲۱: دارایی جاری ۱۵۰ و بدهی جاری ۹۰ واحد، سرمایه در گردش خالص ۶۰ واحد ایجاد می‌کند؛ نقدبودن دارایی‌ها باید جدا بررسی شود.", "Brand 21 hypothetical liquidity: current assets 150 minus current liabilities 90 equal working capital of 60; cash convertibility needs review.", "مثال افتراضي للعلامة ٢١: الأصول المتداولة ١٥٠ ناقص الخصوم المتداولة ٩٠ تعطي رأس مال عامل ٦٠؛ يجب مراجعة قابلية التحويل لنقد."),
    "206": ("مثال فرضی برند ۲۰۶: اگر طرح A سود ۸۰ و طرح B سود ۶۰ واحدی داشته باشد، هزینه فرصت انتخاب B نسبت به A برابر ۲۰ واحد است.", "Brand 206 hypothetical choice: option A earns 80 while B earns 60; choosing B has an opportunity cost of 20 relative to A.", "مثال افتراضي للعلامة ٢٠٦: بديل أ بعائد ٨٠ وبديل ب بعائد ٦٠ يجعل تكلفة الفرصة لاختيار ب مساوية ٢٠."),
    "108": ("مثال فرضی برند ۱۰۸: با درآمد ۱۴۰۰ و هزینه ۱۰۰۰، مازاد ۴۰۰ است؛ افزایش ۱۰٪ هزینه، مازاد را به ۳۰۰، یعنی ۲۵٪ کمتر می‌رساند.", "Brand 108 hypothetical sensitivity: revenue 1,400 less cost 1,000 leaves 400; a 10% cost rise leaves 300, a 25% surplus decline.", "مثال افتراضي للعلامة ١٠٨: إيراد ١٤٠٠ وتكلفة ١٠٠٠ يعطي فائض ٤٠٠؛ زيادة التكلفة ١٠٪ تخفض الفائض إلى ٣٠٠، أي بنسبة ٢٥٪."),
}

LOCALES = {"fa": 0, "en": 1, "ar": 2}
KINDS = ("signals", "store")

TEXT = {
    "fa": {
        "signals": {
            "intro": "راهنمای کاربردی {topic}: ساخت سناریوی پایه، خوش‌بینانه و بدبینانه با ثبت منبع داده، افق زمانی و محدودیت‌های تصمیم. این محتوا سیگنال خرید یا فروش نیست.",
            "section_label": "کاربرگ آموزشی تحلیل بازار",
            "steps_heading": "کاربرگ چهارمرحله‌ای تصمیم",
            "steps": "۱. سؤال اقتصادی را دقیق بنویسید. ۲. منبع، تاریخ و کیفیت داده را ثبت کنید. ۳. سه سناریو با فرض‌های صریح بسازید. ۴. آستانهٔ توقف، میزان عدم‌قطعیت و شرایط بازنگری را مستند کنید. این مراحل باید برای موضوع {topic} جداگانه تکمیل شوند.",
            "example_heading": "مثال محاسباتی؛ نه توصیهٔ معاملاتی",
            "example": "صرفاً برای آموزش، سرمایهٔ فرضی ۱٬۰۰۰ واحد و سقف ریسک ۱٪ یعنی ۱۰ واحد زیان بودجه‌بندی‌شده است. اگر فاصلهٔ توقف فرضی ۲٪ باشد، اندازهٔ اسمی موقعیت ۱۰ ÷ ۰٫۰۲ = ۵۰۰ واحد به دست می‌آید؛ کارمزد، لغزش قیمت، شکاف و نقدشوندگی می‌توانند زیان را بیشتر کنند. هیچ دارایی یا معامله‌ای پیشنهاد نمی‌شود.",
        },
        "store": {
            "intro": "راهنمای ارزیابی منابع آموزشی دربارهٔ {topic}: نمونهٔ محتوا، اعتبار مؤلف، تاریخ ویرایش، مجوز استفاده و شرایط تحویل را پیش از خرید کنترل کنید. این صفحه فهرست فروش فعال یا قیمت قطعی ندارد.",
            "section_label": "راهنمای ارزیابی محصول آموزشی",
            "steps_heading": "چک‌لیست پیش از انتخاب محصول",
            "steps": "ابتدا هدف یادگیری مرتبط با {topic} را مشخص کنید؛ سپس شواهد کیفیت، امکان بازبینی نمونه، منابع و مراجع، حق استفاده، فرمت فایل، پشتیبانی و شرایط بازگشت وجه را ارزیابی کنید. فقط محصول دارای صفحهٔ معتبر و فرایند تحویل قابل‌تأیید باید قابل خرید باشد.",
            "example_heading": "مثال اقتصادی آموزشی",
            "example": "در یک مثال کاملاً فرضی، ۱۰ فروش با قیمت ۱۵ واحد، درآمد ناخالص ۱۵۰ واحد ایجاد می‌کند. اگر هزینهٔ متغیر تحویل هر سفارش ۲ واحد باشد، حاشیهٔ مشارکت پیش از کارمزد، مالیات و هزینهٔ ثابت برابر ۱۳۰ واحد است. این ارقام قیمت، موجودی یا فروش واقعی هیچ محصولی نیستند.",
        },
    },
    "en": {
        "signals": {
            "intro": "A practical guide to {topic}: document data sources, time horizons, uncertainty and base, upside and downside scenarios. This is educational analysis, not a live trade signal.",
            "section_label": "Market analysis worksheet",
            "steps_heading": "Four-step decision worksheet",
            "steps": "1. Define a measurable economic question. 2. Record the source, date and reliability of each dataset. 3. Build three explicit scenarios. 4. Record risk limits, uncertainty and review triggers. Apply each step to {topic}; do not treat scenarios as forecasts of guaranteed returns.",
            "example_heading": "Illustrative arithmetic, not trade advice",
            "example": "With hypothetical capital of 1,000 units, a 1% loss budget is 10 units. At an assumed 2% stop distance, the nominal position size would be 10 / 0.02 = 500 units. Fees, slippage, gaps and liquidity can increase losses. No asset, trade or expected return is recommended.",
        },
        "store": {
            "intro": "A practical buyer's guide for learning resources on {topic}: verify sample content, authorship, revision date, license, download delivery and support before any purchase. No paid listing is activated by this page.",
            "section_label": "Digital learning resource evaluation",
            "steps_heading": "Before-you-buy checklist",
            "steps": "Define your learning outcome for {topic}. Examine an accessible sample, methodology and references; then verify license scope, file format, support terms, refund policy and delivery evidence. Only actual published products with working fulfillment should expose checkout.",
            "example_heading": "Educational unit-economics example",
            "example": "In a purely hypothetical scenario, 10 orders priced at 15 units yield gross sales of 150 units. With 2 units of variable fulfillment cost per order, contribution before fees, taxes and fixed costs is 130 units. These are not real inventory, pricing, orders or revenue.",
        },
    },
    "ar": {
        "signals": {
            "intro": "دليل تطبيقي عن {topic}: توثيق مصادر البيانات والفترة الزمنية وعدم اليقين وبناء سيناريو أساسي وآخر متفائل وثالث متحفظ. هذه مادة تعليمية وليست إشارة تداول مباشرة.",
            "section_label": "ورقة عمل تعليمية لتحليل السوق",
            "steps_heading": "أربع خطوات لاتخاذ قرار موثق",
            "steps": "١. صياغة سؤال اقتصادي قابل للقياس. ٢. تسجيل المصدر والتاريخ وموثوقية البيانات. ٣. بناء ثلاثة سيناريوهات بفرضيات واضحة. ٤. توثيق حدود المخاطر وعدم اليقين ومؤشرات المراجعة. تطبق الخطوات على {topic} دون ادعاء عائد مضمون.",
            "example_heading": "حساب توضيحي وليس توصية تداول",
            "example": "في مثال افتراضي، رأس مال مقداره ١٬٠٠٠ وحدة مع ميزانية خسارة ١٪ يساوي ١٠ وحدات. إذا كانت مسافة الوقف المفترضة ٢٪، فالحجم الاسمي هو ١٠ ÷ ٠٫٠٢ = ٥٠٠ وحدة. قد تزيد الرسوم والانزلاق والفجوات وضعف السيولة الخسارة. لا يُقترح أصل أو صفقة.",
        },
        "store": {
            "intro": "دليل لتقييم الموارد التعليمية حول {topic}: تحقق من العينة ومؤهلات المؤلف وتاريخ التحديث والترخيص والتسليم والدعم قبل الشراء. لا توجد في هذه الصفحة قائمة بيع مفعلة.",
            "section_label": "تقييم الموارد التعليمية الرقمية",
            "steps_heading": "قائمة تحقق قبل اختيار المنتج",
            "steps": "حدد هدف التعلم المتعلق بـ {topic}، وراجع العينة والمنهج والمراجع ثم حقوق الاستخدام وصيغة الملف وشروط الدعم والاسترداد وإثبات التسليم. لا يجوز عرض الدفع إلا لمنتج منشور فعلاً وله تسليم موثوق.",
            "example_heading": "مثال تعليمي لاقتصاديات الوحدة",
            "example": "في سيناريو افتراضي تماماً، تحقق ١٠ طلبات بسعر ١٥ وحدة مبيعات إجمالية ١٥٠ وحدة. ومع تكلفة تسليم متغيرة مقدارها وحدتان لكل طلب، يبلغ هامش المساهمة قبل الرسوم والضرائب والتكاليف الثابتة ١٣٠ وحدة. هذه ليست أسعاراً أو طلبات أو إيرادات حقيقية.",
        },
    },
}

def guide_for(slug: str, locale: str, kind: str) -> dict:
    """Return unique, localized, immutable-by-caller content for one page."""
    if slug not in BRAND_TOPICS or locale not in LOCALES or kind not in KINDS:
        raise ValueError("Unknown finance102 brand, locale or page kind")
    topic = BRAND_TOPICS[slug][LOCALES[locale]]
    rendered = {k: v.replace("{topic}", topic) for k, v in TEXT[locale][kind].items()}
    rendered["example"] += " " + BRAND_CASES[slug][LOCALES[locale]]
    return rendered

def compose_page_copy(slug: str, locale: str, kind: str, original_notice: str) -> tuple:
    """Render full educational copy inside the existing template's text slots.

    No new sections, template edits, payment widgets, or HTML are introduced.
    The original noncommercial disclosure stays at the beginning of the notice.
    """
    if not isinstance(original_notice, str) or not original_notice.strip():
        raise ValueError("Empty existing disclaimer")
    guide = guide_for(slug, locale, kind)
    notice = (
        original_notice.strip() + " "
        + guide["steps_heading"] + ": " + guide["steps"] + " "
        + guide["example_heading"] + ": " + guide["example"]
    )
    return guide["intro"], notice

ROUTE_KIND = {"signals": "market-signals", "store": "digital-products"}

def canonical_url(slug: str, locale: str, kind: str) -> str:
    """Fixed allowlisted production canonical; never echo arbitrary Host headers."""
    if slug not in BRAND_TOPICS or locale not in LOCALES or kind not in ROUTE_KIND:
        raise ValueError("Unknown brand, locale or finance route")
    domain = "zomorodmelal.ir" if locale == "fa" else "mojplaywin.com"
    prefix = "/ar" if locale == "ar" else ""
    return "https://" + domain + prefix + "/" + slug + "/" + ROUTE_KIND[kind] + "/"
