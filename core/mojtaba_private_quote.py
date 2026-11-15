"""Private costed service quote *scenario*, never a sale or authorized price.

Requires review of cost inputs, legal currency, pricing and contract authority.
No customer PII, invoices, payment, outbound messages or public listing.
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile

from .mojtaba_commercial_services import CODES, private_dir
from .revenue_unit_economics import compute_quote_scenario


class QuoteScenarioError(ValueError):
    pass


def _render(payload, summary, sha):
    code = payload["service_code"]
    fields = (
        ("ارز واحد", summary["currency"]),
        ("قیمت محاسباتی هر واحد", summary["unit_price"]),
        ("هزینه متغیر هر واحد", summary["variable_unit_cost"]),
        ("حاشیه مشارکت واحد", summary["unit_contribution"]),
        ("درصد حاشیه مشارکت", summary["contribution_margin_percent"]),
        ("تعداد فرضی در دوره", summary["expected_units"]),
        ("نتیجه عملیاتی فرضی", summary["estimated_operating_result"]),
        ("واحدهای سربه‌سر", summary["break_even_units"]),
        ("حداقل قیمت پوشش هزینه", summary["minimum_unit_sale_price_for_expected_units"]),
    )
    lines = [
        "# سناریوی برآورد هزینه خدمت " + code, "",
        "**سامانه:** mojtaba.bot.ai؛ **وضعیت:** داخلی، بدون تصویب قیمت، نه پیش‌فاکتور، نه سفارش و نه مجوز دریافت وجه.",
        "**اثر انگشت ورودی:** " + sha, "",
        "| شاخص | مقدار مبتنی بر فرضیات |", "|---|---:|",
    ]
    lines.extend("| " + label + " | " + str(value) + " |" for label, value in fields)
    lines += [
        "", "**قابلیت اقتصادی در سناریو:** " + (
            "حاشیه مشارکت مثبت" if summary["unit_economics_viable"]
            else "فاقد حاشیه مشارکت مثبت"
        ),
        "**محدودیت:** قیمت و هزینه‌ها صرفاً داده ورودی هستند. این فایل قیمت‌گذاری مصوب، سود واقعی یا سفارش مشتری نیست.",
        "**مجوز عرضه:** احراز هویت پذیرنده، روش قانونی تسویه، مالیات، حقوق داده، توان تحویل، قرارداد و تصویب موردی مالک لازم‌اند.",
        "**درآمد وصول‌شده:** هیچ سند بیرونی در این محاسبه بررسی نشده است.", "",
    ]
    return "\n".join(lines)


def _private_quote_read(path, *, allow_publish_race=False):
    """Read only private regular artifacts; never follow an existing symlink."""
    if not hasattr(os, "O_NOFOLLOW"):
        raise QuoteScenarioError("QUOTE_SAFE_READ_UNAVAILABLE")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077
                    or (info.st_nlink != 1 and not (allow_publish_race and info.st_nlink == 2))
                    or info.st_size > 262144):
                raise QuoteScenarioError("QUOTE_UNSAFE_EXISTING")
            content = stream.read(262145)
    except OSError:
        raise QuoteScenarioError("QUOTE_UNSAFE_EXISTING") from None
    if len(content) > 262144:
        raise QuoteScenarioError("QUOTE_UNSAFE_EXISTING")
    return content


def prepare_private_quote(payload):
    """Create one immutable private quote scenario with SHA-256 byte proof."""
    if not isinstance(payload, dict) or set(payload) != {"service_code", "scenario"}:
        raise QuoteScenarioError("QUOTE_INVALID_FIELDS")
    code = payload["service_code"]
    if not isinstance(code, str) or code not in CODES:
        raise QuoteScenarioError("QUOTE_INVALID_SERVICE")
    try:
        scenario = compute_quote_scenario(payload["scenario"])
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                               ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError):
        raise QuoteScenarioError("QUOTE_SCENARIO_REJECTED") from None
    if len(canonical) > 16384:
        raise QuoteScenarioError("QUOTE_SCENARIO_TOO_LARGE")
    digest = hashlib.sha256(canonical).hexdigest()
    document = _render(payload, scenario, digest).encode("utf-8")
    root = private_dir()
    path = root / f"QUOTE-{code}-{digest[:24]}.md"
    if path.is_symlink():
        raise QuoteScenarioError("QUOTE_UNSAFE_PATH")
    if path.exists():
        if _private_quote_read(path) != document:
            raise QuoteScenarioError("QUOTE_OUTPUT_COLLISION")
        return {"created": False, "service_code": code, "input_sha256": digest,
                "output_sha256": hashlib.sha256(document).hexdigest(),
                "unit_economics_viable": scenario["unit_economics_viable"],
                "quote_approved": False, "external_settlement": None}
    fd, temp = tempfile.mkstemp(prefix=".quote-", dir=str(root))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(document)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, 0o600)
        try:
            os.link(temp, path, follow_symlinks=False)
            created = True
        except FileExistsError:
            try:
                prior = _private_quote_read(path, allow_publish_race=True)
            except QuoteScenarioError:
                raise QuoteScenarioError("QUOTE_CONCURRENT_COLLISION") from None
            if prior != document:
                raise QuoteScenarioError("QUOTE_CONCURRENT_COLLISION")
            created = False
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    if _private_quote_read(path) != document:
        raise QuoteScenarioError("QUOTE_HASH_CHECK_FAILED")
    return {"created": created, "service_code": code, "input_sha256": digest,
            "output_sha256": hashlib.sha256(document).hexdigest(),
            "bytes": len(document), "unit_economics_viable": scenario["unit_economics_viable"],
            "break_even_units": scenario["break_even_units"],
            "quote_approved": False, "external_settlement": None,
            "customer_contacted": False}
