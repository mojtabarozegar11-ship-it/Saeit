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
    return {k: v.replace("{topic}", topic) for k, v in TEXT[locale][kind].items()}
