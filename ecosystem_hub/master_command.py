"""Authorized private Zomorod master-command intake.

Natural-language instruction is preserved exactly, but task routing is explicit:
the manager selects a supported read-only specialist. No LLM inference,
external delivery, finance posting, factory control or hidden job execution.
"""
from uuid import UUID, uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from enterprise_portal.models import AuditEvent
from enterprise_portal.views import office_access, no_cache
from .analysis import generate_report
from .catalog import CATALOG
from .models import MasterCommand, UnitMembership
from .report_policy import permitted_assistant_codes
from .views import page, permission, require_hub, select_unit


def _manager_for(user, unit):
    return bool(user.is_superuser or UnitMembership.objects.filter(
        user=user, unit=unit, active=True, role__in=("owner", "manager"),
    ).exists())


def _authorized_specialists(user):
    allowed = permitted_assistant_codes(user)
    return [
        {"code": code, "title": definition["title"], "description": definition["description"]}
        for code, definition in CATALOG.items()
        if code in allowed and definition["handler"]
    ]


@never_cache
@office_access
@csrf_protect
@require_http_methods(["GET", "POST"])
def room(request):
    require_hub(request)
    required = (
        "view_mastercommand", "add_mastercommand",
        "view_assistantrun", "add_assistantrun",
    )
    if not all(permission(request.user, name) for name in required):
        raise PermissionDenied("مجوز مستقل فرماندهی و تهیه گزارش در این حساب موجود نیست.")

    unit, units = select_unit(request)
    if unit is None:
        raise Http404("واحد سازمانی مجاز یافت نشد.")
    if not _manager_for(request.user, unit):
        raise PermissionDenied("فرمان‌دهی فقط برای مدیر مجاز همین واحد فعال است.")

    specialists = _authorized_specialists(request.user)
    eligible = {item["code"] for item in specialists}
    if request.method == "POST":
        instruction = (request.POST.get("instruction") or "").strip()
        code = (request.POST.get("assistant_code") or "").strip()
        if not instruction or len(instruction) > 2000:
            return no_cache(HttpResponse("متن فرمان باید بین ۱ تا ۲۰۰۰ نویسه باشد.", status=400))
        if code not in eligible:
            raise PermissionDenied("دستیار انتخاب‌شده فعال نیست یا اجازه بررسی منبع وجود ندارد.")
        try:
            key = UUID(request.POST.get("request_key", ""))
        except (ValueError, TypeError, AttributeError):
            return no_cache(HttpResponse("شناسه فرمان معتبر نیست.", status=400))

        with transaction.atomic():
            command, created = MasterCommand.objects.get_or_create(
                request_key=key,
                defaults={
                    "unit": unit, "issued_by": request.user,
                    "instruction": instruction, "assistant_code": code,
                },
            )
            if not created:
                if (command.unit_id != unit.pk or
                    command.issued_by_id != request.user.pk or
                    command.instruction != instruction or
                    command.assistant_code != code):
                    return no_cache(HttpResponse("شناسه فرمان قبلاً استفاده شده است.", status=409))
                if command.report_id:
                    return no_cache(redirect(
                        "enterprise_portal:ecosystem_hub:report", pk=command.report_id,
                    ))
                return no_cache(HttpResponse("فرمان هنوز در حال پردازش است.", status=409))
            # The existing report generator checks source permissions again,
            # requires this unit and records deterministic, local-only findings.
            report = generate_report(request.user, unit, code)
            command.report = report
            command.status = "draft_ready"
            command.full_clean()
            command.save(update_fields=("report", "status", "updated_at"))
            AuditEvent.objects.create(
                actor=request.user,
                action="ecosystem_master_command_draft",
                target=f"MasterCommand:{command.pk}",
                detail={
                    "unit_id": unit.pk, "assistant_code": code,
                    "report_id": report.pk,
                    "no_external_side_effects": True,
                    "requires_human_review": True,
                },
            )
        return no_cache(redirect("enterprise_portal:ecosystem_hub:report", pk=report.pk))

    visible = MasterCommand.objects.filter(unit=unit).select_related(
        "issued_by", "report",
    ).order_by("-created_at", "-pk")[:40]
    return page(request, "master_command", {
        "selected_unit": unit, "units": units,
        "commands": visible,
        "specialists": specialists,
        "allowed_codes": eligible,
        "request_key": uuid4(),
        "section": "master_command",
    })
