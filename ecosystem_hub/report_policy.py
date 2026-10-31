"""Apply assistant data-source permissions *also when reading archived reports*.

Permission changes and revoked memberships must take effect immediately: access
at report generation time is not authorization to view it months later.
"""
from django.core.exceptions import PermissionDenied

from .analysis import HANDLER_VIEW_PERMISSIONS
from .catalog import CATALOG


def permitted_assistant_codes(user):
    if not user.is_authenticated or not user.is_active or not user.is_staff:
        return set()
    allowed = set()
    for code, meta in CATALOG.items():
        required = HANDLER_VIEW_PERMISSIONS.get(meta["handler"], ())
        if user.is_superuser or all(user.has_perm(perm) for perm in required):
            allowed.add(code)
    return allowed


def enforce_report_sources(user, report):
    if report.assistant_code not in permitted_assistant_codes(user):
        raise PermissionDenied(
            "مجوز مشاهده داده‌های اصلی این گزارش برای حساب فعلی موجود نیست."
        )
