"""Data isolation across ecosystem units. Staff role != access to every unit."""
from django.core.exceptions import PermissionDenied
from enterprise_portal.models import BusinessUnit
from .models import UnitMembership


def user_units(user):
    if not user.is_authenticated or not user.is_active or not user.is_staff:
        return BusinessUnit.objects.none()
    if user.is_superuser:
        return BusinessUnit.objects.all()
    return BusinessUnit.objects.filter(
        ecosystem_memberships__user=user,
        ecosystem_memberships__active=True,
    ).distinct()


def can_view_unit(user, unit):
    if not user or not user.is_authenticated or not user.is_active or not user.is_staff:
        return False
    return bool(user.is_superuser or user_units(user).filter(pk=unit.pk).exists())


def require_unit(user, unit, *, write=False, approve=False):
    if not can_view_unit(user, unit):
        raise PermissionDenied("دسترسی به اطلاعات این واحد شرکت مجاز نیست.")
    if user.is_superuser:
        return
    membership = UnitMembership.objects.get(user=user, unit=unit, active=True)
    if write and membership.role not in ("owner", "manager", "finance", "operations"):
        raise PermissionDenied("مجوز ویرایش در این واحد را ندارید.")
    if approve and not membership.can_approve:
        raise PermissionDenied("تأیید این تصمیم نیازمند مجوز مستقل است.")
