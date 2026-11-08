"""Deterministic, database-backed continuity checks for unattended operations.

This worker never sends messages, handles credentials, publishes, spends money,
posts journal entries, or decides approvals. It manages only its own WorkItems.
"""
from datetime import timedelta

from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from accounting.models import JournalEntry
from .models import CommandRequest, CycleReport, LedgerAuditEvent, WorkItem


# A report is evidence of a recorded action, not proof of external revenue.
STREAMS = {
    "A": ("books", "mojplaywin"),
    "B": ("research",),
    "C": ("mojcoin", "trade"),
    "D": ("zomorod-web",),
    "E": ("management", "factory"),
}
AUTO_SOURCE = "continuity_worker"
MAX_ITEMS_PER_CLASS = 100
SAFE_READ_ONLY_COMMANDS = {"گزارش", "وضعیت", "پایش", "ممیزی", "بررسی", "تعداد", "سلامت"}


def _outstanding(now, horizon):
    """Describe real database gaps without claiming services ran or revenue arrived."""
    cutoff = now - horizon
    desired = {}
    stream_status = {}
    for label, project_keys in STREAMS.items():
        evidence = (
            CycleReport.objects.filter(project_key__in=project_keys, created_at__gte=cutoff)
            .exclude(evidence="").exclude(result="").exclude(measure="")
            .order_by("-created_at").first()
        )
        stream_status[label] = {
            "has_recent_record": evidence is not None,
            "last_record_id": evidence.pk if evidence else None,
        }
        if evidence is None:
            desired[f"stream:{label}"] = {
                "title": f"چرخه {label}: سند اقدام اخیر در میز مدیریت موجود نیست",
                "description": (
                    "در بازه پایش، گزارش دارای اقدام، نتیجه، سنجه و شاهد در دفتر ثبت نشده است. "
                    "این نشانهٔ نبود سند در میز است؛ نه اثبات توقف سرویس یا نبود فروش. "
                    "ابتدا شواهد واقعی را از منبع مجاز ثبت کنید."
                ),
                "priority": "high",
                "assignee_id": None,
                "project_id": None,
            }

    overdue = list(
        WorkItem.objects.filter(due_at__lt=now, status__in=("open", "in_progress", "blocked"))
        .exclude(source_type=AUTO_SOURCE)
        .order_by("due_at", "pk")[:MAX_ITEMS_PER_CLASS]
    )
    for item in overdue:
        desired[f"overdue:{item.pk}"] = {
            "title": f"پیگیری کار معوق #{item.pk}: {item.title}"[:240],
            "description": (
                f"کار اصلی #{item.pk} از سررسید عبور کرده است. "
                "این مورد صرفاً هشدار داخلی است؛ هیچ اقدام مالی یا خارجی انجام نشده."
            ),
            "priority": "high",
            "assignee_id": item.assignee_id,
            "project_id": item.project_id,
        }

    # Posted journal entries must be balanced. A mismatch is flagged, never repaired automatically.
    malformed = list(
        JournalEntry.objects.filter(status=JournalEntry.Status.POSTED)
        .annotate(line_count=Count("lines"), debits=Sum("lines__debit"), credits=Sum("lines__credit"))
        .filter(Q(line_count__lt=2) | Q(debits__isnull=True) | Q(debits__lte=0) | ~Q(debits=F("credits")))
        .order_by("pk")[:MAX_ITEMS_PER_CLASS]
    )
    for entry in malformed:
        desired[f"journal:{entry.pk}"] = {
            "title": f"مغایرت سند حسابداری قطعی #{entry.pk}"[:240],
            "description": (
                f"مرجع: {entry.reference}. ردیف‌ها: {entry.line_count}؛ "
                f"بدهکار: {entry.debits or 0}؛ بستانکار: {entry.credits or 0}. "
                "فقط تشخیص داده شد؛ هیچ سند مالی دستکاری نشده است."
            ),
            "priority": "urgent",
            "assignee_id": None,
            "project_id": None,
        }
    return desired, stream_status, len(overdue), len(malformed)


def run_continuity_cycle(*, actor=None, apply=False, now=None, horizon_hours=24):
    """Run once from cron/systemd or cPanel cron, independent of GitHub Actions.

    Applying requires a named, active staff operator. The transaction locks that
    operator's row to serialize two simultaneous workers using the same actor.
    """
    if not 1 <= horizon_hours <= 168:
        raise ValueError("horizon_hours must be between 1 and 168")
    if apply and (actor is None or not actor.pk or not actor.is_active or not actor.is_staff):
        raise ValueError("--apply requires an existing active staff actor")
    now = now or timezone.now()
    horizon = timedelta(hours=horizon_hours)

    with transaction.atomic():
        if apply:
            # A single lock prevents duplicate tickets across concurrent invocations.
            type(actor).objects.select_for_update().get(pk=actor.pk)
        desired, streams, overdue_count, malformed_count = _outstanding(now, horizon)
        existing = list(WorkItem.objects.filter(source_type=AUTO_SOURCE).order_by("pk"))
        by_key = {}
        for item in existing:
            by_key.setdefault(item.source_id, item)
        created = reopened = resolved = 0
        for key, detail in desired.items():
            item = by_key.get(key)
            if item is None:
                created += 1
                if apply:
                    row = WorkItem.objects.create(
                        source_type=AUTO_SOURCE, source_id=key, created_by=actor,
                        assignee_id=detail["assignee_id"] or actor.pk,
                        project_id=detail["project_id"],
                        title=detail["title"], description=detail["description"],
                        priority=detail["priority"], status="open",
                    )
                    LedgerAuditEvent.objects.create(
                        action="create", entity="work_item", entity_id=str(row.pk),
                        summary="Continuity incident opened", evidence=key, actor=actor,
                    )
            elif item.status == "done":
                reopened += 1
                if apply:
                    item.status = "open"
                    item.resolution_reference = ""
                    item.completed_at = None
                    item.save(update_fields=("status", "resolution_reference", "completed_at", "updated_at"))
                    LedgerAuditEvent.objects.create(
                        action="verify", entity="work_item", entity_id=str(item.pk),
                        summary="Continuity incident reopened", evidence=key, actor=actor,
                    )
        for key, item in by_key.items():
            if key not in desired and item.status != "done":
                resolved += 1
                if apply:
                    item.status = "done"
                    item.completed_at = now
                    item.resolution_reference = ("continuity:cleared:" + key)[:120]
                    item.save(update_fields=("status", "completed_at", "resolution_reference", "updated_at"))
                    LedgerAuditEvent.objects.create(
                        action="resolve", entity="work_item", entity_id=str(item.pk),
                        summary="Continuity condition cleared by database evidence", evidence=key,
                        actor=actor,
                    )
        # Only explicit read-only queries are processed. Unrecognized or sensitive
        # instructions stay pending; viewing the dashboard can never execute them.
        commands = list(
            CommandRequest.objects.filter(status="pending", read_only=True)
            .order_by("created_at", "pk")[:MAX_ITEMS_PER_CLASS]
        )
        safe_commands = [row for row in commands if row.command.strip() in SAFE_READ_ONLY_COMMANDS]
        if apply:
            for row in safe_commands:
                row.status = "executed"
                row.executed_at = now
                row.result = (
                    f"خواندن واقعی پایگاه داده: {len(desired)} شرط نیازمند پیگیری؛ "
                    f"{overdue_count} کار معوق؛ {malformed_count} سند قطعی نامتوازن. "
                    "هیچ اقدام خارجی انجام نشد."
                )
                row.save(update_fields=("status", "executed_at", "result"))
                LedgerAuditEvent.objects.create(
                    action="verify", entity="command", entity_id=str(row.pk),
                    summary="Strictly read-only database inspection executed",
                    evidence=f"command:{row.pk}", actor=actor,
                )
        return {
            "mode": "apply" if apply else "read_only",
            "captured_at": now.isoformat(),
            "streams": streams,
            "overdue_work_checked": overdue_count,
            "unbalanced_posted_journals_checked": malformed_count,
            "open_conditions": len(desired),
            "work_items_created": created,
            "work_items_reopened": reopened,
            "work_items_resolved": resolved,
            "safe_read_only_commands": len(safe_commands),
            "external_actions": 0,
            "payments": 0,
            "messages_sent": 0,
        }
