"""Bounded, opt-in creation of *human* follow-up tasks from agent warnings.

Only a short allowlist of unit-scoped internal source references is eligible.
No message delivery, financial posting, publication or hardware control.
"""
from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.utils import timezone

from enterprise_portal.models import AuditEvent, WorkTask
from .access import require_unit
from .catalog import CATALOG
from .models import AgentFollowUp


MAX_NEW_TASKS_PER_CYCLE = 5
MAX_UNRESOLVED_TASKS_PER_RULE = 40
SOURCE_MODELS = frozenset({
    "CommercialDocument", "InventoryItem", "ProductionOrder",
    "MaterialRequirement", "ManagementRisk", "MaintenanceTicket",
    "QualityInspection", "Campaign", "Publication",
})


def _warning_sources(report):
    """Keep a single warning per stable, known source; never recurse on WorkTask."""
    seen = set()
    for finding in report.findings[:30]:
        if not isinstance(finding, dict) or finding.get("severity") not in ("warning", "critical"):
            continue
        source = finding.get("source")
        if not isinstance(source, str) or len(source) > 160:
            continue
        model, separator, identifier = source.partition(":")
        if not separator or model not in SOURCE_MODELS or not identifier.isascii() or not identifier.isdecimal():
            continue
        if int(identifier) < 1 or source in seen:
            continue
        seen.add(source)
        yield source, finding["severity"]


def create_followups(rule, report, *, now=None):
    """Run within the locked scheduler transaction, after source ACL checks.

    The rule flag alone is never authorization: both task permissions and a
    write-capable membership are checked independently.
    """
    outcome = {"created": 0, "already_tracked": 0, "capacity_skipped": 0}
    if not rule.auto_create_tasks:
        return outcome
    actor = rule.owner
    if not (actor.is_superuser or (
        actor.has_perm("enterprise_portal.add_worktask") and
        actor.has_perm("enterprise_portal.view_worktask")
    )):
        raise PermissionDenied("برای ایجاد خودکار مأموریت داخلی، مجوز ثبت و مشاهده وظایف لازم است.")
    require_unit(actor, rule.unit, write=True)
    if (report.unit_id != rule.unit_id or
            report.requested_by_id != actor.pk or
            report.assistant_code != rule.assistant_code):
        raise PermissionDenied("گزارش دستیار با مالک یا واحد برنامه تطابق ندارد.")

    unresolved = AgentFollowUp.objects.filter(rule=rule).exclude(task__status="done").count()
    allowed = max(0, min(MAX_NEW_TASKS_PER_CYCLE,
                         MAX_UNRESOLVED_TASKS_PER_RULE - unresolved))
    due = timezone.localdate(now) + timedelta(days=1) if now else timezone.localdate() + timedelta(days=1)
    for source, severity in _warning_sources(report):
        if AgentFollowUp.objects.filter(rule=rule, source_ref=source).exists():
            outcome["already_tracked"] += 1
            continue
        if outcome["created"] >= allowed:
            outcome["capacity_skipped"] += 1
            continue
        task = WorkTask(
            unit=rule.unit,
            assigned_to=actor,
            created_by=actor,
            title=("پیگیری هشدار " + CATALOG[rule.assistant_code]["title"])[:240],
            description=(
                f"پیگیری داخلی گزارش AssistantRun:{report.pk}، مرجع {source}. "
                "خلاصه و شواهد تخصصی فقط در گزارش خصوصی دستیار است. "
                "این مأموریت هیچ اقدام خارجی را خودکار انجام نمی‌دهد."
            ),
            status="todo",
            priority="urgent" if severity == "critical" else "high",
            due_on=due,
        )
        task.full_clean()
        task.save()
        AgentFollowUp.objects.create(
            rule=rule, report=report, task=task, source_ref=source,
        )
        AuditEvent.objects.create(
            actor=actor,
            action="ecosystem_agent_followup_created",
            target=f"WorkTask:{task.pk}",
            detail={
                "unit_id": rule.unit_id, "automation_id": rule.pk,
                "report_id": report.pk, "source_ref": source,
                "requires_human_review": True,
                "no_external_side_effects": True,
            },
        )
        outcome["created"] += 1
    return outcome
