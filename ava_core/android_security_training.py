"""Deterministic, fully offline Android security lessons.

This module works exclusively with internally hard-coded synthetic events.
No phone access, network I/O, file reads, permissions, device discovery,
or background execution. It must only be invoked by the authorized bot host.
"""
from __future__ import annotations

from collections.abc import Mapping

LESSONS = (
    {
        "id": "android_permissions",
        "title_fa": "تشخیص درخواست‌های غیرضروری مجوز در اندروید",
        "goal_fa": "تشخیص تفاوت بین مجوز ضروری و دسترسی پرخطر",
    },
    {
        "id": "accessibility_misuse",
        "title_fa": "شناسایی سوءاستفاده از سرویس دسترس‌پذیری",
        "goal_fa": "بازبینی ضرورت مجوز دسترس‌پذیری بدون دسترسی به گوشی واقعی",
    },
    {
        "id": "covert_surveillance_detection",
        "title_fa": "آزمون کشف نشانه‌های نفوذ و جاسوسی مخفیانه",
        "goal_fa": "تشخیص رفتارهای هشداردهنده و انتخاب پاسخ دفاعی بدون دسترسی به گوشی واقعی",
    },
    {
        "id": "synthetic_exfiltration",
        "title_fa": "تحلیل رویداد ساختگی انتقال داده",
        "goal_fa": "تشخیص الگوهای مشکوک در لاگ آموزشی غیرواقعی",
    },
)

# Each event is fabricated; even the app names are laboratory placeholders.
CASES = {
    "normal_notes": (
        ("training.notes", "OPEN_SCREEN", 0),
        ("training.notes", "SAVE_LOCAL_DEMO_NOTE", 0),
    ),
    "overprivileged_app": (
        ("training.overprivileged", "READ_SMS_PERMISSION", 3),
        ("training.overprivileged", "ACCESSIBILITY_PERMISSION", 3),
        ("training.overprivileged", "OVERLAY_PERMISSION", 2),
    ),
    "fictional_covert_surveillance": (
        ("training.fictional_monitor", "UNEXPECTED_PRIVILEGED_PERMISSION", 3),
        ("training.fictional_monitor", "UNRECOGNIZED_BACKGROUND_ACTIVITY", 2),
        ("training.fictional_monitor", "SIMULATED_READ_DEMO_MEDIA_NO_FILES", 3),
        ("training.fictional_monitor", "SIMULATED_DATA_TRANSFER_NO_NETWORK", 4),
    ),
    "fictional_transfer": (
        ("training.fictional", "READ_DEMO_MESSAGES", 3),
        ("training.fictional", "SIMULATED_DATA_TRANSFER_NO_NETWORK", 4),
    ),
}

QUESTIONS = {
    "android_permissions": {
        "question_fa": "کدام رفتار برای یک برنامه یادداشت‌برداری ساده نیازمند بررسی بیشتر است؟",
        "options": {
            "A": "ذخیره یادداشت در فضای خود برنامه",
            "B": "درخواست خواندن پیامک‌های گوشی بدون ضرورت عملکردی",
            "C": "نمایش فهرست یادداشت‌های ساخته‌شده",
        },
        "answer": "B",
        "explanation_fa": "مجوز خواندن پیامک باید ضرورت روشن داشته باشد؛ داشتن این مجوز به‌تنهایی اثبات بدافزار نیست.",
    },
    "accessibility_misuse": {
        "question_fa": "برای ارزیابی درخواست سرویس دسترس‌پذیری چه اقدامی مناسب‌تر است؟",
        "options": {
            "A": "بررسی علت نیاز برنامه، سازنده و تنظیمات مجوز",
            "B": "اجازه دائم به همه برنامه‌ها",
            "C": "غیرفعال کردن تمام محافظت‌های سیستم",
        },
        "answer": "A",
        "explanation_fa": "مجوز دسترس‌پذیری حساس است؛ باید ضرورت و منبع برنامه بررسی شود.",
    },
    "covert_surveillance_detection": {
        "question_fa": "در سناریوی کاملاً ساختگی، برنامه‌ای ناشناس هم مجوز غیرضروری می‌خواهد و هم فعالیت پس‌زمینه مشکوک دارد. پاسخ دفاعی مناسب چیست؟",
        "options": {
            "A": "بررسی منبع نصب و مجوزها، لغو دسترسی مشکوک و اسکن امنیتی دستگاه خود",
            "B": "اجازه دادن به تمام مجوزهای جدید",
            "C": "منتقل کردن فایل‌های واقعی دیگران به محیط آزمون",
        },
        "answer": "A",
        "explanation_fa": "چند شاخص همزمان نیازمند بررسی هستند، اما هیچ شاخصی به‌تنهایی نفوذ را اثبات نمی‌کند؛ سناریو هیچ داده واقعی ندارد.",
    },
    "synthetic_exfiltration": {
        "question_fa": "در گزارش تمرینی، رویداد SIMULATED_DATA_TRANSFER_NO_NETWORK چه معنایی دارد؟",
        "options": {
            "A": "داده واقعی گوشی به اینترنت ارسال شده است",
            "B": "گوشی شخص دیگری کنترل شده است",
            "C": "یک رویداد آموزشی ساختگی بدون انتقال واقعی داده ثبت شده است",
        },
        "answer": "C",
        "explanation_fa": "این آزمایش هیچ اتصال شبکه یا دسترسی به داده شخصی ندارد.",
    },
}


def _assert_choice(value: object, *, choices: frozenset[str], field: str) -> str:
    if type(value) is not str or value not in choices:
        raise ValueError("Unsupported " + field)
    return value


def list_lessons() -> dict:
    """Publicly harmless descriptions; the bot still enforces owner scope."""
    return {
        "synthetic": True,
        "lessons": [dict(item) for item in LESSONS],
        "data_source": "hard_coded_educational_examples",
        "remote_access": False,
        "real_data_collected": False,
        "network_requests": 0,
    }


def run_synthetic_case(arguments: Mapping) -> dict:
    case_id = _assert_choice(
        arguments.get("case_id"),
        choices=frozenset(CASES),
        field="case_id",
    )
    events = CASES[case_id]
    risk_points = sum(event[2] for event in events)
    risk_level = "high" if risk_points >= 6 else "low" if risk_points <= 2 else "medium"
    return {
        "case_id": case_id,
        "risk_points": risk_points,
        "risk_level": risk_level,
        "events": [{"app": a, "indicator": b, "weight": w} for a, b, w in events],
        "fictional": True,
        "actual_compromise_detected": False,
        "network_requests": 0,
        "interpretation_fa": "این امتیاز صرفاً برای تمرین است؛ اثبات جاسوسی یا آلودگی دستگاه نیست.",
    }


def quiz(arguments: Mapping) -> dict:
    lesson_id = _assert_choice(
        arguments.get("lesson_id"),
        choices=frozenset(QUESTIONS),
        field="lesson_id",
    )
    question = QUESTIONS[lesson_id]
    choice = arguments.get("choice")
    if choice is None:
        return {
            "lesson_id": lesson_id,
            "question_fa": question["question_fa"],
            "options": dict(question["options"]),
            "fictional": True,
        }
    choice = _assert_choice(choice, choices=frozenset(("A", "B", "C")), field="choice")
    return {
        "lesson_id": lesson_id,
        "correct": choice == question["answer"],
        "correct_choice": question["answer"],
        "explanation_fa": question["explanation_fa"],
        "fictional": True,
    }
