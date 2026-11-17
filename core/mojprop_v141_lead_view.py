"""Isolated, default-OFF MOJ PROP prelaunch inquiry; never a checkout.

All incoming messages require explicit purpose-limited consent. No marketing,
invoice, KYC, brokerage order, social-post agreement or cash transfer.
"""
from hashlib import sha256
import hmac

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404, HttpResponse, HttpResponseNotAllowed
from django.shortcuts import render
from django.utils.cache import patch_vary_headers
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect

from core.contact_intake import canonical_contact_email
from prop_firm.plan1_v141_lead_models import CONSENT_VERSION, PropV141Interest
from prop_firm.mojprop_v141_interest_i18n import interest_context, interest_catalog
from prop_firm.moj_prop_page import SUPPORTED_CODES

_HOSTS = frozenset(("mojplaywin.com", "www.mojplaywin.com"))
_LANGUAGE = frozenset(SUPPORTED_CODES)
_REQUIRED = frozenset((
    "email", "plan_code", "consent_version",
    "contact_consent", "language",
))


def _response_headers(response):
    response["Cache-Control"] = "private, no-store, max-age=0"
    response["Pragma"] = "no-cache"
    response["Referrer-Policy"] = "same-origin"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["X-Frame-Options"] = "DENY"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = (
        "default-src 'none'; style-src 'unsafe-inline'; "
        "form-action 'self'; base-uri 'none'; frame-ancestors 'none'; "
        "connect-src 'none'; object-src 'none'"
    )
    return response


def _limit_ip(request):
    ip = request.META.get("REMOTE_ADDR", "")
    if type(ip) is not str or not 1 <= len(ip) <= 80:
        return False
    key = "mojprop-v141:interest:" + hmac.new(
        str(settings.SECRET_KEY).encode(), ip.encode(), sha256
    ).hexdigest()
    try:
        # Cache backend must support atomic add/incr. Fail closed if unavailable.
        if cache.add(key, 1, timeout=3600):
            return True
        return cache.incr(key) <= 8
    except Exception:
        return False


@never_cache
@csrf_protect
def moj_prop_v141_interest(request):
    if getattr(settings, "MOJ_PROP_V141_INTEREST_ENABLED", False) is not True:
        raise Http404("Inquiries disabled pending release")
    try:
        host = request.get_host().split(":", 1)[0].lower()
    except Exception as exc:
        raise Http404("Invalid host") from exc
    if host not in _HOSTS or request.is_secure() is not True:
        raise Http404("MojPlayWin HTTPS only")
    if request.method not in ("GET", "HEAD", "POST"):
        return _response_headers(HttpResponseNotAllowed(["GET", "HEAD", "POST"]))

    if request.method in ("GET", "HEAD"):
        if set(request.GET) - {"lang"} or len(request.GET.getlist("lang")) > 1:
            return _response_headers(HttpResponse("Unsupported query", status=400))
        lang = request.GET.get("lang", "en")
        if lang not in _LANGUAGE:
            return _response_headers(HttpResponse("Unsupported language", status=400))
        response = render(
            request, "moj-prop-plan1-v141-prelaunch/interest.html",
            {**interest_context(lang), "consent_version": CONSENT_VERSION},
        )
        patch_vary_headers(response, ("Cookie",))
        if request.method == "HEAD":
            response.content = b""
        return _response_headers(response)

    # No query-string parameters on POST; personal details belong in CSRF form.
    if request.META.get("QUERY_STRING", ""):
        return _response_headers(HttpResponse("Unexpected query", status=400))
    try:
        length = int(request.META.get("CONTENT_LENGTH", "0"))
    except (TypeError, ValueError):
        return _response_headers(HttpResponse("Invalid length", status=400))
    if request.content_type != "application/x-www-form-urlencoded" or not 0 < length <= 4096:
        return _response_headers(HttpResponse("Invalid form", status=400))
    submitted = set(request.POST)
    if submitted not in (_REQUIRED, _REQUIRED | {"csrfmiddlewaretoken"}):
        return _response_headers(HttpResponse("Invalid form keys", status=400))
    if any(len(request.POST.getlist(k)) != 1 for k in submitted):
        return _response_headers(HttpResponse("Duplicate form fields", status=400))
    if (request.POST["plan_code"] != "MOJ-PROP-01"
            or request.POST["consent_version"] != CONSENT_VERSION
            or request.POST["contact_consent"] != "yes"
            or request.POST["language"] not in _LANGUAGE):
        return _response_headers(HttpResponse("Explicit Plan 1 contact consent required", status=400))
    try:
        email = canonical_contact_email(request.POST["email"])
    except ValidationError:
        return _response_headers(HttpResponse("Invalid email", status=400))
    if not _limit_ip(request):
        return _response_headers(HttpResponse("Request unavailable or rate limited", status=429))
    # Cannot enroll/pay or change a withdrawn record. The unique email index
    # serializes concurrent get_or_create requests; an existing origin is immutable.
    with transaction.atomic():
        PropV141Interest.objects.get_or_create(
            email=email,
            defaults={
                "plan_code": "MOJ-PROP-01",
                "source_language": request.POST["language"],
                "consent_version": CONSENT_VERSION,
            },
        )
    lang = request.POST["language"]
    message = interest_catalog()[lang]["received"]
    response = HttpResponse(message, status=202,
                            content_type="text/plain; charset=utf-8")
    return _response_headers(response)
