"""MOJ PROP public Plan 1 information-request funnel. No checkout or trading."""
import hashlib
import hmac

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.utils.cache import patch_vary_headers
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from .signal_interest_models import CommercialInterest

HOSTS = frozenset(("mojplaywin.com", "www.mojplaywin.com"))
LOCALES = frozenset(("en", "fa", "ar", "de"))
SKU = "MOJ-PROP-01"
CONSENT = "moj-prop-interest-v1"
LANGUAGE = {
    "en": {
        "title": "MOJ PROP — Plan 1 information",
        "headline": "Request information about the MOJ PROP challenge",
        "description": "Plan 1: owner-declared starting capital of $100 and a proposed 30 TRX entry fee. Contact only: no purchase, invoice, funded promise or trading account.",
        "email": "Email for contact", "consent": "I agree that MojPlayWin may use this email solely to reply about MOJ PROP Plan 1.",
        "send": "Request Plan 1 details", "result": "Your Plan 1 contact request was recorded. No payment or enrollment occurred.",
    },
    "fa": {
        "title": "مج پراپ — اطلاعات پلن ۱",
        "headline": "درخواست اطلاعات چالش مج پراپ",
        "description": "پلن ۱ طبق اعلام مالک: سرمایه آغازین ۱۰۰ دلار و کارمزد پیشنهادی ۳۰ TRX. این فرم فقط درخواست اطلاعات است؛ خرید، فاکتور، تعهد سرمایه یا حساب معامله ایجاد نمی‌کند.",
        "email": "ایمیل تماس", "consent": "رضایت می‌دهم مج پلی وین فقط برای پاسخ به درخواست پلن ۱ از این ایمیل استفاده کند.",
        "send": "درخواست اطلاعات پلن ۱", "result": "درخواست اطلاعات پلن ۱ ثبت شد. هیچ پرداخت یا ثبت‌نامی انجام نشد.",
    },
    "ar": {
        "title": "MOJ PROP — معلومات الخطة الأولى",
        "headline": "طلب معلومات تحدي MOJ PROP",
        "description": "الخطة الأولى: رأس المال المعلن من المالك 100 دولار والرسوم المقترحة 30 TRX. طلب معلومات فقط، وليس شراءً أو فاتورة أو حساب تداول.",
        "email": "البريد الإلكتروني", "consent": "أوافق على استخدام بريدي الإلكتروني للرد على هذا الطلب فقط.",
        "send": "طلب التفاصيل", "result": "تم تسجيل طلب المعلومات. لم يحدث دفع أو تسجيل.",
    },
    "de": {
        "title": "MOJ PROP — Informationen zu Plan 1",
        "headline": "MOJ PROP: Informationen zu Plan 1 anfordern",
        "description": "Plan 1: vom Eigentümer gemeldetes Startkapital von 100 USD, vorgeschlagene Gebühr von 30 TRX. Nur Kontaktanfrage, keine Zahlung, Rechnung oder Kontoeröffnung.",
        "email": "Kontakt-E-Mail", "consent": "Ich stimme zu, dass MojPlayWin meine E-Mail nur für diese Anfrage nutzt.",
        "send": "Informationen anfordern", "result": "Die Anfrage wurde erfasst. Keine Zahlung oder Registrierung.",
    },
}


def _authorized_host(request):
    try:
        host = request.get_host().split(":")[0].lower()
    except Exception:
        raise Http404("Unknown merchant host") from None
    if host not in HOSTS or not request.is_secure():
        raise Http404("MOJ PROP requires a MojPlayWin HTTPS origin")
    return host


@never_cache
@require_GET
def moj_prop_public(request, lang="en"):
    _authorized_host(request)
    if lang not in LOCALES:
        raise Http404("Unsupported language")
    response = render(request, "core/moj_prop_public.html", {
        "locale": lang, "copy": LANGUAGE[lang],
        "direction": "rtl" if lang in ("fa", "ar") else "ltr",
    })
    patch_vary_headers(response, ("Cookie",))
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Referrer-Policy"] = "same-origin"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


@never_cache
@csrf_protect
@require_POST
def moj_prop_public_interest(request):
    host = _authorized_host(request)
    try:
        length = int(request.META.get("CONTENT_LENGTH", "0"))
    except (TypeError, ValueError):
        return HttpResponse("Invalid form", status=400)
    if request.content_type != "application/x-www-form-urlencoded" or not 0 < length <= 4096:
        return HttpResponse("Invalid form", status=400)
    required = frozenset(("email", "plan_code", "source_language",
                          "contact_consent", "consent_version"))
    if set(request.POST) != required | {"csrfmiddlewaretoken"}:
        return HttpResponse("Unexpected form fields", status=400)
    if any(len(request.POST.getlist(field)) != 1 for field in required):
        return HttpResponse("Duplicate form fields", status=400)
    if (request.POST["plan_code"] != SKU
            or request.POST["contact_consent"] != "yes"
            or request.POST["consent_version"] != CONSENT
            or request.POST["source_language"] not in LOCALES):
        return HttpResponse("Plan 1 and explicit contact consent required", status=400)
    language = request.POST["source_language"]
    raw = request.POST["email"]
    if type(raw) is not str or not 1 <= len(raw) <= 254 or raw != raw.strip():
        return HttpResponse("Invalid email", status=400)
    email = raw.lower()
    try:
        validate_email(email)
    except ValidationError:
        return HttpResponse("Invalid email", status=400)
    ip = request.META.get("REMOTE_ADDR", "")
    if type(ip) is not str or not 1 <= len(ip) <= 80:
        return HttpResponse("Request unavailable", status=503)
    key = "moj-prop:lead:public:v1:" + hmac.new(
        str(settings.SECRET_KEY).encode(),
        ("moj-prop-intake:" + ip).encode(), hashlib.sha256
    ).hexdigest()
    try:
        if not cache.add(key, 1, timeout=3600) and cache.incr(key) > 8:
            return HttpResponse("Too many requests", status=429)
    except Exception:
        return HttpResponse("Request unavailable", status=503)
    with transaction.atomic():
        CommercialInterest.objects.get_or_create(
            email=email, offer_family="moj_prop", brand="moj_prop", plan_code=SKU,
            defaults={"source_host": host, "source_language": language,
                      "consent_version": CONSENT},
        )
    response = HttpResponse(LANGUAGE[language]["result"], status=202,
                            content_type="text/plain; charset=utf-8")
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Referrer-Policy"] = "same-origin"
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["X-Content-Type-Options"] = "nosniff"
    return response
