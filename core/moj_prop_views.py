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
