"""Isolated PICM account login; no credential literals in source or GitHub."""
import hashlib
import json
import time
import unicodedata

from django.contrib.auth import authenticate, login, logout
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from .picm_views import locked
from .picm_access import owner_allowed

LIMIT = 5
PERIOD = 900


def normalize_username(value):
    if not isinstance(value, str):
        return ""
    value = value.strip()
    # Accept ۰۱۲۳... Persian and ٠١٢٣... Arabic forms of the digits.
    output = []
    for ch in value:
        try:
            output.append(str(unicodedata.digit(ch)))
        except (TypeError, ValueError):
            output.append(ch)
    normalized = "".join(output)
    return normalized if 1 <= len(normalized) <= 64 else ""


def _failure_key(username, request):
    ip = request.META.get("REMOTE_ADDR", "")[:70]
    return hashlib.sha256((username + "|" + ip).encode("utf-8")).hexdigest()


def _throttle(key, failed=False, clear=False):
    with locked() as root:
        path = root / ".picm-login-attempts.json"
        if path.is_symlink():
            return True
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (ValueError, OSError):
            data = {}
        now = time.time()
        data = {k: v for k, v in data.items()
                if isinstance(v, list) and len(v) == 2 and
                isinstance(v[0], (int, float)) and now - v[0] < PERIOD}
        if clear:
            data.pop(key, None)
        elif failed:
            first, count = data.get(key, [now, 0])
            data[key] = [first, count + 1]
        allowed = data.get(key, [now, 0])[1] < LIMIT
        # Keep file bounded; credential data and IP addresses are never recorded.
        if len(data) > 1500:
            data = dict(list(data.items())[-1500:])
        path.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
        path.chmod(0o600)
        return not allowed


@never_cache
@require_http_methods(["GET", "POST"])
def picm_login(request):
    if owner_allowed(request.user):
        return redirect("/picm/workspace/")
    error = None
    if request.method == "POST":
        username = normalize_username(request.POST.get("username", ""))
        # Isolate the photo studio from any existing site admin identity.
        credential_username = "picm-" + username if username.startswith("09") and len(username) == 11 and username.isascii() and username.isdigit() else ""
        password = request.POST.get("password", "")
        key = _failure_key(username, request)
        if _throttle(key):
            error = "تلاش‌های ناموفق زیاد بوده است. کمی بعد دوباره امتحان کنید."
        elif not credential_username or not password or len(password) > 256:
            _throttle(key, failed=True)
            error = "نام کاربری یا گذرواژه صحیح نیست."
        else:
            user = authenticate(request, username=credential_username, password=password)
            if user is None or not owner_allowed(user):
                _throttle(key, failed=True)
                error = "نام کاربری یا گذرواژه صحیح نیست."
            else:
                _throttle(key, clear=True)
                login(request, user)
                return redirect("/picm/workspace/")
    return render(request, "picm/login.html", {"picm_error": error})


@never_cache
@require_POST
def picm_logout(request):
    if not request.user.is_authenticated:
        return redirect("/picm/login/")
    if not owner_allowed(request.user):
        # Never log users out of unrelated MojPlayWin services.
        from django.http import HttpResponse
        return HttpResponse(status=403)
    logout(request)
    return redirect("/picm/login/")
