"""Read-only MojPlayWin / Moj Prop landing page.

Never expose the page as the independent Zomorod Melal company's offer.
No customer registration, wallet payment, promise of funded eligibility, or trades.
"""
from django.http import Http404
from django.shortcuts import render

from prop_firm.moj_prop_page import page_context, SUPPORTED_CODES
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

INTEREST_COPY = {
    "en": ("Request Plan 1 information", "Email for this request",
           "I consent to MojPlayWin retaining this email to contact me about Plan 1 only.",
           "Submit contact request", "This form does not create an order, TRX invoice or trading account.",
           "Your Plan 1 contact request has been recorded. No payment or enrollment occurred."),
    "fa": ("درخواست اطلاعات پلن ۱", "ایمیل تماس",
           "رضایت می‌دهم مج پلی وین فقط برای پاسخ درباره پلن ۱ این ایمیل را نگهداری کند.",
           "ثبت درخواست تماس", "این فرم هیچ سفارش، فاکتور TRX یا حساب معاملاتی ایجاد نمی‌کند.",
           "درخواست اطلاعات پلن ۱ ثبت شد. هیچ پرداخت یا ثبت‌نامی انجام نشده است."),
    "ar": ("طلب معلومات الخطة الأولى", "البريد الإلكتروني",
           "أوافق على الاحتفاظ بالبريد للتواصل بشأن الخطة الأولى فقط.",
           "إرسال طلب التواصل", "هذا النموذج لا ينشئ طلب شراء أو فاتورة TRX أو حساب تداول.",
           "تم تسجيل طلب التواصل. لم يحدث دفع أو تسجيل."),
    "de": ("Informationen zu Plan 1 anfordern", "E-Mail für diese Anfrage",
           "Ich stimme zu, dass MojPlayWin mich ausschließlich zu Plan 1 kontaktiert.",
           "Kontaktanfrage senden", "Dieses Formular erstellt weder Rechnung noch Zahlung oder Handelskonto.",
           "Ihre Anfrage wurde gespeichert. Es gab keine Zahlung oder Anmeldung."),
}



def moj_prop_landing(request, lang="en"):
    host = request.get_host().split(":")[0].lower()
    if host not in {"mojplaywin.com", "www.mojplaywin.com"}:
        raise Http404("Moj Prop belongs to MojPlayWin")
    try:
        data = page_context(lang)
    except ValueError as error:
        raise Http404("Unsupported language") from error
    data["interest_copy"] = INTEREST_COPY.get(lang, INTEREST_COPY["en"])
    response = render(request, "mojplaywin/moj_prop.html", data)
    # The CSRF token is per browser; shared caching can leak or break it.
    from django.utils.cache import patch_vary_headers
    patch_vary_headers(response, ("Cookie",))
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Pragma"] = "no-cache"
    response["Referrer-Policy"] = "same-origin"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


def moj_prop_dashboard(request, lang="en"):
    """Authenticated, owner-scoped GET-only view; no self-registration/payment."""
    from django.http import HttpResponseNotAllowed
    from django.shortcuts import redirect
    from prop_firm.moj_prop_page import page_context
    from prop_firm.portal_i18n import labels_for
    from prop_firm.models import PropTrader, PropAccount
    from prop_firm.portal import account_projection

    host = request.get_host().split(":")[0].lower()
    if host not in {"mojplaywin.com", "www.mojplaywin.com"}:
        raise Http404("Moj Prop belongs to MojPlayWin")
    if request.method not in ("GET", "HEAD"):
        return HttpResponseNotAllowed(["GET", "HEAD"])
    try:
        page = page_context(lang)
        labels = labels_for(lang)
    except ValueError as error:
        raise Http404("Unsupported language") from error

    if not request.user.is_authenticated:
        # Keep customer login unlaunched; do not redirect to staff admin login.
        response = redirect("/moj-prop/" if lang == "en" else f"/moj-prop/{lang}/")
        response["Cache-Control"] = "private, no-store"
        return response

    profile = PropTrader.objects.filter(user=request.user).first()
    accounts = [] if profile is None else list(
        PropAccount.objects.filter(trader=profile)
        .order_by("-created_at")[:20]
    )
    projected = [account_projection(account) for account in accounts]
    context = dict(page)
    context.update({
        "labels": labels,
        "records": projected,
        "dashboard_path": ("/moj-prop/dashboard/" if lang == "en"
                           else f"/moj-prop/{lang}/dashboard/"),
        "portal_prelaunch": True,
    })
    response = render(request, "mojplaywin/moj_prop_dashboard.html", context)
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Pragma"] = "no-cache"
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["X-Frame-Options"] = "DENY"
    return response


@never_cache
@csrf_protect
@require_POST
def moj_prop_interest(request):
    """Consent-only Plan 1 interest intake; NOT a checkout or confirmed enrollment."""
    import hashlib
    import hmac
    from django.conf import settings
    from django.core.cache import cache
    from django.core.exceptions import ValidationError
    from core.contact_intake import canonical_contact_email
    from django.db import transaction
    from django.http import HttpResponse
    from prop_firm.models import PropInterest

    try:
        host = request.get_host().split(":")[0].lower()
    except Exception:
        raise Http404
    if host not in ("mojplaywin.com", "www.mojplaywin.com") or not request.is_secure():
        raise Http404
    # Require browser-native form format; read no raw POST body (CSRF may consume it).
    try:
        length = int(request.META.get("CONTENT_LENGTH", "0"))
    except (ValueError, TypeError):
        return HttpResponse("Invalid form", status=400)
    if (request.content_type != "application/x-www-form-urlencoded"
            or not 0 < length <= 4096):
        return HttpResponse("Invalid form", status=400)
    # Django QueryDict.get returns the last value on duplicate keys. Reject
    # duplicate critical fields so an intermediate proxy cannot reinterpret them.
    required = ("email", "plan_code", "contact_consent", "consent_version", "source_language")
    fields = set(request.POST)
    if (fields not in (set(required), set(required) | {"csrfmiddlewaretoken"})
            or any(len(request.POST.getlist(field)) != 1 for field in required)
            or ("csrfmiddlewaretoken" in fields
                and len(request.POST.getlist("csrfmiddlewaretoken")) != 1)):
        return HttpResponse("Invalid form fields", status=400)
    if (request.POST["plan_code"] != "MOJ-PROP-01"
            or request.POST["contact_consent"] != "yes"
            or request.POST["consent_version"] != "moj-prop-interest-v1"):
        return HttpResponse("Plan 1 and explicit consent required", status=400)
    language = request.POST["source_language"]
    if language not in SUPPORTED_CODES:
        return HttpResponse("Unsupported language", status=400)
    try:
        email = canonical_contact_email(request.POST["email"])
    except ValidationError:
        return HttpResponse("Valid email required", status=400)
    # Rate-limit BEFORE database writes. Store only an IP HMAC bucket, never raw IP.
    ip = request.META.get("REMOTE_ADDR", "")
    if type(ip) is not str or not 1 <= len(ip) <= 80:
        return HttpResponse("Request unavailable", status=503)
    digest = hmac.new(str(settings.SECRET_KEY).encode(), ip.encode(), hashlib.sha256).hexdigest()
    key = "moj-prop:intake:v2:" + digest
    try:
        if not cache.add(key, 1, timeout=3600) and cache.incr(key) > 8:
            return HttpResponse("Too many requests", status=429)
    except Exception:
        return HttpResponse("Request unavailable", status=503)
    with transaction.atomic():
        PropInterest.objects.get_or_create(email=email, defaults={
            "plan_code": "MOJ-PROP-01", "source_language": language,
            "consent_version": "moj-prop-interest-v1",
        })
    # Do not reveal whether an email was already registered or withdrawn.
    response = HttpResponse(INTEREST_COPY.get(language, INTEREST_COPY["en"])[5],
                            status=202, content_type="text/plain; charset=utf-8")
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Referrer-Policy"] = "same-origin"
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["X-Content-Type-Options"] = "nosniff"
    return response
