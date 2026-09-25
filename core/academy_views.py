
from django.shortcuts import render


def academy(request):
    courses = [
        {"title": "کشاورزی هوشمند", "meta": "RESEARCH · FIELD", "text": "از داده و دانش فنی تا تصمیم‌گیری در مزرعه."},
        {"title": "زنجیره ارزش", "meta": "BUSINESS · VALUE", "text": "طراحی زنجیره محصول از تولید تا بازار."},
        {"title": "هوش مصنوعی و عامل‌ها", "meta": "AI · AGENTS", "text": "مبانی Agent، Governance و اجرای قابل حسابرسی."},
    ]
    return render(request, "core/academy.html", {"courses": courses})
