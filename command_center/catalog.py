"""Bilingual navigation and agent capability catalog. No execution side effects."""
MODULES = (
    ("overview", "داشبورد فرماندهی", "Command Dashboard"),
    ("factory", "مدیریت کارخانه", "Factory Management"),
    ("sites", "مدیریت سایت‌ها", "Website Management"),
    ("master", "مستر ایجنت", "Master Agent"),
    ("agents", "مدیریت ایجنت‌ها", "Agent Control Center"),
    ("bots", "مدیریت ربات‌ها", "Bot Management"),
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
    "sites": "/company/",
    "projects": "/research/projects/",
    "staff": "/staff/",
    "agents": "/staff/command-center/mpw-agents/",
    "content": "/staff/command-center/mpw-operations/",
    "finance": "/staff/command-center/accounting/",
    "approvals": "#staff-approvals",
    "infrastructure": "#staff-infrastructure",
}

AGENT_SETTINGS = (
    ("mission", "مأموریت", "Mission"),
    ("permissions", "سطح اختیار", "Permissions"),
    ("schedule", "برنامه فعالیت", "Schedule"),
    ("resources", "منابع مجاز", "Allowed Resources"),
    ("model_budget", "مدل و بودجه", "Model & Budget"),
    ("quality", "کنترل کیفیت", "Quality Control"),
    ("collaboration", "همکاری ایجنت‌ها", "Agent Collaboration"),
    ("publishing", "انتشار", "Publishing"),
    ("recovery", "مدیریت خطا", "Error Recovery"),
    ("performance", "گزارش عملکرد", "Performance"),
)
def localized(rows, lang):
    if lang not in ("fa", "en"):
        raise ValueError("Unsupported language")
    index = 1 if lang == "fa" else 2
    return [{"id": row[0], "label": row[index], "url": MODULE_URLS.get(row[0], ""), "connected": row[0] in {"overview", "sites", "projects", "staff", "agents", "content", "approvals", "infrastructure", "finance"}} for row in rows]
