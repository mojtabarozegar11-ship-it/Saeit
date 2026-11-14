"""Realistic service sales cards + bounded release evidence for mojtaba.bot.ai.

No invoices, customer data, pricing claims, lead sends or state changes.
A PASS here is *internal documentation readiness*, NEVER production deployment
or permission to bind a customer or spend funds.
"""
from __future__ import annotations

from copy import deepcopy
from types import MappingProxyType


_SERVICES = {
    "AGR-01": {
        "title_fa": "تحلیل اقتصاد و سودآوری مزرعه",
        "customer": "مدیر مزرعه یا گلخانه",
        "input": "داده سطح، محصول، عملکرد، هزینه و فروش با منشأ مشخص",
        "deliverables": (
            "جدول هزینه متغیر و ثابت", "حاشیه مشارکت و نقطه سربه‌سر",
            "سه سناریو و تحلیل حساسیت", "گزارش تصمیم مشروط",
        ),
        "limitation": "هیچ سود یا عملکردی بدون داده معتبر تضمین نمی‌شود",
    },
    "RS-01": {
        "title_fa": "ممیزی شاخص‌های پژوهش کشاورزی",
        "customer": "مشاور، پژوهشگر یا شرکت",
        "input": "جدول داده و ادعا با منابع و واحد مشخص",
        "deliverables": (
            "شناسنامه شاخص و منبع", "ماتریس ادعا-شاهد",
            "کنترل عدد و حساسیت", "فایل قابل بازبینی",
        ),
        "limitation": "تأیید علّی یا انتشار داوری‌شده تلقی نمی‌شود",
    },
    "RS-02": {
        "title_fa": "ممیزی سناریوی آبیاری",
        "customer": "مدیر منابع آب کشاورزی و گلخانه",
        "input": "سطح، سری زمانی، فرضیات خاک، آب و حسگر",
        "deliverables": (
            "کنترل واحد و موازنه", "مقایسه سناریو",
            "حساسیت به خطای حسگر", "محدودیت اجرای میدانی",
        ),
        "limitation": "صرفه‌جویی قطعی واقعی آب یا افزایش برداشت تضمین نمی‌شود",
    },
    "RS-03": {
        "title_fa": "طراحی آزمایش و بررسی اقتصادی تحقیق",
        "customer": "پژوهشگاه یا شرکت تولیدکننده",
        "input": "فرضیه، تیمار، تکرار، بلوک، محدودیت و متغیر پیامد",
        "deliverables": (
            "پروتکل و طرح تخصیص", "برنامه سنجش و کنترل کیفیت",
            "طرح تحلیل", "برآورد هزینه و محدودیت",
        ),
        "limitation": "هیچ داده ساختگی یا نتیجه معنادار تضمینی تولید نمی‌شود",
    },
    "WEB-01": {
        "title_fa": "طراحی مسیر درخواست و فروش کسب‌وکار",
        "customer": "کسب‌وکار خدماتی و محلی",
        "input": "هویت/مجوز کسب‌وکار، فهرست خدمات، اطلاعات تماس مجاز",
        "deliverables": (
            "صفحه خدمات و فرم", "ثبت پیگیری درخواست",
            "کنترل موبایل و دسترسی", "اندازه‌گیری قیف",
        ),
        "limitation": "بازدید یا رتبه جست‌وجو معادل فروش واقعی نیست",
    },
    "SEO-01": {
        "title_fa": "ممیزی فنی و محتوایی سئو",
        "customer": "وب‌سایت دارای مجوز",
        "input": "نشانی وب مجاز، بازار هدف، داده جست‌وجو و هدف کسب‌وکار",
        "deliverables": (
            "فهرست مشکلات فنی", "شکاف جست‌وجو و محتوا",
            "اولویت اصلاحات", "گزارش شواهد و شاخص‌ها",
        ),
        "limitation": "رتبه یا تعداد مشتری تضمین نمی‌شود",
    },
}
SERVICE_CARDS = MappingProxyType(_SERVICES)
REQUIRED_OFFER_EVIDENCE = (
    "customer_problem_defined",
    "service_delivery_capacity_verified",
    "data_rights_and_privacy_cleared",
    "pricing_costed_and_owner_approved",
    "scope_and_exclusions_documented",
    "contract_and_legal_basis_approved",
    "delivery_method_verified",
    "payment_method_legally_available",
)
_STATES = {True: "PASS", False: "FAIL", None: "UNKNOWN"}


def service_card(service_code: str) -> dict:
    """Return copy: callers cannot alter the master catalogue by mutation."""
    if not isinstance(service_code, str) or service_code not in SERVICE_CARDS:
        raise ValueError("unknown service code")
    record = deepcopy(SERVICE_CARDS[service_code])
    return {"service_code": service_code, **record, "price": None,
            "price_state": "REQUIRES_COSTING_AND_OWNER_APPROVAL",
            "external_sale_enabled": False}


def list_service_cards() -> list[dict]:
    """Original deliverables and limitations only; no fake proof of sale."""
    return [service_card(code) for code in SERVICE_CARDS]


def assess_service_offer(service_code: str, evidence: dict) -> dict:
    """Strict evidence dictionary. No external authorization is produced."""
    service_card(service_code)
    if not isinstance(evidence, dict) or set(evidence) != set(REQUIRED_OFFER_EVIDENCE):
        raise ValueError("all and only required evidence keys must be present")
    for value in evidence.values():
        if value is not None and type(value) is not bool:
            raise ValueError("gate evidence must be bool or None")
    gates = {key: _STATES[evidence[key]] for key in REQUIRED_OFFER_EVIDENCE}
    passed = sum(value == "PASS" for value in gates.values())
    failed = sum(value == "FAIL" for value in gates.values())
    unknown = sum(value == "UNKNOWN" for value in gates.values())
    return {
        "service_code": service_code,
        "agent": "mojtaba.bot.ai",
        "gates": gates,
        "passed": passed,
        "failed": failed,
        "unknown": unknown,
        "total": len(REQUIRED_OFFER_EVIDENCE),
        "source_evidence_percentage": round(passed * 100 / len(REQUIRED_OFFER_EVIDENCE), 2),
        "internal_review_ready": passed == len(REQUIRED_OFFER_EVIDENCE),
        "external_sale_enabled": False,
        "live_settlement": None,
        "live_delivery": None,
        "final_external_commitment_requires_separate_approval": True,
    }
