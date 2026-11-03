"""Opt-in management scheduler: read-only reports and capped internal follow-ups.

Usage:
  python manage.py run_ecosystem_assistants                    # preview only
  ECOSYSTEM_SCHEDULED_ANALYSIS_ENABLED=True python manage.py run_ecosystem_assistants --commit

An external, authorized scheduler must separately launch this command.
No automatic cron installation, outbound requests or hidden external effects.\nOnly explicitly enabled rules can create internal tasks for human review.
"""
from calendar import monthrange
import json
from datetime import date, timedelta

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from enterprise_portal.models import AuditEvent
from ecosystem_hub.analysis import generate_report
from ecosystem_hub.catalog import CATALOG
from ecosystem_hub.followups import create_followups
from ecosystem_hub.models import ProposedAutomation
from ecosystem_hub.task_watch import watch_for_unit


MAX_BATCH = 100


def is_due(rule, *, now=None):
    """Hourly elapsed-time semantics; longer cadences follow the local calendar."""
    if not rule.active or not rule.requires_human_review:
        return False
    if rule.assistant_code not in CATALOG or not CATALOG[rule.assistant_code]["handler"]:
        return False
    if rule.last_checked_at is None:
        return True
    now = now or timezone.now()
    if rule.cadence == "hourly":
        return now >= rule.last_checked_at + timedelta(hours=1)
    current = timezone.localtime(now).date()
    last = timezone.localtime(rule.last_checked_at).date()
    if rule.cadence == "daily":
        return current > last
    if rule.cadence == "weekly":
        return current >= last + timedelta(days=7)
    if rule.cadence == "monthly":
        year = last.year + (last.month == 12)
        month = last.month % 12 + 1
        anniversary = date(year, month, min(last.day, monthrange(year, month)[1]))
        return current >= anniversary
    return False


@transaction.atomic
def process_rule(rule_id, *, now):
    """Atomic compare-and-update: never duplicate a due run across workers."""
    rule = ProposedAutomation.objects.select_for_update().select_related("owner", "unit").get(pk=rule_id)
    if not is_due(rule, now=now):
        return None
    actor = rule.owner
    if not actor.is_active or not actor.is_staff:
        raise PermissionDenied("صاحب برنامه باید کاربر فعال دارای مجوز باشد.")
    matched = ProposedAutomation.objects.filter(
        pk=rule.pk, active=True, requires_human_review=True,
        last_checked_at=rule.last_checked_at,
    ).update(last_checked_at=now)
    if matched != 1:
        return None
    # generate_report verifies both unit membership and all handler's source
    # permissions. On any exception this transaction rolls back claimed time.
    report = generate_report(actor, rule.unit, rule.assistant_code)
    followups = create_followups(rule, report, now=now)
    detail = {"unit_id": rule.unit_id, "automation_id": rule.pk,
              "method": "read-only deterministic", "no_external_side_effects": True}
    detail["followups"] = followups
    # generate_report has already checked view_worktask for these handler types.
    # Record an auditable due-date snapshot, never change task status or send.
    if CATALOG[rule.assistant_code]["handler"] in ("tasks", "executive"):
        detail["task_watch"] = watch_for_unit(
            rule.unit, actor=actor, today=timezone.localdate(now), limit=1,
        )["counts"]
    AuditEvent.objects.create(
        actor=actor,
        action="ecosystem_scheduled_draft",
        target=f"AssistantRun:{report.pk}",
        detail=detail,
    )
    return report


class Command(BaseCommand):
    help = ("اجرای کنترل‌شده گزارش‌های داخلی و پیگیری‌های انسانیِ اختیاری؛"
            " هیچ پرداخت، پیام یا انتشاری انجام نمی‌شود.")

    def add_arguments(self, parser):
        parser.add_argument("--commit", action="store_true", help="ثبت پیش‌نویس‌ها پس از مجوز صریح")
        parser.add_argument("--unit", default=None, help="کد واحد سازمانی (اختیاری)")
        parser.add_argument("--limit", type=int, default=25, help="حداکثر برنامه‌های بررسی‌شده، ۱ تا ۱۰۰")
        parser.add_argument("--json-receipt", action="store_true", help="رسید شمارشی ماشین‌خوان برای چرخهٔ مدیریت")
        parser.add_argument("--strict", action="store_true", help="خروج ناموفق در صورت رد هر برنامه")

    def handle(self, *args, **options):
        if options["limit"] < 1 or options["limit"] > MAX_BATCH:
            raise CommandError("حد بررسی باید بین ۱ و ۱۰۰ باشد.")
        commit = bool(options["commit"])
        if commit and not getattr(settings, "ECOSYSTEM_SCHEDULED_ANALYSIS_ENABLED", False):
            raise CommandError("اجرای زمان‌بندی در تنظیمات سرور فعال نشده است.")
        qs = ProposedAutomation.objects.filter(
            active=True, requires_human_review=True,
        ).select_related("owner", "unit").order_by("pk")
        if options["unit"]:
            qs = qs.filter(unit__code=options["unit"])
        now = timezone.now()
        checked = scheduled = skipped = errors = 0
        drafts_created = followup_tasks_created = 0
        for rule in qs[:options["limit"]]:
            checked += 1
            if not is_due(rule, now=now):
                skipped += 1
                continue
            if not commit:
                scheduled += 1
                self.stdout.write(f"PREVIEW id={rule.pk} unit={rule.unit.code} assistant={rule.assistant_code} auto_tasks={int(rule.auto_create_tasks)}")
                continue
            try:
                report = process_rule(rule.pk, now=now)
            except (PermissionDenied, ValidationError) as error:
                errors += 1
                self.stderr.write(f"DENIED rule_id={rule.pk} reason={type(error).__name__}")
            else:
                if report:
                    scheduled += 1
                    drafts_created += 1
                    followup_count = report.agent_followups.count()
                    followup_tasks_created += followup_count
                    self.stdout.write(f"DRAFT_CREATED rule_id={rule.pk} report_id={report.pk} followups={followup_count}")
                else:
                    skipped += 1
        self.stdout.write(
            f"ECOSYSTEM_ANALYSIS commit={int(commit)} checked={checked} "
            f"due_or_created={scheduled} skipped={skipped} errors={errors}"
        )
        if options["json_receipt"]:
            # Expose only counters and operational state: no private financial,
            # employee, customer, instruction or report content reaches CI logs.
            receipt = {
                "schema_version": 1,
                "source": "zomorod_office_scheduler",
                "mode": "commit" if commit else "preview",
                "rules_checked": checked,
                "due_or_created": scheduled,
                "drafts_created": drafts_created,
                "human_followups_created": followup_tasks_created,
                "skipped": skipped,
                "errors": errors,
                "outcome": "partial_failure" if errors else "ok",
                "external_actions_executed": False,
            }
            self.stdout.write(
                "ECOSYSTEM_CYCLE_RECEIPT_JSON=" +
                json.dumps(receipt, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            )
        if options["strict"] and errors:
            raise CommandError(f"ECOSYSTEM_CYCLE_INCOMPLETE errors={errors}")
