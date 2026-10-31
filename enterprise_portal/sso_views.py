"""Private, disabled-by-default PHP→Django office SSO consumer.

Only a fresh active PHP account can issue a ticket; Django additionally requires
an explicitly approved mapping, an eligible office user and a confirmed OTP
device. The sole CSRF-exempt action uses a secret HMAC and exact HTTPS Origin.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import stat
import time

from django.conf import settings
from django.contrib.auth import login as django_login
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.http import HttpResponseForbidden, HttpResponseNotFound
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_otp import user_has_device
from django_otp.views import LoginView as OtpLoginView

from .forms import has_office_access
from .models import OfficeSsoIdentity, OfficeSsoNonce
from .sso_contract import SSOTicketError, verify_ticket
from .views import no_cache

SSO_ORIGIN = "https://zomorodmelal.ir"
SSO_PENDING_LIMIT = 300


def _private_key() -> bytes:
    location = getattr(settings, "COMPANY_OFFICE_SSO_KEY_PATH", "")
    if not isinstance(location, str) or not location.startswith("/"):
        raise SSOTicketError("server key unavailable")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(location, flags)
        try:
            status = os.fstat(fd)
            if (not stat.S_ISREG(status.st_mode) or status.st_uid != os.geteuid()
                    or stat.S_IMODE(status.st_mode) != 0o600 or status.st_size < 32
                    or status.st_size > 256):
                raise SSOTicketError("server key unavailable")
            with os.fdopen(fd, "rb", closefd=False) as file:
                key = file.read(257)
            if len(key) < 32 or len(key) > 256:
                raise SSOTicketError("server key unavailable")
            return key
        finally:
            os.close(fd)
    except OSError as exc:
        raise SSOTicketError("server key unavailable") from exc


def _consume_nonce(digest: str, expires: int) -> bool:
    # Unique primary key makes concurrent one-time use atomic across workers.
    try:
        with transaction.atomic():
            OfficeSsoNonce.objects.create(
                digest=digest,
                expires_at=datetime.fromtimestamp(expires, tz=timezone.utc),
            )
        return True
    except IntegrityError:
        return False


@csrf_exempt
@require_POST
@never_cache
def consume_ticket(request):
    if not getattr(settings, "COMPANY_OFFICE_SSO_ENABLED", False):
        return no_cache(HttpResponseNotFound())
    if not request.is_secure() or request.headers.get("Origin") != SSO_ORIGIN:
        return no_cache(HttpResponseForbidden("ورود امن تأیید نشد."))
    if request.content_type != "application/x-www-form-urlencoded":
        return no_cache(HttpResponseForbidden("درخواست ورود نامعتبر است."))
    token = request.POST.get("ticket", "")
    try:
        identity = verify_ticket(
            token, _private_key(), consume_nonce=_consume_nonce,
        )
    except (SSOTicketError, ValueError):
        return no_cache(HttpResponseForbidden("درخواست ورود نامعتبر است."))
    mapping = OfficeSsoIdentity.objects.select_related("user").filter(
        php_uid=identity["uid"], role=identity["role"], active=True,
    ).first()
    if mapping is None or not has_office_access(mapping.user):
        return no_cache(HttpResponseForbidden("مجوز ورود فعال نیست."))
    if not user_has_device(mapping.user, confirmed=True):
        return no_cache(HttpResponseForbidden("تأیید دومرحله‌ای قبلاً ثبت نشده است."))
    django_login(request, mapping.user, backend="django.contrib.auth.backends.ModelBackend")
    request.session["zm_sso_pending"] = int(time.time())
    request.session["zm_sso_php_uid"] = identity["uid"]
    request.session.set_expiry(SSO_PENDING_LIMIT)
    return no_cache(redirect("enterprise_portal:sso_step_up"))


@method_decorator(never_cache, name="dispatch")
class CompanySsoOtpStepUp(OtpLoginView):
    """Passwordless *second step only* after a valid PHP assertion."""
    template_name = "enterprise_portal/sso_step_up.html"

    def dispatch(self, request, *args, **kwargs):
        if not getattr(settings, "COMPANY_OFFICE_SSO_ENABLED", False):
            return no_cache(HttpResponseNotFound())
        issued = request.session.get("zm_sso_pending")
        if (not request.is_secure() or not request.user.is_authenticated
                or type(issued) is not int or not 0 <= int(time.time()) - issued <= SSO_PENDING_LIMIT):
            return no_cache(HttpResponseForbidden("نشست ورود یکپارچه معتبر نیست."))
        if not has_office_access(request.user):
            return no_cache(HttpResponseForbidden("مجوز ورود فعال نیست."))
        return no_cache(super().dispatch(request, *args, **kwargs))

    def get_success_url(self):
        return reverse("enterprise_portal:dashboard")

    def form_valid(self, form):
        # OtpLoginView validates a device-specific token and persists that device.
        response = super().form_valid(form)
        self.request.session.pop("zm_sso_pending", None)
        self.request.session.set_expiry(30 * 60)
        return no_cache(response)
