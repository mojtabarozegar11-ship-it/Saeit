from django.shortcuts import render

def services(request):
    items = [
        {"no": "01", "title": "زنجیره ارزش", "meta": "VALUE · OPERATIONS", "text": "طراحی مسیر محصول از تولید و فرآوری تا بسته‌بندی، بازار و فروش.", "url": "/company/"},
        {"no": "02", "title": "هوش مصنوعی", "meta": "AI · AGENTS", "text": "عامل‌های تخصصی، گردش‌کارهای قابل حسابرسی و اتوماسیون تصمیم‌یار.", "url": "/agents/"},
        {"no": "03", "title": "آموزش", "meta": "EDUCATION · SKILLS", "text": "مسیرهای آموزشی کاربردی برای دانش، کسب‌وکار، فناوری و عملیات.", "url": "/education/"},
        {"no": "04", "title": "بازار و محصولات", "meta": "MARKET · COMMERCE", "text": "معرفی، عرضه و اتصال خدمات و محصولات به مسیرهای بازار.", "url": "/market/"},
        {"no": "05", "title": "دانش و محتوا", "meta": "KNOWLEDGE · MEDIA", "text": "تبدیل دانش تخصصی به مقاله، مرجع، محتوای آموزشی و رسانه.", "url": "/knowledge/"},
    ]
    return render(request, "core/services.html", {"items": items})
