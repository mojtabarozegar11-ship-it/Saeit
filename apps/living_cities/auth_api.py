"""Scoped login/session endpoints using the existing MojPlayWin Django users."""
import json

from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST


@require_GET
@ensure_csrf_cookie
def csrf_view(request):
    """Bootstrap CSRF for the current static game without replacing its HTML."""
    response = JsonResponse({"csrf_token": get_token(request)})
    response["Cache-Control"] = "private, no-store"
    return response


@require_POST
@csrf_protect
def login_view(request):
    if len(request.body) > 4096:
        return JsonResponse({"error": "invalid_request"}, status=400)
    try:
        credentials = json.loads(request.body or "{}")
    except (TypeError, ValueError, UnicodeDecodeError):
        credentials = None
    if not isinstance(credentials, dict):
        return JsonResponse({"error": "invalid_request"}, status=400)
    username = credentials.get("username")
    password = credentials.get("password")
    if not isinstance(username, str) or not isinstance(password, str):
        return JsonResponse({"error": "invalid_credentials"}, status=401)
    user = authenticate(request, username=username, password=password)
    if user is None or not user.is_active:
        return JsonResponse({"error": "invalid_credentials"}, status=401)
    login(request, user)
    # login() rotates the CSRF secret; return the *new* masked token so the
    # browser can immediately issue a protected business action.
    response = JsonResponse({
        "authenticated": True,
        "user": {"id": user.pk, "username": user.get_username()},
        "csrf_token": get_token(request),
    })
    response["Cache-Control"] = "private, no-store"
    return response


@require_GET
def me_view(request):
    if not request.user.is_authenticated:
        response = JsonResponse({"authenticated": False}, status=401)
    else:
        response = JsonResponse({
            "authenticated": True,
            "user": {"id": request.user.pk, "username": request.user.get_username()},
        })
    response["Cache-Control"] = "private, no-store"
    return response


@require_POST
@csrf_protect
def logout_view(request):
    logout(request)
    response = JsonResponse({"authenticated": False})
    response["Cache-Control"] = "private, no-store"
    return response
