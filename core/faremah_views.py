from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import render
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
    return render(request, "core/faremah.html", {"submitted": submitted})
