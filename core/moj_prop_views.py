"""Read-only MojPlayWin / Moj Prop landing page.

Never expose the page as the independent Zomorod Melal company's offer.
No customer registration, wallet payment, promise of funded eligibility, or trades.
"""
from django.http import Http404
from django.shortcuts import render

from prop_firm.moj_prop_page import page_context


def moj_prop_landing(request, lang="en"):
    host = request.get_host().split(":")[0].lower()
    if host not in {"mojplaywin.com", "www.mojplaywin.com"}:
        raise Http404("Moj Prop belongs to MojPlayWin")
    try:
        data = page_context(lang)
        # Only render an information CTA when the consent/privacy backend
        # has been explicitly released. It never links to a payment form.
        from prop_firm.interest import intake_enabled
        data["interest_enabled"] = intake_enabled()
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

def moj_prop_interest(request):
    """Information inquiry, English-first; NEVER challenge enrollment or billing."""
    from django.http import HttpResponse, Http404
    from django.views.decorators.http import require_http_methods
    from django.views.decorators.csrf import csrf_protect
    from prop_firm.interest import intake_enabled, submit_inquiry, PropInterestError

    @csrf_protect
    @require_http_methods(["GET", "POST"])
    def endpoint(request):
        host = request.get_host().split(":")[0].lower()
        if host not in ("mojplaywin.com", "www.mojplaywin.com"):
            raise Http404("Moj Prop is exclusive to MojPlayWin")
        if not intake_enabled():
            raise Http404("Interest intake is not published")
        if not request.is_secure():
            raise Http404("Secure channel required")
        success, error, status = False, "", 200
        if request.method == "POST":
            try:
                submit_inquiry(
                    email=request.POST.get("email", ""),
                    consent=request.POST.get("privacy_consent") == "yes",
                    remote_addr=request.META.get("REMOTE_ADDR", ""),
                )
                success = True
            except PropInterestError as exc:
                reason = str(exc)
                if reason == "interest_rate_limited":
                    status, error = 429, "Too many requests. Try again later."
                elif reason in ("interest_rate_check_unavailable", "interest_intake_not_released"):
                    status, error = 503, "Contact requests are temporarily unavailable."
                else:
                    status, error = 400, "Valid email and explicit consent are required."
        response = render(
            request, "mojplaywin/moj_prop_interest.html",
            {"success": success, "error": error},
            status=status,
        )
        response["Cache-Control"] = "private, no-store, max-age=0"
        response["X-Robots-Tag"] = "noindex, nofollow"
        response["X-Frame-Options"] = "DENY"
        response["Referrer-Policy"] = "same-origin"
        response["Content-Security-Policy"] = (
            "default-src 'self'; form-action 'self'; base-uri 'self'; "
            "frame-ancestors 'none'; style-src 'self' 'unsafe-inline'"
        )
        return response

    return endpoint(request)

def moj_prop_privacy(request):
    """Source-specific inquiry disclosure, not a blanket legal compliance claim."""
    if request.get_host().split(":")[0].lower() not in {
        "mojplaywin.com", "www.mojplaywin.com"
    }:
        raise Http404("Moj Prop information belongs to MojPlayWin")
    if request.method not in ("GET", "HEAD"):
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(["GET", "HEAD"])
    response = render(request, "mojplaywin/moj_prop_privacy.html")
    response["Cache-Control"] = "public, max-age=300"
    response["X-Robots-Tag"] = "noindex, nofollow"
    response["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'self'; frame-ancestors 'none'; "
        "style-src 'self' 'unsafe-inline'"
    )
    return response
