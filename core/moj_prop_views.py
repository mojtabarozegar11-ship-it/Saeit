"""Read-only MojPlayWin / Moj Prop landing page.

Never expose the page as the independent Zomorod Melal company's offer.
No customer registration, wallet payment, promise of funded eligibility, or trades.
"""
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from prop_firm.moj_prop_page import page_context


def moj_prop_landing(request, lang="en"):
    host = request.get_host().split(":")[0].lower()
    if host not in {"mojplaywin.com", "www.mojplaywin.com"}:
        raise Http404("Moj Prop belongs to MojPlayWin")
    try:
        data = page_context(lang)
    except ValueError as error:
        raise Http404("Unsupported language") from error
    response = render(request, "mojplaywin/moj_prop.html", data)
    response["Cache-Control"] = "public, max-age=300"
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
    """Accept an opt-in contact request for Plan 1; NEVER sell or issue a TRX invoice."""
    import hashlib
    import hmac
    from django.conf import settings
    from django.core.cache import cache
    from django.core.exceptions import ValidationError
    from django.core.validators import validate_email
    from django.db import transaction
    from django.http import HttpResponse, HttpResponseNotAllowed
    from prop_firm.models import PropInterest

    # The route is deliberately not mounted on other domains or plaintext HTTP.
    try:
        host = request.get_host().split(":")[0].lower()
    except Exception:
        raise Http404
    if host not in ("mojplaywin.com", "www.mojplaywin.com") or not request.is_secure():
        raise Http404
    if (request.content_type != "application/x-www-form-urlencoded"
            or len(request.body) > 4096):
        return HttpResponse("Invalid form", status=400)
    if (request.POST.get("plan_code") != "MOJ-PROP-01"
            or request.POST.get("contact_consent") != "yes"
            or request.POST.get("consent_version") != "moj-prop-interest-v1"):
        return HttpResponse("Plan 1 and contact consent required", status=400)
    raw = request.POST.get("email", "")
    if type(raw) is not str or not raw or len(raw) > 254:
        return HttpResponse("Valid email required", status=400)
    email = raw.strip().lower()
    try:
        validate_email(email)
    except ValidationError:
        return HttpResponse("Valid email required", status=400)

    # Do not store IP addresses; HMAC-keyed throttling is fail-closed.
    ip = request.META.get("REMOTE_ADDR", "")
    if type(ip) is not str or not 1 <= len(ip) <= 80:
        return HttpResponse("Request unavailable", status=503)
    bucket = hmac.new(str(settings.SECRET_KEY).encode(), ip.encode(), hashlib.sha256).hexdigest()
    key = "moj-prop:interest:v1:" + bucket
    try:
        if not cache.add(key, 1, timeout=3600) and cache.incr(key) > 8:
            return HttpResponse("Too many requests", status=429)
    except Exception:
        return HttpResponse("Request unavailable", status=503)

    with transaction.atomic():
        PropInterest.objects.get_or_create(email=email, defaults={
            "plan_code": "MOJ-PROP-01", "source_language": "en",
            "consent_version": "moj-prop-interest-v1",
        })
    # Do not reveal whether this email was previously registered.
    response = HttpResponse(
        "Your interest in MOJ PROP Plan 1 was recorded. "
        "No payment has been requested, no challenge account has been created. "
        "MojPlayWin will contact you only about this request.",
        status=202, content_type="text/plain; charset=utf-8",
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response
