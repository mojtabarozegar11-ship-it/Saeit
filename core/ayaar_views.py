"""Exact, read-only AYAR microsite on the MojPlayWin Django router.

Only seven code-reviewed files inside the checked-in immutable release are
served. This endpoint does not touch accounts, payments, inventory or orders.
"""

from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseNotAllowed


_DIR = Path(settings.BASE_DIR) / "site_releases" / "mojplaywin" / "ayaar-20261027"
_ALLOWED = {
    "index.html": "text/html; charset=utf-8",
    "methodology.html": "text/html; charset=utf-8",
    "styles.css": "text/css; charset=utf-8",
    "hero.css": "text/css; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
    "favicon.svg": "image/svg+xml",
    "hero-art.svg": "image/svg+xml",
}
_CSP = (
    "default-src 'self'; base-uri 'self'; form-action 'self'; "
    "object-src 'none'; frame-ancestors 'none'; "
    "script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; "
    "connect-src 'none'; upgrade-insecure-requests"
)


def ayaar(request, asset="index.html"):
    """Serve exact AYAR assets without directory listing or dynamic evaluation."""
    if request.method not in ("GET", "HEAD"):
        return HttpResponseNotAllowed(("GET", "HEAD"))
    if asset not in _ALLOWED:
        raise Http404("AYAR asset not found")
    path = _DIR / asset
    if not path.is_file() or path.is_symlink():
        raise Http404("AYAR release is unavailable")
    result = FileResponse(path.open("rb"), content_type=_ALLOWED[asset])
    result["X-Content-Type-Options"] = "nosniff"
    result["X-Frame-Options"] = "DENY"
    result["Content-Security-Policy"] = _CSP
    if asset.endswith(".html"):
        result["Cache-Control"] = "public, max-age=180, must-revalidate"
    else:
        result["Cache-Control"] = "public, max-age=3600, must-revalidate"
    return result
