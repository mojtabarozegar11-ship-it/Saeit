"""Six sellable, evidence-limited service scope pages on the company domain.

GET only. Uses the existing one-source intake router; no shadow lead form,
customer record, outbound message, quote, invoice, gateway or spend.
"""
from __future__ import annotations

import json

from django.http import Http404
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from .service_lead_views import _host_allowed
from .service_intake_routing import service_contact_card
from .service_sales_controls import SERVICE_CARDS, service_card


SCOPE_GUIDES = {
    "AGR-01": {
        "pain": "تصمیم‌گیری درباره محصول، سطح تولید، هزینه‌های مزرعه و سودآوری به داده و محاسبه قابل بازبینی نیاز دارد.",
        "questions": (
            "کدام محصول یا سناریو با فرض هزینه و عملکرد واقعی مناسب‌تر است؟",
            "قیمت فروش و نقطه سربه‌سر در شرایط مختلف چقدر تغییر می‌کند؟",
            "کدام هزینه و ریسک بیشترین اثر را بر تصمیم تولید دارد؟",
        ),
        "intake": (
            "فهرست محصولات، سطح کشت و دوره بررسی",
            "هزینه‌های متغیر و ثابت با تاریخ و واحد",
            "عملکرد و قیمت فروش ثبت‌شده یا فرضیات مشخص",
        ),
        "acceptance": "جدول ورودی‌های مستند، سناریوهای مقایسه‌پذیر و محدودیت اعتبار نتیجه",
    },
    "RS-01": {
        "pain": "ادعای پژوهشی بدون زنجیره شفاف داده، شاخص، منبع و روش محاسبه قابل اتکا نیست؛ ممیزی شواهد، نقاط ضعف استدلال را روشن می‌کند.",
        "questions": (
            "کدام شاخص‌ها تعریف، واحد یا منشأ داده نامشخص دارند؟",
            "چه ادعاهایی با شواهد در دسترس سازگار یا ناسازگارند؟",
            "برای بازتولید محاسبات چه اسناد و فرض‌هایی کم است؟",
        ),
        "intake": (
            "داده و شاخص‌ها با مجوز بررسی",
            "فهرست ادعاها، روش و منابع ارجاع",
            "واحدها، دوره مشاهده و حدود انتشار اطلاعات",
        ),
        "acceptance": "ماتریس ادعا و شاهد، کنترل واحدها و فهرست نواقص قابل اقدام",
    },
    "RS-02": {
        "pain": "برآورد مصرف آب و مقایسه برنامه‌های آبیاری بدون کنترل داده، خطای سنسور و فرضیات گمراه‌کننده می‌شود.",
        "questions": (
            "آیا مقدارهای ورودی آب و سطح در واحدهای سازگار ثبت شده‌اند؟",
            "سناریوهای مختلف آبیاری با چه فرض‌هایی مقایسه می‌شوند؟",
            "خطای داده و سنسور چه اثری روی نتیجه دارد؟",
        ),
        "intake": (
            "سطح و محصول، منبع آب و دوره کشت",
            "داده سنسور یا آبیاری و مشخصات کالیبراسیون در صورت وجود",
            "فرضیات خاک، هوا، بهره‌برداری و محدودیت‌ها",
        ),
        "acceptance": "موازنه و مقایسه سناریو، حساسیت خطای داده و شروط اجرای میدانی",
    },
    "RS-03": {
        "pain": "طرح آزمایش بدون تکرار، تصادفی‌سازی و سنجش هزینه می‌تواند نتیجه‌ای غیرقابل دفاع بسازد.",
        "questions": (
            "تعداد تیمار، تکرار، بلوک و متغیر پیامد چگونه تعیین شود؟",
            "خطا و سوگیری اجرا از کجا ایجاد می‌شود؟",
            "هزینه گردآوری داده و تحلیل در چه بخش‌هایی قرار دارد؟",
        ),
        "intake": (
            "سؤال پژوهش، تیمارها و محدودیت‌های عملیاتی",
            "ظرفیت نمونه، دوره آزمایش و امکانات موجود",
            "متغیرهای پیامد و حدود مجوز استفاده از داده",
        ),
        "acceptance": "پروتکل، برنامه تخصیص، معیار کیفیت داده و چارچوب تحلیل",
    },
    "WEB-01": {
        "pain": "وجود یک وب‌سایت به معنی دریافت درخواست واقعی، ثبت قابل پیگیری یا فروش نیست.",
        "questions": (
            "بازدیدکننده دقیقاً از چه مسیری درخواست خدمت ثبت می‌کند؟",
            "آیا رضایت، فرم، CRM و پیگیری بدون ثبت دوباره به هم وصل هستند؟",
            "کدام رخدادها واقعاً نشان‌دهنده درخواست، پاسخ و فروش‌اند؟",
        ),
        "intake": (
            "دامنه و سطح دسترسی مجاز مالک",
            "شرح خدمات، بازار هدف و نشانی تماس قابل انتشار",
            "مسیر کنونی درخواست، ابزار تحویل و شواهد آماری مجاز",
        ),
        "acceptance": "نقشه قیف، فرم امن، تحویل قابل پیگیری و شاخص‌های تفکیک‌شده",
    },
    "SEO-01": {
        "pain": "بهبود رتبه فنی زمانی ارزشمند است که مسائل واقعی دسترسی، محتوای خدمت و تبدیل مشتری روشن باشند.",
        "questions": (
            "آیا صفحات تجاری در جست‌وجو قابل یافتن و در موبایل قابل استفاده‌اند؟",
            "چه خطاهای فنی مانع خزش، نمایه‌سازی یا درخواست مشتری می‌شوند؟",
            "کدام اقدام با داده قابل‌اندازه‌گیری در اولویت است؟",
        ),
        "intake": (
            "نشانی دامنه و مجوز ممیزی آن",
            "بازار و خدمات هدف، زبان‌ها و محتوای موجود",
            "داده جست‌وجو و تحلیل ترافیک در صورت اختیار قانونی",
        ),
        "acceptance": "فهرست نواقص مستند، اولویت اصلاح و تعریف معیار پایش",
    },
}


@require_GET
def service_scope_page(request, service_code):
    if not _host_allowed(request):
        raise Http404("Company service belongs to Zomorod Melal")
    if not isinstance(service_code, str) or service_code not in SERVICE_CARDS:
        raise Http404("Unknown service")
    offer = service_card(service_code)
    contact = service_contact_card(service_code)
    guide = SCOPE_GUIDES[service_code]

    structured = {
        "@context": "https://schema.org",
        "@type": "Service",
        "name": offer["title_fa"],
        "serviceType": offer["title_fa"],
        "url": "https://zomorodmelal.ir" + reverse(
            "service_scope_page", args=[service_code]
        ),
        "provider": {
            "@type": "Organization",
            "name": "شرکت کشت و صنعت زمرد ملل",
            "url": "https://zomorodmelal.ir/",
        },
        "areaServed": {"@type": "Country", "name": "ایران"},
        "description": guide["pain"],
    }
    # All values are curated first-party constants or exact validated codes.
    # JSON inside a script must never contain literal tag breakers.
    schema_json = json.dumps(structured, ensure_ascii=False).replace(
        "<", "\\u003c"
    ).replace(">", "\\u003e").replace("&", "\\u0026")
    response = render(
        request,
        "core/service_scope.html",
        {
            "offer": offer,
            "guide": guide,
            "contact": contact,
            "service_scope_code": service_code,
            "structured_data": schema_json,
            "canonical": structured["url"],
            "service_form_active": contact["intake_source"] == "django_company_inquiry_v1",
        },
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response
