"""Scoped AYAR public pages and private dossier review API.

No changes to MojPlayWin's database, account records, orders or payment flows.
The API uses an isolated, private SQLite case store; staff review requires an
already-authenticated Django staff session and explicit conflict disclosure.
"""

import json
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseNotAllowed, JsonResponse
from django.middleware.csrf import get_token

from core import ayaar_case_service as cases


_DIR = Path(settings.BASE_DIR) / "site_releases" / "mojplaywin" / "ayaar-20261027"
_ALLOWED = {
    "index.html": "text/html; charset=utf-8",
    "methodology.html": "text/html; charset=utf-8",
    "styles.css": "text/css; charset=utf-8",
    "hero.css": "text/css; charset=utf-8",
    "app.js": "text/javascript; charset=utf-8",
    "favicon.svg": "image/svg+xml",
    "hero-art.svg": "image/svg+xml",
    "services.html": "text/html; charset=utf-8",
    "submit.html": "text/html; charset=utf-8",
    "track.html": "text/html; charset=utf-8",
    "reviewer.html": "text/html; charset=utf-8",
    "registry.html": "text/html; charset=utf-8",
    "privacy.html": "text/html; charset=utf-8",
    "platform.css": "text/css; charset=utf-8",
    "platform.js": "text/javascript; charset=utf-8",
}
_CSP = (
    "default-src 'self'; base-uri 'self'; form-action 'self'; "
    "object-src 'none'; frame-ancestors 'none'; "
    "script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; "
    "connect-src 'self'; upgrade-insecure-requests"
)


def _api_json(data, status=200):
    response = JsonResponse(data, status=status)
    response["Cache-Control"] = "no-store, max-age=0"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = _CSP
    return response


def _read_payload(request):
    length = request.META.get("CONTENT_LENGTH", "")
    try:
        if length and int(length) > cases.MAX_REQUEST + 100000:
            raise cases.CaseError("Submission exceeds the evidence upload limit", 413)
    except ValueError:
        raise cases.CaseError("Invalid body length")
    if request.content_type and request.content_type.startswith("multipart/form-data"):
        source = request.POST.get("payload", "")
    elif request.content_type == "application/json":
        source = request.body.decode("utf-8")
    else:
        raise cases.CaseError("Use JSON or multipart form data")
    try:
        payload = json.loads(source)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise cases.CaseError("Invalid JSON payload")
    if not isinstance(payload, dict):
        raise cases.CaseError("Expected a JSON object")
    return payload


def _require_staff(request):
    if not request.user.is_authenticated or not request.user.is_staff:
        raise cases.CaseError("Authenticated staff access required", 403)
    return "staff:" + str(request.user.pk)


def _api(request):
    if request.method == "GET":
        operation = request.GET.get("op", "config")
        if operation == "config":
            return _api_json({
                "ok": True, "csrf_token": get_token(request),
                "categories": sorted(cases.CASE_TYPES),
                "services": sorted(cases.SERVICE_TYPES),
                "attachment_limit": cases.MAX_FILE,
                "max_attachments": cases.MAX_ATTACHMENTS,
                "case_tracking": True, "payment_enabled": False,
                "applicant_followups": True, "report_export": True,
                "independent_certification_enabled": False,
                "staff": bool(request.user.is_authenticated and request.user.is_staff),
            })
        if operation == "registry":
            return _api_json({"ok": True, "reports": cases.registry()})
        return _api_json({"ok": False, "error": "Unknown API operation"}, 404)
    if request.method != "POST":
        return _api_json({"ok": False, "error": "Method not allowed"}, 405)
    try:
        payload = _read_payload(request)
        action = payload.get("action")
        if action == "submit":
            result = cases.create_case(
                payload.get("case"), request.FILES.getlist("files"),
                request.META.get("REMOTE_ADDR", ""), settings.SECRET_KEY
            )
        elif action == "status":
            result = cases.case_status(
                payload.get("case_id", ""), payload.get("access_key", ""), settings.SECRET_KEY
            )
        elif action == "reply":
            result = cases.append_case_evidence(
                payload.get("case_id", ""), payload.get("access_key", ""),
                payload.get("note", ""), request.FILES.getlist("files"), settings.SECRET_KEY
            )
        elif action == "delete":
            result = cases.delete_case(
                payload.get("case_id", ""), payload.get("access_key", ""), settings.SECRET_KEY
            )
        elif action == "staff_list":
            _require_staff(request)
            result = {"cases": cases.staff_list()}
        elif action == "staff_case":
            _require_staff(request)
            result = cases.staff_case(payload.get("case_id", ""))
        elif action == "staff_status":
            actor = _require_staff(request)
            result = cases.set_status(
                payload.get("case_id", ""), payload.get("status", ""),
                actor, payload.get("note", "")
            )
        elif action == "staff_review":
            actor = _require_staff(request)
            result = cases.submit_review(
                payload.get("case_id", ""), actor, payload.get("review")
            )
        elif action == "staff_file":
            _require_staff(request)
            path, name = cases.staff_file(payload.get("case_id", ""), payload.get("file_id", ""))
            response = FileResponse(path.open("rb"), as_attachment=True, filename=name,
                                    content_type="application/octet-stream")
            response["Cache-Control"] = "no-store, max-age=0"
            response["X-Content-Type-Options"] = "nosniff"
            response["Content-Security-Policy"] = "default-src 'none'; sandbox"
            return response
        else:
            raise cases.CaseError("Unknown API action", 404)
        return _api_json({"ok": True, "data": result})
    except cases.CaseError as error:
        return _api_json({"ok": False, "error": str(error)}, error.status)


def ayaar(request, asset="index.html"):
    """Serve only allowlisted AYAR assets and its isolated same-origin API."""
    if asset == "api":
        return _api(request)
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
