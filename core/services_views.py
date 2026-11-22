from django.shortcuts import render

def services(request):
    items = [
        {"no": "01", "title": "دامپروری", "meta": "LIVESTOCK · FARM", "text": "راهنمای موضوعی برای برنامه‌ریزی، بهره‌وری و سلامت واحدهای دامداری.", "url": "/agriculture/livestock/"},
        {"no": "02", "title": "باغبانی و گلخانه", "meta": "HORTICULTURE · GREENHOUSE", "text": "مدیریت باغ، گلخانه، تولید محصولات و مراقبت از گیاهان.", "url": "/agriculture/horticulture/"},
        {"no": "03", "title": "طیور و آبزیان", "meta": "POULTRY · AQUACULTURE", "text": "راهنمای پرورش طیور و آبزیان و مدیریت واحدهای تولیدی.", "url": "/agriculture/poultry/"},
        {"no": "04", "title": "نهاده، بذر و کود", "meta": "INPUTS · SEEDS · FERTILIZERS", "text": "شناخت نهاده‌های کشاورزی و مسیرهای تهیه بذر و کود.", "url": "/agriculture/inputs/"},
        {"no": "05", "title": "سموم و خدمات کشاورزی", "meta": "CROP PROTECTION · SERVICES", "text": "اطلاعات ایمن و راهنمای دسترسی به ادارات و خدمات کشاورزی.", "url": "/agriculture/pesticides/"},
    ]
    # These exact public cPanel service-scopes already exist. This is an
    # additive Django discovery route only; it does not publish a static index.
    scopes = (
        ("AGR-01", "تحلیل اقتصاد و سودآوری مزرعه", "بررسی هزینه تولید، حاشیه مشارکت و سناریوهای اقتصادی"),
        ("RS-01", "ممیزی شاخص‌های پژوهش کشاورزی", "ماتریس شاخص، داده و شواهد موردنیاز طرح"),
        ("RS-02", "ممیزی سناریوی آبیاری", "ارزیابی محدودیت داده، مصرف آب و هزینه سناریوها"),
        ("RS-03", "طراحی آزمایش و بررسی اقتصادی تحقیق", "تعریف پرسش، آزمایش و شاخص‌های مالی پژوهش"),
        ("WEB-01", "طراحی مسیر درخواست و فروش کسب‌وکار", "بررسی مسیر استعلام، پیگیری و تبدیل"),
        ("SEO-01", "ممیزی فنی و محتوایی سئو", "ممیزی ساختار و قابلیت کشف محتوا، بدون تضمین رتبه"),
    )
    if request.get_host().split(":")[0].lower() in {"mojplaywin.com", "www.mojplaywin.com"}:
        from .mojplaywin_views import home
        return home(request)
    return render(request, "core/services.html", {"items": items, "scope_offers": scopes})
