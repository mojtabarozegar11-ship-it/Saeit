from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib import messages

def faremah_home(request):
    submitted = False
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        phone = request.POST.get("phone", "").strip()
        service = request.POST.get("service", "").strip()
        if not name or not phone:
            messages.error(request, "نام و شماره تماس را وارد کنید.")
        else:
            subject = f"درخواست جدید فره‌ماه — {service or 'مشاوره'}"
            body = f"نام: {name}\nتلفن: {phone}\nخدمت: {service or 'مشاوره'}\nپیام: {request.POST.get('message','').strip()}"
            destination = getattr(settings, "COMPANY_TRADE_EMAIL", "")
            sender = getattr(settings, "DEFAULT_FROM_EMAIL", "")
            if destination and sender:
                send_mail(subject, body, sender, [destination], fail_silently=True)
            submitted = True
            messages.success(request, "درخواست شما ثبت شد؛ کارشناسان فره‌ماه برای هماهنگی تماس می‌گیرند.")
    try:
        return render(request, "core/faremah.html", {"submitted": submitted})
    except Exception:
        # Keep the public subsite available even if a host has a stale template cache.
        return HttpResponse("""<!doctype html><html lang="fa" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>فره‌ماه | لیزر و زیبایی</title><style>body{font-family:Tahoma,Arial;max-width:760px;margin:0 auto;padding:28px;line-height:2;background:#fffaf7;color:#211a2e}a,button{background:#211a2e;color:white;border:0;border-radius:12px;padding:12px 18px;text-decoration:none;font:inherit}section{padding:28px 0}input,textarea{display:block;width:100%;padding:12px;margin:8px 0;border:1px solid #eadfe4;border-radius:10px;font:inherit}</style><h1>فره‌ماه</h1><p>مرکز لیزر و زیبایی در شیراز؛ مشاوره شفاف و برنامه مراقبت اختصاصی.</p><section><h2>خدمات</h2><p>لیزر موهای زائد · مراقبت پوست · مشاوره اختصاصی</p></section><section><h2>درخواست مشاوره</h2><form method="post">{% csrf_token %}<input name="name" placeholder="نام و نام خانوادگی" required><input name="phone" placeholder="شماره تماس" required><textarea name="message" placeholder="توضیحات"></textarea><button>ثبت درخواست</button></form></section><p><a href="#top">بازگشت به بالا</a></p></html>""")
