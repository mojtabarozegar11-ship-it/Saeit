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
