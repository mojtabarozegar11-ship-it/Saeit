"""Determine MojPlayWin-main-only presentation mode without mutating request routing.

Fail closed: never apply the shared MojPlayWin shell to isolated subsite,
checkout/API/admin endpoints, unknown routes, or other hosts.
"""
from django import template

register = template.Library()

MAIN_HOSTS = frozenset(("mojplaywin.com", "www.mojplaywin.com"))

# The current main-home design is already embedded by these Django templates.
ALREADY_BRANDED = frozenset((
    "/", "/store/", "/research/", "/knowledge/", "/market/", "/economy/",
    "/studio/", "/agents/", "/industry/", "/company/", "/services/",
))
# Main-site page families that use core/base.html but still need the same
# masthead, footer, dark panels and gold typography as the active home.
MAIN_FAMILIES = (
    "/agriculture/", "/search/", "/weather/", "/auctions/", "/blog/",
    "/knowledge/article/", "/knowledge/book/", "/knowledge/domain/",
    "/company-gallery/", "/company-content/", "/newsletter/",
    "/amozeshgah/", "/education/", "/academy/",
)
MAIN_EXACT = frozenset(("/agriculture", "/search", "/weather", "/auctions", "/blog", "/newsletter"))
# Prefix denylist is deliberately wider than the existing Django routes,
# because sibling sites may be served from cPanel paths outside this repo.
EXCLUDED_FAMILIES = (
    "/admin/", "/staff/", "/api/", "/farnaz/", "/zahra/", "/roham/",
    "/saman/", "/taniya/", "/mojtaba.roozegar/", "/mojtaba-rozegar/",
    "/picm/", "/tala/", "/mohammad/", "/ghanadi/", "/research-lab/admin/",
    "/checkout/", "/cart/", "/orders/", "/payments/", "/payment/",
    "/webhook/", "/account/", "/accounts/", "/login/", "/logout/",
)


def shell_mode(host, path):
    """Return managed, legacy, or skip. Never dispatch URLs or alter products."""
    if not isinstance(host, str) or host.split(":", 1)[0].lower().rstrip(".") not in MAIN_HOSTS:
        return "skip"
    if not isinstance(path, str) or not path.startswith("/") or "//" in path:
        return "skip"
    lowered = path.lower()
    if any(lowered.startswith(prefix) or lowered == prefix.rstrip("/")
           for prefix in EXCLUDED_FAMILIES):
        return "skip"
    if lowered in ALREADY_BRANDED or lowered.startswith("/ventures/"):
        return "managed"
    if lowered in MAIN_EXACT or any(lowered.startswith(prefix) for prefix in MAIN_FAMILIES):
        return "legacy"
    return "skip"


@register.simple_tag
def mpw_shell_mode(request):
    if request is None:
        return "skip"
    try:
        return shell_mode(request.get_host(), request.path)
    except (AttributeError, ValueError):
        return "skip"
