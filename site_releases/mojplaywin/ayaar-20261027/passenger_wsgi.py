"""Isolated, dependency-free, read-only WSGI site for /ayaar/.

No Django process, database, filesystem write, network fetch, or credential.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ALLOWED = {
    "index.html": "text/html; charset=utf-8",
    "methodology.html": "text/html; charset=utf-8",
    "styles.css": "text/css; charset=utf-8",
    "hero.css": "text/css; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
    "favicon.svg": "image/svg+xml",
    "hero-art.svg": "image/svg+xml",
}
CSP = (
    "default-src 'self'; base-uri 'self'; form-action 'self'; "
    "frame-ancestors 'none'; object-src 'none'; script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; "
    "connect-src 'none'; upgrade-insecure-requests"
)


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "")
    if method not in ("GET", "HEAD"):
        body = b"Method not allowed"
        start_response("405 Method Not Allowed", [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Allow", "GET, HEAD"),
            ("Cache-Control", "no-store"),
        ])
        return [body] if method != "HEAD" else [b""]

    path = environ.get("PATH_INFO", "/")
    # Passenger normally strips SCRIPT_NAME; also accept the full prefix.
    if path in ("", "/", "/ayaar", "/ayaar/"):
        filename = "index.html"
    else:
        if path.startswith("/ayaar/"):
            path = path[len("/ayaar"):]
        filename = path[1:] if path.startswith("/") else ""
    if filename not in ALLOWED:
        body = b"Not found"
        start_response("404 Not Found", [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
        ])
        return [body] if method != "HEAD" else [b""]

    file = ROOT / filename
    if file.is_symlink() or not file.is_file() or file.stat().st_size > 350_000:
        body = b"Unavailable"
        start_response("503 Service Unavailable", [
            ("Content-Type", "text/plain; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
        ])
        return [body] if method != "HEAD" else [b""]

    payload = file.read_bytes()
    headers = [
        ("Content-Type", ALLOWED[filename]),
        ("Content-Length", str(len(payload))),
        ("Content-Security-Policy", CSP),
        ("X-Content-Type-Options", "nosniff"),
        ("X-Frame-Options", "DENY"),
        ("Cache-Control", "public, max-age=180" if filename.endswith(".html") else "public, max-age=3600"),
    ]
    start_response("200 OK", headers)
    return [payload] if method == "GET" else [b""]
