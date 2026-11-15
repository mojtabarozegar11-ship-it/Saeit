"""Mojtaba.bot.ai canonical signal interest intake across 17 brand mirrors.

Does not generate financial signals, sell subscriptions, charge wallets or send mail.
"""
import hashlib
import hmac

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import Http404, HttpResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from .signal_interest_policy import CANONICAL_AGENT, SIGNAL_BRANDS, SUPPORTED_LOCALES, SIGNAL_PLAN_CODES
from .signal_interest_models import SignalInterest

ALLOWED_HOSTS = frozenset((
    "mojplaywin.com", "www.mojplaywin.com", "zomorodmelal.ir", "www.zomorodmelal.ir",
))
ALLOWED_SKUS = frozenset(SIGNAL_PLAN_CODES)
EXPECTED_FIELDS = frozenset((
    "email", "brand", "plan_code", "source_language",
    "contact_consent", "consent_version",
))
SUCCESS = {
    "en": "Your interest in Mojtaba.bot.ai signals was recorded. No subscription, invoice or payment was created.",
    "fa": "درخواست اطلاع‌رسانی درباره سیگنال‌های mojtaba.bot.ai ثبت شد. هیچ اشتراک، فاکتور یا پرداختی ایجاد نشده است.",
    "ar": "تم تسجيل طلب المعلومات عن إشارات mojtaba.bot.ai. لم يتم إنشاء اشتراك أو فاتورة أو دفعة.",
}


def _host(request):
    host = request.get_host().split(":")[0].lower()
    if host not in ALLOWED_HOSTS or not request.is_secure():
        raise Http404("Signal intake requires an authorized HTTPS merchant")
    return host


@never_cache
@csrf_protect
@require_POST
def signal_interest(request):
    """Real DB write after explicit consent, but never paid activation."""
    host = _host(request)
    try:
        length = int(request.META.get("CONTENT_LENGTH", "0"))
    except (TypeError, ValueError):
        return HttpResponse("Invalid request", status=400)
    if request.content_type != "application/x-www-form-urlencoded" or not 0 < length <= 4096:
        return HttpResponse("Invalid form", status=400)
    if set(request.POST) != EXPECTED_FIELDS | {"csrfmiddlewaretoken"}:
        return HttpResponse("Unexpected form fields", status=400)
    if any(len(request.POST.getlist(k)) != 1 for k in EXPECTED_FIELDS):
        return HttpResponse("Duplicate form fields", status=400)

    brand = request.POST["brand"]
    sku = request.POST["plan_code"]
    language = request.POST["source_language"]
    if (brand not in SIGNAL_BRANDS or sku not in ALLOWED_SKUS
            or language not in SUPPORTED_LOCALES
            or request.POST["contact_consent"] != "yes"
            or request.POST["consent_version"] != "mojtaba-signals-interest-v1"):
        return HttpResponse("Invalid plan or consent", status=400)
    raw = request.POST["email"]
    if not isinstance(raw, str) or not raw or len(raw) > 254 or raw != raw.strip():
        return HttpResponse("Invalid email", status=400)
    email = raw.lower()
    try:
        validate_email(email)
    except ValidationError:
        return HttpResponse("Invalid email", status=400)
    ip = request.META.get("REMOTE_ADDR", "")
    if type(ip) is not str or not 1 <= len(ip) <= 80:
        return HttpResponse("Not available", status=503)
    digest = hmac.new(
        str(settings.SECRET_KEY).encode(),
        ("signals-v1:" + ip).encode(), hashlib.sha256,
    ).hexdigest()
    bucket = "mojtaba:signals:interest:" + digest
    try:
        if not cache.add(bucket, 1, timeout=3600) and cache.incr(bucket) > 8:
            return HttpResponse("Too many requests", status=429)
    except Exception:
        return HttpResponse("Not available", status=503)

    with transaction.atomic():
        SignalInterest.objects.get_or_create(
            email=email, brand=brand, plan_code=sku,
            defaults={
                "source_host": host,
                "source_language": language,
                "consent_version": "mojtaba-signals-interest-v1",
            },
        )
    response = HttpResponse(SUCCESS[language], status=202,
                            content_type="text/plain; charset=utf-8")
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Referrer-Policy"] = "same-origin"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response
