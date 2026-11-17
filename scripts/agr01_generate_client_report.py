#!/usr/bin/env python3
"""Generate one deliverable, private AGR-01 farm economics report from buyer input.

Usage: python scripts/agr01_generate_client_report.py --input /private/farm.json --output /private/report.html
Input JSON contains ONLY the seven FarmEnterpriseInputs keys (no customer PII).
No website, broker, network, DB, outbound mail, cash or live product is touched.
Never overwrites an existing report; file permissions default to owner-only.
"""
from __future__ import annotations
import argparse
from dataclasses import asdict, fields
from html import escape
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "core" / "agriculture_service_economics.py"


def _engine():
    name = "agr01_pure_engine"
    spec = importlib.util.spec_from_file_location(name, ENGINE)
    if spec is None or spec.loader is None:
        raise RuntimeError("agr01_engine_missing")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def report_for_input(raw):
    if type(raw) is not dict:
        raise ValueError("agr01_input_must_be_json_object")
    engine = _engine()
    names = {f.name for f in fields(engine.FarmEnterpriseInputs)}
    required = names - {"currency_code"}
    if set(raw) - names or not required.issubset(raw):
        raise ValueError("agr01_missing_or_extra_input_fields")
    item = engine.FarmEnterpriseInputs(**raw)
    return asdict(engine.assess_farm_enterprise(item))


def render_printable_html(report):
    if type(report) is not dict or not report:
        raise ValueError("agr01_report_invalid")
    captions = (
        ("currency_code", "واحد پول"),
        ("gross_revenue", "درآمد ناخالص"),
        ("variable_cost_total", "هزینه متغیر"),
        ("total_cost", "کل هزینه"),
        ("operating_surplus", "مازاد یا کسری عملیاتی"),
        ("contribution_per_tonne", "حاشیه مشارکت هر تن"),
        ("break_even_yield_tonnes_per_hectare", "عملکرد سربه‌سر تن در هکتار"),
        ("water_productivity_kg_per_m3", "بهره‌وری آب کیلوگرم بر مترمکعب"),
        ("price_down_10pct_surplus", "مازاد با افت ۱۰ درصد قیمت"),
        ("yield_down_10pct_surplus", "مازاد با افت ۱۰ درصد عملکرد"),
        ("combined_price_and_yield_down_10pct_surplus", "مازاد با افت همزمان قیمت و عملکرد"),
        ("operating_margin_pct", "حاشیه عملیاتی درصد"),
    )
    if any(name not in report for name, _ in captions):
        raise ValueError("agr01_report_incomplete")
    rows = "".join(
        "<tr><th>" + escape(label) + "</th><td>" +
        escape("تعریف‌نشده" if report[name] is None else str(report[name])) +
        "</td></tr>" for name, label in captions
    )
    return (
        "<!doctype html><html lang='fa' dir='rtl'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>گزارش اقتصاد مزرعه AGR-01</title>"
        "<style>body{font:16px Tahoma,sans-serif;max-width:850px;margin:auto;"
        "padding:2rem;line-height:1.8;color:#182620}h1{font-size:1.6rem}"
        "table{width:100%;border-collapse:collapse}th,td{border:1px solid #bac8c1;"
        "padding:.5rem;text-align:right}th{width:58%;background:#eef4f1}"
        "footer{margin-top:2rem;font-size:.85rem} @media print{body{padding:0}}</style>"
        "</head><body><main><h1>گزارش اقتصادی AGR-01 — زمرد ملل</h1>"
        "<p>محاسبات بر مبنای داده‌های ارائه‌شده مشتری؛ این گزارش تضمین سود، "
        "راستی‌آزمایی قیمت بازار یا تأیید تولید واقعی نیست.</p>"
        "<table><tbody>" + rows + "</tbody></table>"
        "<footer>قیمت، عملکرد و هزینه‌های ورودی باید با اسناد مشتری تطبیق داده شوند. "
        "هیچ پرداختی با تولید این فایل ایجاد نشده است.</footer></main></body></html>"
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="AGR-01 customer-input report")
    parser.add_argument("--input", required=True, help="Local JSON of farm numerical inputs")
    parser.add_argument("--output", required=True, help="Private new HTML report (must not exist)")
    args = parser.parse_args(argv)
    inp, out = Path(args.input), Path(args.output)
    if not inp.is_file() or inp.is_symlink() or inp.stat().st_size > 10000:
        raise ValueError("agr01_input_unsafe")
    if out.exists() or out.is_symlink() or not out.parent.is_dir():
        raise ValueError("agr01_output_must_be_new")
    data = json.loads(inp.read_text(encoding="utf8"))
    html = render_printable_html(report_for_input(data))
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(out), flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf8") as handle:
        handle.write(html)
    print(json.dumps({"report_written": True, "output_file": str(out),
                      "realized_income_verified": False}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
