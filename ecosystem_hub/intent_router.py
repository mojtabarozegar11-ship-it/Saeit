"""Conservative, offline Persian/English intent routing for Zomorod's private desk.

No third-party service sees the instruction. A routing match chooses only an
authorized deterministic read-only specialist; ambiguous or unknown requests
must not silently execute a different assistant.
"""
import re
import unicodedata

from .catalog import CATALOG


ROUTER_VERSION = "keyword-scope-v1"

# Distinct subject labels, not natural-language execution directives.
# Keep phrases specific: fallback to an explicit human selection on ties.
SUBJECTS = {
    "marketing-performance": (
        "بازاریابی", "تبلیغات", "تبلیغاتی", "کمپین", "سرنخ", "قیف فروش",
        "marketing", "campaign", "ads", "advertising",
    ),
    "production-scheduling": (
        "سفارش تولید", "برنامه تولید", "تولید", "کارخانه", "production", "factory",
    ),
    "quality-inspector": (
        "کنترل کیفیت", "بازرسی کیفیت", "کیفیت", "quality control", "qc",
    ),
    "inventory-alerts": (
        "انبار", "موجودی", "نقطه سفارش", "inventory", "stock level",
    ),
    "procurement-planner": (
        "تامین مواد", "تأمین مواد", "تدارکات", "خرید مواد", "procurement", "purchasing",
    ),
    "risk-analyst": ("ریسک", "خطرات", "risk", "compliance"),
    "budget-controller": ("بودجه", "budget"),
    "ledger-reviewer": ("حسابداری", "دفتر کل", "سند حسابداری", "ledger", "accounting"),
    "receivables": ("مطالبات", "دریافتنی", "وصول مطالبات", "receivables"),
    "payables": ("پرداختنی", "بدهی تجاری", "payables"),
    "executive-brief": (
        "مدیریت کل", "گزارش مدیریتی", "خلاصه مدیریتی",
        "کسب و کار", "business overview", "executive brief",
    ),
    "agent-supervisor": (
        "مسترایجنت", "ایجنت", "ربات", "اتوماسیون", "چرخه ساعتی", "agent", "automation",
    ),
    "site-qa": ("سایت", "وبسایت", "وب سایت", "website", "web health"),
    "performance-coach": ("وظایف", "کارهای معوق", "تسک", "tasks", "backlog"),
    "project-manager": ("پروژه", "مدیریت پروژه", "project"),
    "maintenance-planner": ("تعمیرات", "نگهداری ماشین آلات", "maintenance"),
}


def normalize(value):
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = text.replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ")
    return re.sub(r"[^\w]+", " ", text, flags=re.UNICODE).strip()


def route_instruction(instruction, permitted_codes):
    """Return a verifiable routing decision; never use permissions to hide a
    higher-scoring unauthorized subject and incorrectly choose another engine.
    """
    value = " " + normalize(instruction) + " "
    scores = {}
    for code, phrases in SUBJECTS.items():
        if code not in CATALOG or not CATALOG[code]["handler"]:
            continue
        score = sum(
            len(normalize(phrase).split())
            for phrase in phrases
            if " " + normalize(phrase) + " " in value
        )
        if score:
            scores[code] = score

    if not scores:
        return {"status": "unmatched", "code": None, "candidates": [],
                "version": ROUTER_VERSION}
    highest = max(scores.values())
    leaders = sorted(code for code, score in scores.items() if score == highest)
    if len(leaders) != 1:
        return {"status": "ambiguous", "code": None, "candidates": leaders,
                "version": ROUTER_VERSION}
    chosen = leaders[0]
    if chosen not in permitted_codes:
        return {"status": "unauthorized", "code": None, "candidates": [],
                "version": ROUTER_VERSION}
    return {"status": "matched", "code": chosen, "candidates": [chosen],
            "version": ROUTER_VERSION}
