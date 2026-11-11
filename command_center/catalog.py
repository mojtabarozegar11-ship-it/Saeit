"""Bilingual navigation for one bot and its internal capability modules."""

from ava_core.identity import BOT_ID

MODULES = (
    ("overview", "داشبورد فرماندهی", "Command Dashboard"),
    ("factory", "مدیریت کارخانه", "Factory Management"),
    ("sites", "مدیریت سایت‌ها", "Website Management"),
    ("unified_bot", BOT_ID + " — فرماندهی یکپارچه", BOT_ID + " — Unified Command"),
    ("content", "استودیوی محتوا", "Content Studio"),
    ("publishing", "مدیریت انتشار", "Publishing Center"),
    ("seo", "مدیریت سئو", "SEO Management"),
    ("diagnostics", "عیب‌یابی هوشمند", "Intelligent Diagnostics"),
    ("projects", "مدیریت پروژه", "Project Management"),
    ("analytics", "گزارش‌های تحلیلی", "Analytics & Reports"),
    ("finance", "دفتر مالی و حسابداری", "Accounting Ledger"),
    ("infrastructure", "زیرساخت", "Infrastructure"),
    ("staff", "پرسنل و دسترسی‌ها", "Staff & Permissions"),
    ("audit", "سوابق عملیات", "Activity Audit"),
    ("approvals", "مرکز تأیید عملیات", "Approval Center"),
    ("alerts", "هشدارها", "Alerts & Incidents"),
    ("settings", "تنظیمات سامانه", "System Settings"),
)
MODULE_URLS = {
    "overview": "/staff/command-center/",
    "unified_bot": "/staff/command-center/",
    "sites": "/company/",
    "projects": "/research/projects/",
    "staff": "/staff/",
    "content": "#staff-content",
    "finance": "/staff/command-center/accounting/",
    "approvals": "#staff-approvals",
    "infrastructure": "#staff-infrastructure",
    "analytics": "#staff-summary",
}

AGENT_SETTINGS = (
    ("mission", "مأموریت", "Mission"),
    ("permissions", "سطح اختیار", "Permissions"),
    ("schedule", "برنامه فعالیت", "Schedule"),
    ("resources", "منابع مجاز", "Allowed Resources"),
    ("model_budget", "مدل و بودجه", "Model & Budget"),
    ("quality", "کنترل کیفیت", "Quality Control"),
    ("collaboration", "هماهنگی ماژول‌های داخلی", "Internal Module Coordination"),
    ("publishing", "انتشار", "Publishing"),
    ("recovery", "مدیریت خطا", "Error Recovery"),
    ("performance", "گزارش عملکرد", "Performance"),
)


def localized(rows, lang):
    if lang not in ("fa", "en"):
        raise ValueError("Unsupported language")
    index = 1 if lang == "fa" else 2
    connected = {
        "overview", "sites", "projects", "staff", "unified_bot",
        "content", "approvals", "infrastructure", "finance", "analytics",
    }
    return [
        {"id": row[0], "label": row[index],
         "url": MODULE_URLS.get(row[0], ""),
         "connected": row[0] in connected}
        for row in rows
    ]
