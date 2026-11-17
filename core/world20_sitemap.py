"""Read-only MojPlayWin-owned sitemap and robots; no cross-domain poisoning.

This module is ONLY for HTTPS mojplaywin.com/www and does not change the
original zomorodmelal.ir sitemap, product commerce, robots or checkout.
"""
from django.http import Http404, HttpResponse
from django.views.decorators.http import require_GET
from xml.sax.saxutils import escape as xml_escape

from .world20_views import world_catalog

_HOSTS = frozenset(("mojplaywin.com", "www.mojplaywin.com"))
_CANONICAL = "https://mojplaywin.com"
_PUBLIC = ("/", "/moj-prop/", "/store/", "/studio/", "/research/",
           "/knowledge/", "/agents/", "/company/")


def _check_host(request):
    try:
        host = request.get_host().split(":", 1)[0].lower()
    except Exception as exc:
        raise Http404("Unavailable sitemap host") from exc
    if host not in _HOSTS or not request.is_secure():
        raise Http404("Only the MojPlayWin HTTPS sitemap is allowed")


@require_GET
def mojplaywin_world_robots(request):
    _check_host(request)
    response = HttpResponse(
        "User-agent: *\nAllow: /\n"
        "Disallow: /admin/\nDisallow: /api/\n"
        "Disallow: /moj-prop-v141/portfolio/\n"
        "Disallow: /moj-prop-v141/statement/\n"
        "Disallow: /moj-prop-v141-interest/\n"
        "Sitemap: https://mojplaywin.com/sitemap.xml\n",
        content_type="text/plain; charset=utf-8",
    )
    response["Cache-Control"] = "public, max-age=300"
    return response


@require_GET
def mojplaywin_world_sitemap(request):
    _check_host(request)
    source = world_catalog()
    codes = tuple(source["ranked_codes"]) + tuple(source["supplementary_codes"])
    alt = [("x-default", _CANONICAL + "/world/")] + [
        (code, _CANONICAL + "/world/" + code + "/") for code in codes
    ]
    entries = []
    for path in _PUBLIC + ("/world/",) + tuple(
            "/world/" + code + "/" for code in codes):
        loc = _CANONICAL + path
        if path.startswith("/world/"):
            alternates = "".join(
                '<xhtml:link rel="alternate" hreflang="' + code +
                '" href="' + xml_escape(url, {'"': '&quot;'}) + '"/>'
                for code, url in alt
            )
        else:
            alternates = ""
        entries.append("<url><loc>" + xml_escape(loc) + "</loc>" +
                       alternates + "</url>")
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">' +
        "".join(entries) + "</urlset>"
    )
    response = HttpResponse(xml, content_type="application/xml; charset=utf-8")
    response["Cache-Control"] = "public, max-age=300"
    return response
