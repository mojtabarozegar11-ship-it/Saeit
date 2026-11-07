"""Localized financial education, analysis, and digital-store landing pages.

No live prices, investment advice, performance claims, or purchasable items are
fabricated here. Pages only describe the service and link to the existing shop.
"""
from django.shortcuts import render

BRANDS = [
    ("saman", "سمن", "SAMAN", "سمن"),
    ("zahra", "زهرا", "ZAHRA", "زهرة"),
    ("zhila", "ژیلا", "ZHILA", "جيلا"),
    ("marzieh", "مرضیه", "MARZIEH", "مرضية"),
    ("maryam", "مریم", "MARYAM", "مريم"),
    ("marjan", "مرجان", "MARJAN", "مرجان"),
    ("faremah", "فریماه", "FAREMAH", "فريماه"),
    ("farnaz", "فرناز", "FARNAZ", "فرناز"),
    ("taniya", "تانیا", "TANIYA", "تانيا"),
    ("raham", "رهام", "RAHAM", "رهام"),
    ("mojtaba", "مجتبی", "MOJTABA", "مجتبى"),
    ("mohammad", "محمد", "MOHAMMAD", "محمد"),
    ("mostafa", "مصطفی", "MOSTAFA", "مصطفى"),
    ("17", "۱۷", "17", "١٧"),
    ("21", "۲۱", "21", "٢١"),
    ("206", "۲۰۶", "206", "٢٠٦"),
    ("108", "۱۰۸", "108", "١٠٨"),
]
PALETTES = [
    ("emerald", "#0b322b", "#c9a65a"), ("amethyst", "#2b173c", "#dfbd7a"),
    ("sapphire", "#112947", "#d7b56d"), ("rose", "#472233", "#e0ba83"),
    ("midnight", "#161e37", "#d6b765"), ("jade", "#123c36", "#d5bf80"),
    ("plum", "#341b34", "#d4ad65"), ("copper", "#432c23", "#e0b76d"),
    ("teal", "#153c43", "#d9bd78"), ("indigo", "#20254b", "#cbb477"),
    ("onyx", "#181818", "#d2ae63"), ("ruby", "#451f2a", "#dbb775"),
    ("bronze", "#3a2b1c", "#ddbd7c"), ("silver", "#252d34", "#d8c893"),
    ("ocean", "#143146", "#d2b16a"), ("orchid", "#392347", "#dfbd79"),
    ("champagne", "#352a22", "#dfc783"),
]
COPY = {
 "fa": {
  "signals_title":"تحلیل بازار و آموزش تصمیم‌گیری",
  "signals_intro":"مرور ساختارمند بازارهای مالی، سناریوها و مدیریت ریسک؛ با توضیح روشنِ فرض‌ها و محدودیت‌ها.",
  "signals_notice":"در این صفحه هنوز سیگنال زنده یا سابقهٔ عملکردِ راستی‌آزمایی‌شده منتشر نشده است. هیچ بازده یا سودی تضمین نمی‌شود.",
  "store_title":"فروشگاه محصولات دیجیتال",
  "store_intro":"راهنماها، قالب‌ها و محتوای آموزشی دیجیتال با توضیح روشن دربارهٔ محتوا و شرایط استفاده.",
  "store_notice":"فهرست محصولات و پرداخت این زیردسته هنوز فعال نشده است؛ موجودی، قیمت یا لینک خریدِ ساختگی نمایش داده نمی‌شود.",
  "cta":"بازگشت به فروشگاه اصلی", "disclaimer":"محتوا آموزشی و اطلاع‌رسانی است و توصیهٔ شخصی سرمایه‌گذاری، پیشنهاد خریدوفروش یا تضمین نتیجه محسوب نمی‌شود.",
  "pill":"تحلیل شفاف · آموزش کاربردی"
 },
 "en": {
  "signals_title":"Market analysis and decision education",
  "signals_intro":"Structured market context, scenarios, and risk management, with assumptions and limitations stated clearly.",
  "signals_notice":"No live signal or independently verified performance history is published on this page yet. Returns and profits are never guaranteed.",
  "store_title":"Digital products shop",
  "store_intro":"Digital guides, templates, and learning materials with clear descriptions and usage terms.",
  "store_notice":"This sub-store's product listing and checkout are not active yet. No fictional stock, prices, or purchase links are shown.",
  "cta":"Visit the main shop", "disclaimer":"For education and information only. This is not personalized investment advice or a recommendation to buy or sell, and no outcome is guaranteed.",
  "pill":"Clear analysis · Practical learning"
 },
 "ar": {
  "signals_title":"تحليل الأسواق وتعليم اتخاذ القرار",
  "signals_intro":"عرض منظم للسوق والسيناريوهات وإدارة المخاطر، مع توضيح الافتراضات والقيود.",
  "signals_notice":"لا تُنشر هنا حالياً إشارات مباشرة أو نتائج أداء موثقة مستقلة. لا نضمن أي عائد أو ربح.",
  "store_title":"متجر المنتجات الرقمية",
  "store_intro":"أدلة وقوالب ومواد تعليمية رقمية مع وصف واضح للمحتوى وشروط الاستخدام.",
  "store_notice":"قائمة المنتجات والدفع لهذا المتجر الفرعي غير مفعّلين بعد. لن نعرض مخزوناً أو أسعاراً أو روابط شراء وهمية.",
  "cta":"زيارة المتجر الرئيسي", "disclaimer":"للتعليم والمعلومات فقط. لا يُعد ذلك نصيحة استثمارية شخصية أو توصية بالشراء أو البيع، ولا نضمن النتائج.",
  "pill":"تحليل واضح · تعلم عملي"
 }
}

def financial_brand_page(request, brand, locale, page_type):
    match = next((item for item in BRANDS if item[0] == brand), None)
    if locale == "host":
        forwarded = request.META.get("HTTP_X_FORWARDED_HOST") or request.META.get("HTTP_HOST") or ""
        host = forwarded.split(",")[0].split(":")[0].strip().lower().removeprefix("www.")
        locale = "fa" if "zomorodmelal.ir" in host else "en"
    if locale not in COPY:
        locale = "en"
    if match is None or page_type not in {"signals", "store"}:
        from django.http import Http404
        raise Http404
    slug, fa_name, en_name, ar_name = match
    name = {"fa": fa_name, "en": en_name, "ar": ar_name}[locale]
    copy = COPY[locale]
    title = copy["signals_title"] if page_type == "signals" else copy["store_title"]
    intro = copy["signals_intro"] if page_type == "signals" else copy["store_intro"]
    notice = copy["signals_notice"] if page_type == "signals" else copy["store_notice"]
    palette = PALETTES[next(i for i, item in enumerate(BRANDS) if item[0] == slug)]
    shop_url = "/store/" if locale == "fa" else "/commerce/"
    return render(request, "core/financial_brand_page.html", {
        "brand_name": name, "brand_slug": slug, "locale": locale,
        "page_type": page_type, "page_title": title, "page_intro": intro,
        "page_notice": notice, "copy": copy, "shop_url": shop_url,
        "page_palette": palette, "page_direction": "rtl" if locale in {"fa", "ar"} else "ltr",
    })
