from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.company_activity_agent import REPORT_TYPES, REPORT_TITLES, build_report_inputs, build_report_content, ensure_agent, source_activities
from core.company_activity_models import CompanyActivityAgentPlan, CompanyActivityReport


class Command(BaseCommand):
    help = "Queue a daily Company Activity Intelligence Agent report set."

    def handle(self, *args, **options):
        now = timezone.now()
        plan, _ = CompanyActivityAgentPlan.objects.get_or_create(
            code="company-activity-intelligence",
            defaults={
                "title": "Company Activity Intelligence Agent",
                "mission": "گزارش و تحلیل روزانه فعالیت‌های واقعی صفحه شرکت.",
                "cadence_hours": 24,
                "reports_per_day": 6,
                "active": True,
                "require_owner_approval": True,
                "next_run_at": now,
            },
        )
        ensure_agent()
        if not plan.active or (plan.next_run_at and plan.next_run_at > now):
            self.stdout.write("COMPANY_ACTIVITY_AGENT=WAIT")
            return
        inputs = build_report_inputs(1)
        if not inputs:
            self.stdout.write("COMPANY_ACTIVITY_AGENT=NO_REAL_ACTIVITY")
            plan.last_run_at = now
            plan.next_run_at = now + timedelta(hours=plan.cadence_hours)
            plan.save(update_fields=["last_run_at", "next_run_at", "updated_at"])
            return
        period_start = now - timedelta(days=1)
        rows = list(source_activities(1))
        created = 0
        for report_type in REPORT_TYPES[:plan.reports_per_day]:
            report, made = CompanyActivityReport.objects.get_or_create(
                plan=plan,
                report_type=report_type,
                period_start=period_start,
                defaults={
                    "title": REPORT_TITLES[report_type],
                    "period_end": now,
                    "source_activity_ids": inputs["source_activity_ids"],
                    "source_count": inputs["activity_count"],
                    "content": build_report_content(report_type, rows, inputs),
                    "approval_required": plan.require_owner_approval,
                    "status": "review",
                },
            )
            if made:
                created += 1
            elif report.source_activity_ids != inputs["source_activity_ids"] and report.status not in ("approved", "published"):
                report.source_activity_ids = inputs["source_activity_ids"]
                report.source_count = inputs["activity_count"]
                report.period_end = now
                report.content = build_report_content(report_type, rows, inputs)
                report.save(update_fields=["source_activity_ids", "source_count", "period_end", "content", "updated_at"])
        plan.last_run_at = now
        plan.next_run_at = now + timedelta(hours=plan.cadence_hours)
        plan.save(update_fields=["last_run_at", "next_run_at", "updated_at"])
        self.stdout.write(f"COMPANY_ACTIVITY_AGENT=QUEUED REPORTS={created} SOURCES={inputs['activity_count']}")
