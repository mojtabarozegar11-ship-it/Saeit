"""Company Activity Intelligence Agent.

Daily, evidence-bound reporting from real Company activity records.
No fabricated activities, projects, outcomes or financial claims.
"""
from datetime import timedelta
from django.utils import timezone
from .models import Agent, NewsletterStory

AGENT_CODE = "company-activity-intelligence"
REPORT_TYPES = ("DAILY_DIGEST", "ACTIVITY_ANALYSIS", "TREND_ANALYSIS", "UNIT_ANALYSIS", "PROJECT_ANALYSIS", "EXECUTIVE_BRIEF")
PIPELINE = ("COLLECT_COMPANY_ACTIVITIES", "DEDUPLICATE", "CLASSIFY", "ANALYZE", "CROSS_LINK", "FACT_CHECK", "DRAFT", "OWNER_APPROVAL", "PUBLISH")
REPORT_TITLES = {
    "DAILY_DIGEST": "گزارش روزانه فعالیت شرکت",
    "ACTIVITY_ANALYSIS": "تحلیل فعالیت‌های ثبت‌شده شرکت",
    "TREND_ANALYSIS": "تحلیل روند فعالیت‌های شرکت",
    "UNIT_ANALYSIS": "تحلیل واحدهای فعال شرکت",
    "PROJECT_ANALYSIS": "تحلیل پروژه‌های ثبت‌شده شرکت",
    "EXECUTIVE_BRIEF": "خلاصه مدیریتی فعالیت‌های شرکت",
}


def source_activities(days=1):
    since = timezone.now() - timedelta(days=max(1, days))
    return NewsletterStory.objects.filter(company_activity_kind="activity", company_activity_content__isnull=False, created_at__gte=since).exclude(company_activity_content="").order_by("created_at")


def activity_snapshot(days=1):
    rows = list(source_activities(days))
    units, projects = {}, {}
    for row in rows:
        unit = row.company_unit_title or "بدون واحد مشخص"
        units[unit] = units.get(unit, 0) + 1
        if row.company_project_title:
            projects[row.company_project_title] = projects.get(row.company_project_title, 0) + 1
    return {"source_count": len(rows), "units": units, "projects": projects, "source_ids": [row.pk for row in rows]}


def report_contract():
    return {"agent": AGENT_CODE, "mission": "تحلیل روزانه فعالیت‌های واقعی ثبت‌شده شرکت", "report_types": list(REPORT_TYPES), "pipeline": list(PIPELINE), "source_of_truth": "NewsletterStory.company_activity_*", "fabrication_forbidden": True, "publication_requires_owner_approval": True, "public_numeric_financial_claims": False}


def ensure_agent():
    agent, _ = Agent.objects.get_or_create(code=AGENT_CODE, defaults={"name": "Company Activity Intelligence Agent", "mission": "تولید گزارش و تحلیل روزانه از فعالیت‌های واقعی صفحه شرکت؛ بدون جعل فعالیت.", "risk_level": "low", "active": True})
    if not agent.active:
        agent.active = True
        agent.save(update_fields=["active", "updated_at"])
    return agent


def build_report_inputs(days=1):
    snap = activity_snapshot(days)
    if not snap["source_count"]:
        return None
    return {"agent": AGENT_CODE, "window_days": days, "source_activity_ids": snap["source_ids"], "activity_count": snap["source_count"], "unit_distribution": snap["units"], "project_distribution": snap["projects"], "instruction": "فقط بر اساس این رکوردها گزارش بساز؛ هیچ فعالیت، پروژه، نتیجه یا عددی خارج از منابع اضافه نشود."}


def build_report_content(report_type, rows, snapshot):
    """Create an evidence-bound Persian draft without inventing facts."""
    if not rows:
        return "منبع واقعی برای این گزارش ثبت نشده است؛ انتشار مسدود است."
    lines = [REPORT_TITLES[report_type], "", "دامنه: فعالیت‌های واقعی ثبت‌شده شرکت در بازه روزانه.", "اصل اعتبار: این متن فقط از رکوردهای فعالیت شرکت ساخته شده و ادعای خارج از منبع ندارد.", ""]
    if report_type == "DAILY_DIGEST":
        lines.append("فعالیت‌های ثبت‌شده:")
        lines.extend(f"• {r.title} — واحد: {r.company_unit_title or 'بدون واحد مشخص'} — وضعیت: {r.company_activity_status or 'ثبت نشده'}" for r in rows)
    elif report_type == "ACTIVITY_ANALYSIS":
        lines.append(f"در این بازه {len(rows)} رکورد فعالیت واقعی برای تحلیل در دسترس است.")
        for r in rows:
            lines.append(f"• {r.title}: {r.summary or r.company_activity_content[:240]}")
    elif report_type == "TREND_ANALYSIS":
        lines.append("الگوی مشاهده‌شده بر اساس توزیع ثبت‌هاست و به‌عنوان پیش‌بینی آینده ارائه نمی‌شود.")
        lines.extend(f"• {name}: {count} فعالیت ثبت‌شده" for name, count in snapshot["units"].items())
    elif report_type == "UNIT_ANALYSIS":
        lines.append("توزیع فعالیت بر اساس واحدهای ثبت‌شده:")
        lines.extend(f"• {name}: {count} رکورد" for name, count in snapshot["units"].items())
    elif report_type == "PROJECT_ANALYSIS":
        if snapshot["projects"]:
            lines.append("پروژه‌های ثبت‌شده در فعالیت‌ها:")
            lines.extend(f"• {name}: {count} فعالیت مرتبط" for name, count in snapshot["projects"].items())
        else:
            lines.append("در رکوردهای این بازه پروژه مادری ثبت نشده است.")
    elif report_type == "EXECUTIVE_BRIEF":
        lines.append("خلاصه مدیریتی مبتنی بر داده ثبت‌شده:")
        lines.append(f"• تعداد فعالیت‌های قابل استناد: {len(rows)}")
        lines.append(f"• واحدهای دارای ثبت فعالیت: {len(snapshot['units'])}")
        lines.append(f"• پروژه‌های دارای ثبت: {len(snapshot['projects'])}")
        lines.append("• تصمیم یا نتیجه جدید از این داده‌ها استنباط نشده و برای هر ادعای جدید نیاز به منبع مستقل وجود دارد.")
    lines.extend(["", "منابع داخلی: شناسه رکوردهای فعالیت شرکت = " + ", ".join(str(r.pk) for r in rows), "وضعیت انتشار: نیازمند بازبینی و تأیید مالک."])
    return "\n".join(lines)
