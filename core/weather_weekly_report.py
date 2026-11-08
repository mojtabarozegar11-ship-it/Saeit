"""Seven-day weather editorial report, independent from Django and paid models."""

from datetime import date
from typing import Callable


def _value(number, suffix: str) -> str:
    return f"{number}{suffix}" if number is not None else "ناموجود"


def render_seven_day_report(
    provinces: list[dict], *, report_date: str,
    flags_for_day: Callable[[dict], list[str]], attribution: str,
    source_url: str, license_url: str,
) -> str:
    """Render the full seven days for each province capital; reject missing days."""
    if not provinces:
        raise ValueError("Weather report cannot have an empty province list")
    lines = [
        f"گزارش ۷ روزه هواشناسی ایران — {report_date}", "",
        "این جدول برآورد مراکز استان‌هاست، نه تمامی نقاط هر استان. "
        "دما، بارش و باد از پیش‌بینی زمان‌بندی‌شده یک ارائه‌دهنده گردآوری شده‌اند. "
        "این داده‌ها مشاهدهٔ قطعی، اجماع چند مدل یا هشدار رسمی نیستند.",
        "احتمال بارش «ناموجود» به معنی احتمال صفر نیست. ",
    ]
    for item in provinces:
        province = item.get("province")
        capital = item.get("capital")
        days = item.get("forecast") or []
        if not province or not capital or len(days) != 7:
            raise ValueError(f"Incomplete weather record for {province or 'unknown'}")
        if any(day.get("min_c") is None or day.get("max_c") is None or not day.get("date") for day in days):
            raise ValueError(f"Missing essential weather values for {province}")
        dates = [date.fromisoformat(day["date"]) for day in days]
        if len(set(dates)) != 7 or dates != sorted(dates):
            raise ValueError(f"Repeated or unordered dates for {province}")
        low = min(day["min_c"] for day in days)
        high = max(day["max_c"] for day in days)
        rain_known = all(day.get("rain_mm") is not None for day in days)
        rain_total = f"{sum(day['rain_mm'] for day in days):.1f} میلی‌متر" if rain_known else "ناموجود (داده ناقص)"
        lines.append("")
        lines.append(
            f"{province} — {capital} | دامنه دمای ۷ روز: {low} تا {high} درجه | "
            f"جمع بارش برآوردی ۷ روز: {rain_total}"
        )
        for day in days:
            warnings = "، ".join(flags_for_day(day)) or "بدون عبور از آستانه هشدار خودکار"
            lines.append(
                f"• {day['date']}: دما {day['min_c']} تا {day['max_c']}°C؛ "
                f"بارش {_value(day.get('rain_mm'), ' میلی‌متر')}؛ "
                f"باد تا {_value(day.get('wind_kmh'), ' km/h')}؛ "
                f"احتمال بارش {_value(day.get('rain_probability'), '٪')}؛ {warnings}"
            )
    lines.extend([
        "", f"داده: {attribution} — {source_url}؛ مجوز انتساب: {license_url}.",
        "بارش دوره‌های چندساعته هنگام عبور از نیمه‌شب به‌صورت تقریبی بین روزها تقسیم شده است. "
        "پرچم‌های خودکار صرفاً عبور از آستانه‌های محاسباتی هستند؛ پیش از آبیاری، "
        "سم‌پاشی، برداشت یا تصمیم مالی، شرایط واقعی مزرعه، محصول و اطلاعیهٔ رسمی منطقه را بررسی کنید.",
    ])
    return "\n".join(lines)
