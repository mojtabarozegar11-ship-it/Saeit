"""Bilingual navigation and capability catalog. Links target existing Django admin surfaces."""
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

# Only map a tile when the corresponding model is registered in Django admin.
# Links are additionally gated by the user's view/change permission in dashboard().
MODULE_ADMIN_ROUTES = {
    "overview": ("command_center_dashboard", ()),
    "sites": ("admin:core_platformpagecontent_changelist", ("core.view_platformpagecontent", "core.change_platformpagecontent")),
    "agents": ("admin:core_agent_changelist", ("core.view_agent", "core.change_agent")),
    "content": ("admin:core_newsletterstory_changelist", ("core.view_newsletterstory", "core.change_newsletterstory")),
    "publishing": ("admin:core_newsletterpublication_changelist", ("core.view_newsletterpublication", "core.change_newsletterpublication")),
    "seo": ("admin:core_blogpage_changelist", ("core.view_blogpage", "core.change_blogpage")),
    "projects": ("admin:core_researchproject_changelist", ("core.view_researchproject", "core.change_researchproject")),
    "staff": ("admin:auth_user_changelist", ("auth.view_user", "auth.change_user")),
    "audit": ("admin:core_auditlog_changelist", ("core.view_auditlog", "core.change_auditlog")),
    "approvals": ("admin:core_approvalrequest_changelist", ("core.view_approvalrequest", "core.change_approvalrequest")),
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


def localized(rows, lang, admin_links=False):
    if lang not in ("fa", "en"):
        raise ValueError("Unsupported language")
    index = 1 if lang == "fa" else 2
    result = []
    for row in rows:
        route = MODULE_ADMIN_ROUTES.get(row[0]) if admin_links else None
        result.append({
            "id": row[0],
            "label": row[index],
            "connected": route is not None,
            "route_name": route[0] if route else "",
            "permissions": route[1] if route else (),
        })
    return result
