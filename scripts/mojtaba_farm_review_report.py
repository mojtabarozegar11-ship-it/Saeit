#!/usr/bin/env python3
"""Professional Persian offline farm analysis worksheet for manual review.

Creates neither a customer-delivered report nor a contract, invoice or sale.
Uses deterministic numerical model output; no customer identities are accepted.
"""
from __future__ import annotations

from mojtaba_farm_break_even import model

TRUTH = "پیش‌نویس علمی داخلی — نه گزارش تأییدشده، نه سفارش و نه درآمد وصول‌شده"


def render(data: dict) -> str:
    report = model(data)
    if report["canonical_bot"] != "mojtaba.bot.ai":
        raise ValueError("CANONICAL_BOT_REQUIRED")
    def val(key):
        raw = report[key]
        return "محاسبه‌ناپذیر با مفروضات کنونی" if raw is None else raw
    provenance = ("اعداد نمونهٔ ساختگی" if report["synthetic_example"]
                  else "ارقام تجمیعی ارائه‌شده و هنوز راستی‌آزمایی‌نشده")
    lines = [
        "# برگه بررسی اقتصاد تولید یک محصول",
        "",
        f"> {TRUTH}",
        "",
        "**مرجع محاسبات:** mojtaba.bot.ai — توانمندی اقتصاد تولید، نه ربات مستقل.",
        f"**مبنای داده:** {provenance}. **واحد پول:** ریال. **دوره:** {report['period']}.",
        "**دامنه:** یک محصول و یک دوره؛ قبل از مالیات، استهلاک، تأمین مالی، یارانه‌ها و هزینه‌های تخصیص‌نیافته.",
        "",
        "## نتایج پایه",
        "",
        "| سنجه | مقدار |",
        "|---|---:|",
        f"| تولید (کیلوگرم) | {val('volume_kg')} |",
        f"| درآمد ناخالص (ریال) | {val('gross_revenue_irr')} |",
        f"| هزینه متغیر (ریال) | {val('variable_cost_irr')} |",
        f"| هزینه ثابت دوره (ریال) | {val('fixed_cost_irr')} |",
        f"| کل هزینه (ریال) | {val('total_cost_irr')} |",
        f"| سود/زیان ساده‌شده (ریال) | {val('estimated_profit_irr')} |",
        f"| حاشیه مشارکت واحد (ریال/کیلوگرم) | {val('unit_contribution_irr_per_kg')} |",
        f"| مقدار سربه‌سر (کیلوگرم، گرد رو به بالا) | {val('breakeven_quantity_kg_ceil')} |",
        f"| درآمد سربه‌سر (ریال، گرد رو به بالا) | {val('breakeven_revenue_irr_ceil')} |",
        f"| قیمت سربه‌سر (ریال/کیلوگرم، گرد رو به بالا) | {val('breakeven_sale_price_irr_per_kg_ceil')} |",
        f"| حاشیه ایمنی مقدار (کیلوگرم) | {val('margin_of_safety_kg')} |",
        "",
    ]
    if report["unit_contribution_nonpositive"]:
        lines.extend([
            "**هشدار اقتصادی:** قیمت فروش از هزینه متغیر واحد بیشتر نیست؛",
            "در این فرض، افزایش مقدار تولید به تنهایی هزینه ثابت را جبران نمی‌کند.",
            "",
        ])
    lines.extend([
        "## تحلیل حساسیت مستقل ۲۷ حالت",
        "",
        "علامت **−۱/۰/+۱** به معنی کاهش، پایه یا افزایش هر عامل در دامنه درصدهای ورودی است؛",
        "این سناریوها پیش‌بینی احتمالاتی یا تضمین سود نیستند.",
        "",
        "| تغییر قیمت | تغییر عملکرد | تغییر هزینه متغیر | سود/زیان (ریال) | زیان؟ |",
        "|---:|---:|---:|---:|---|",
    ])
    for row in report["sensitivity_scenarios"]:
        lines.append(
            f"| {row['price_direction']:+d} | {row['yield_direction']:+d} | "
            f"{row['variable_cost_direction']:+d} | {row['profit_irr']} | "
            f"{'بله' if row['loss_scenario'] else 'خیر'} |")
    lines.extend([
        "",
        "## گیت‌های صحت و تحویل",
        "",
        "- راستی‌آزمایی واحدهای سطح، عملکرد، قیمت و دورهٔ هزینه‌های ثابت و متغیر توسط متخصص",
        "- تطبیق محاسبات با داده‌های واقعی مزرعه و بررسی معناداری سناریوهای انتخاب‌شده",
        "- اصلاح دامنه مدل برای هزینه‌های مغفول، مالیات، استهلاک یا سرمایه در گردش، در صورت نیاز",
        "- بازبینی حقوق استفاده از داده‌ها و الزامات محرمانگی پیش از هر تحویل",
        "- تصویب مجزای محدوده کار، قیمت، قرارداد، نحوه پرداخت و تحویل توسط مالک",
        "",
        "**وضعیت تجاری:** استعلام/بررسی داخلی؛ بدون شماره فاکتور، بدون دریافت وجه، بدون تحویل مشتری.",
        "",
    ])
    return "\n".join(lines)
