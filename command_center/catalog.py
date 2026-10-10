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
    ("finance", "امور مالی", "Financial Management"),
    ("infrastructure", "زیرساخت", "Infrastructure"),
    ("staff", "پرسنل و دسترسی‌ها", "Staff & Permissions"),
    ("audit", "سوابق عملیات", "Activity Audit"),
    ("approvals", "مرکز تأیید عملیات", "Approval Center"),
    ("alerts", "هشدارها", "Alerts & Incidents"),
    ("settings", "تنظیمات سامانه", "System Settings"),
)
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
    return [{"id": row[0], "label": row[index], "connected": row[0] in {"overview", "agents", "content", "approvals", "infrastructure"}} for row in rows]
