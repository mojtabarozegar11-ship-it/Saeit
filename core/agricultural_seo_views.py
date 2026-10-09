"""Public, server-rendered agricultural SEO landing pages (Zomorod Melal only)."""
import json
from django.http import Http404, HttpResponse
from django.views.decorators.http import require_GET
from .brand import brand_for_request

PAGES = {
    "agricultural-services": ("شرکت خدمات کشاورزی", "خدمات کشاورزی، مشاوره و راهکارهای تخصصی", "آشنایی با حوزه‌های خدمات کشاورزی شرکت کشت و صنعت زمرد ملل؛ پژوهش، تحلیل، آموزش و راهکارهای هوشمند برای مزرعه و زنجیره تولید.", [
        ("تحلیل و برنامه‌ریزی", "بررسی داده‌های تولید، منابع، هزینه‌ها و گزینه‌های مدیریتی در پروژه‌های کشاورزی."),
        ("پژوهش و امکان‌سنجی", "مطالعه علمی و اقتصادی طرح‌های کشاورزی و ارزیابی ریسک و امکان اجرا."),
        ("فناوری و آموزش", "آشنایی با ابزارهای تصمیم‌یار، آموزش و فناوری‌های نوین کشاورزی.")]),
    "agro-industry": ("کشت و صنعت", "کشت و صنعت؛ از تولید تا بازار", "معرفی زنجیره کشت و صنعت، پژوهش، فرآوری و توسعه بازار در شرکت کشت و صنعت زمرد ملل.", [
        ("تولید", "برنامه‌ریزی زراعت، باغبانی و مدیریت منابع تولید."), ("فرآوری", "مطالعه زنجیره ارزش، فرآوری و بسته‌بندی."), ("بازار", "بررسی اقتصاد تولید و مسیرهای عرضه محصول.")]),
    "agricultural-company": ("شرکت کشاورزی", "شرکت کشاورزی و حوزه‌های فعالیت زمرد ملل", "آشنایی با شرکت کشت و صنعت زمرد ملل و حوزه‌های کشاورزی، تحقیق، خدمات و فناوری.", [
        ("کشاورزی", "حوزه‌های تولید و مدیریت زنجیره ارزش."), ("تحقیقات", "مطالعات و تحلیل‌های تخصصی."), ("خدمات", "مسیر آشنایی و درخواست همکاری در پروژه‌های کشاورزی.")]),
    "agricultural-research": ("شرکت تحقیقات کشاورزی", "تحقیقات کشاورزی و پژوهش‌های کاربردی", "پژوهش و تحلیل داده در اقتصاد، تولید و فناوری کشاورزی در چارچوب فعالیت‌های زمرد ملل.", [
        ("مسئله پژوهشی", "تعریف سؤال و فرضیه قابل بررسی."), ("شواهد", "گردآوری و ارزیابی منابع معتبر."), ("نتایج", "تحلیل یافته‌ها، محدودیت‌ها و امکان استفاده کاربردی.")]),
    "breeding": ("شرکت اصلاح نژاد", "اصلاح نژاد و ژنتیک در کشاورزی", "معرفی حوزه علمی اصلاح نژاد گیاهان و دام، ژنتیک و زیست‌فناوری؛ جزئیات خدمات اجرایی با استعلام از شرکت.", [
        ("اصلاح نباتات", "اصول انتخاب، صفات و بهبود ژنتیکی گیاهان."), ("اصلاح نژاد دام", "شاخص‌های ژنتیکی، رکوردگیری و مدیریت برنامه اصلاحی."), ("زیست‌فناوری", "بررسی روش‌های نوین و ملاحظات علمی و قانونی.")]),
    "agricultural-technology": ("شرکت فناوری کشاورزی", "فناوری کشاورزی و راهکارهای هوشمند", "فناوری‌های نوین، تحلیل داده و هوش مصنوعی در کشاورزی و دامپروری؛ معرفی زمینه‌های مطالعه و همکاری.", [
        ("کشاورزی هوشمند", "کاربرد داده‌های مزرعه و اقلیم در تصمیم‌گیری."), ("هوش مصنوعی", "ابزارهای تصمیم‌یار و محدودیت‌های آن‌ها."), ("فناوری تولید", "ارزیابی راهکارهای فنی و اقتصادی پیش از پیاده‌سازی.")]),
}

@require_GET
def agricultural_seo_page(request, slug):
    if brand_for_request(request):
        raise Http404()
    if slug not in PAGES:
        raise Http404()
    from html import escape
    keyword, heading, description, sections = PAGES[slug]
    canonical = f"https://zomorodmelal.ir/agricultural-topics/{slug}/"
    title = f"{keyword} | شرکت کشت و صنعت زمرد ملل"
    esc = lambda x: escape(x, quote=True)
    nav = '<a href="/">خانه</a> · <a href="/services/">خدمات</a> · <a href="/agriculture/">کشاورزی</a> · <a href="/company/">شرکت</a>'
    cards = "".join(f"<section><h2>{esc(h)}</h2><p>{esc(t)}</p></section>" for h,t in sections)
    related = "".join(f'<li><a href="/agricultural-topics/{esc(key)}/">{esc(item[0])}</a></li>' for key,item in PAGES.items() if key != slug)
    schema = {"@context":"https://schema.org","@type":"WebPage","name":title,"description":description,"url":canonical,"isPartOf":{"@type":"WebSite","name":"زمرد ملل","url":"https://zomorodmelal.ir/"},"about":{"@type":"Organization","name":"شرکت کشت و صنعت زمرد ملل","url":"https://zomorodmelal.ir/"}}
    schema_json = json.dumps(schema, ensure_ascii=False).replace("<", "\\u003c")
    body = f"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><meta name="description" content="{esc(description)}"><link rel="canonical" href="{esc(canonical)}"><script type="application/ld+json">{schema_json}</script><style>body{{margin:0;background:#f7f8f4;color:#19362c;font:17px/1.9 Tahoma,Arial,sans-serif}}header,main,footer{{max-width:950px;margin:auto;padding:22px}}header{{border-bottom:3px solid #a58b48}}a{{color:#205c46}}h1{{font-size:2rem;line-height:1.5}}section{{background:white;border:1px solid #d8dfd5;border-radius:12px;margin:18px 0;padding:16px 24px}}footer{{font-size:.85rem}}</style></head><body><header><strong>شرکت کشت و صنعت زمرد ملل</strong><nav aria-label="مسیرهای اصلی">{nav}</nav></header><main><h1>{esc(heading)}</h1><p>{esc(description)}</p>{cards}<section><h2>همکاری و اطلاعات بیشتر</h2><p>برای بررسی شرایط و دامنه خدمات قابل ارائه، از طریق <a href="/company/">صفحه شرکت</a> اقدام کنید. معرفی حوزه‌های علمی به‌معنای ارائه قطعی همه خدمات اجرایی نیست.</p></section><section><h2>موضوعات مرتبط</h2><ul>{related}</ul></section></main><footer>تمام حقوق مادی و معنوی سایت برای شرکت کشت و صنعت زمرد ملل محفوظ است. آبان ۱۳۹۸.</footer></body></html>"""
    return HttpResponse(body, content_type="text/html; charset=utf-8")
