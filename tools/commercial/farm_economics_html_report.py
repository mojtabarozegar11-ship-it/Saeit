"""Offline Persian RTL presentation for a validated internal farm economics JSON result.

This is a review artifact, NOT an approved quote, invoice, tax advice, or cash receipt.
Never contacts the network or takes payments.
"""
import argparse
from html import escape
import json
import sys
from pathlib import Path

REQUIRED = (
    "enterprise_id", "enterprise_type", "period_start", "period_end",
    "currency", "output_unit", "production_quantity", "sold_quantity", "unsold_quantity",
    "inventory_cost_allocation", "sales_revenue", "other_revenue",
    "variable_cost", "fixed_cost", "opportunity_cost", "economic_profit",
    "break_even_units", "economic_break_even_units", "economic_break_even_feasibility",
    "reported_profit_basis", "economic_break_even_basis",
)


def render_html(payload):
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("unsupported farm economics JSON schema")
    rows = payload.get("records")
    if not isinstance(rows, list) or not (1 <= len(rows) <= 1000):
        raise ValueError("expected 1 to 1000 enterprise records")
    items = []
    for index, data in enumerate(rows, 1):
        if not isinstance(data, dict) or any(key not in data or not isinstance(data[key], str)
                                              for key in REQUIRED):
            raise ValueError(f"record {index}: missing or invalid required evidence")
        def val(key): return escape(data[key], quote=True)
        warning = (
            "تطبیق هزینه موجودی فروش‌نرفته لازم است؛ نتیجه سود دوره، گزارش قطعی تعهدی نیست."
            if data["inventory_cost_allocation"] == "REQUIRES_RECONCILIATION"
            else "موجودی فروش‌نرفته در این رکورد ثبت نشده است."
        )
        items.append(f'''<section class="report" aria-label="گزارش بنگاه {index}">
<h2>واحد {val('enterprise_id')} — {val('enterprise_type')}</h2>
<p>دوره: <b dir="ltr">{val('period_start')} — {val('period_end')}</b> · واحد محصول: {val('output_unit')} · واحد پول: {val('currency')}</p>
<table><caption>داده‌های مبنا و محاسبات</caption><tbody>
<tr><th scope="row">تولید</th><td>{val('production_quantity')}</td><th scope="row">فروش</th><td>{val('sold_quantity')}</td></tr>
<tr><th scope="row">موجودی فروش‌نرفته</th><td>{val('unsold_quantity')}</td><th scope="row">درآمد فروش</th><td>{val('sales_revenue')}</td></tr>
<tr><th scope="row">درآمد جانبی</th><td>{val('other_revenue')}</td><th scope="row">هزینه متغیر</th><td>{val('variable_cost')}</td></tr>
<tr><th scope="row">هزینه ثابت</th><td>{val('fixed_cost')}</td><th scope="row">هزینه فرصت</th><td>{val('opportunity_cost')}</td></tr>
<tr><th scope="row">مازاد اقتصادی دوره*</th><td>{val('economic_profit')}</td><th scope="row">سربه‌سر عملیاتی (واحد)</th><td>{val('break_even_units')}</td></tr>
<tr><th scope="row">سربه‌سر اقتصادی (واحد)</th><td>{val('economic_break_even_units')}</td><th scope="row">امکان‌پذیری سربه‌سر اقتصادی</th><td>{val('economic_break_even_feasibility')}</td></tr>
</tbody></table>
<p class="warning">{warning}</p>
<p class="small">* مبنای سود: {val('reported_profit_basis')}. مبنای سربه‌سر اقتصادی: {val('economic_break_even_basis')}. هیچ‌کدام پیش‌بینی قطعی سود یا قیمت مصوب نیستند.</p>
</section>''')
    return '''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>پیش‌نویس گزارش اقتصاد کشاورزی — زمرد ملل</title>
<style>html{font-family:Tahoma,Arial,sans-serif;color:#19352a;background:#f6f8f6}body{max-width:1020px;margin:auto;padding:16px}h1{font-size:1.6rem}h2{font-size:1.2rem} .report{background:white;border:1px solid #ccd9cd;border-radius:10px;padding:18px;margin:16px 0;page-break-inside:avoid}table{width:100%;border-collapse:collapse;table-layout:fixed}caption{font-weight:700;text-align:right;padding:10px}th,td{border:1px solid #cbd6ce;padding:9px;overflow-wrap:anywhere;text-align:right;font-size:.88rem}.warning{border-right:4px solid #ad6a25;padding:10px;background:#fff3e2}.small{font-size:.82rem;color:#4e6257;overflow-wrap:anywhere} .draft{font-weight:bold} @media(max-width:600px){body{padding:8px}.report{padding:10px}th,td{padding:4px;font-size:.73rem}}@media print{html{background:white}.report{box-shadow:none}}</style>
</head><body><header><h1>گزارش داخلی اقتصاد کشاورزی</h1>
<p class="draft">پیش‌نویس برای بررسی کارشناسی — بدون تأیید علمی، قیمت، تعهد خدمت یا اعتبار فاکتور</p>
<p>این گزارش فقط از داده‌های ارائه‌شده استخراج شده است؛ صحت داده‌ها و تخصیص هزینه موجودی نیازمند مدارک مستقل است.</p></header>''' + ''.join(items) + '</body></html>'


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render internal farm economics JSON as print-ready RTL HTML")
    parser.add_argument("json_file", help="Local JSON emitted by farm_economics_cli.py")
    args = parser.parse_args(argv)
    try:
        data = json.loads(Path(args.json_file).read_text(encoding="utf-8-sig"))
        html = render_html(data)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Report rejected: {exc}", file=sys.stderr)
        return 2
    print(html)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
