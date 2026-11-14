#!/usr/bin/env python3
"""Offline internal service delivery engine, owned by single mojtaba.bot.ai.
No network, messages, payment, public release, user identity or trading.
Input: JSON object with service_code and non-personal data.
"""
from decimal import Decimal, InvalidOperation
from pathlib import Path
import argparse
import hashlib
import json
import os
import random
import re
import tempfile

CODES = ("AGR-01", "RS-01", "RS-02", "RS-03", "WEB-01", "SEO-01")
LINE = re.compile(r"^[^\x00-\x1f\x7f@<>]{1,96}$")


class InvalidService(ValueError):
    pass


def exact(obj, keys):
    if not isinstance(obj, dict) or set(obj) != set(keys):
        raise InvalidService("invalid input field set")


def dec(value, *, positive=False):
    # Floats have already lost exact decimal precision before conversion;
    # prices, costs and physical quantities must be supplied as text or ints.
    if isinstance(value, bool) or not isinstance(value, (int, str, Decimal)):
        raise InvalidService("exact numeric string or integer required")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise InvalidService("invalid decimal") from exc
    if not result.is_finite() or result < 0 or result > Decimal("1e15"):
        raise InvalidService("numeric range exceeded")
    if positive and result == 0:
        raise InvalidService("positive value required")
    return result


def integer(value, *, maximum=10000000):
    if type(value) is not int or not 0 <= value <= maximum:
        raise InvalidService("invalid integer")
    return value


def name(value):
    if not isinstance(value, str) or value != value.strip() or not LINE.fullmatch(value):
        raise InvalidService("nonpersonal short identifier required")
    return value.replace("|", "｜")


def pct(a, b):
    return "n/a" if not b else f"{Decimal(a) * 100 / Decimal(b):.2f}%"


def table(rows):
    return "\n".join("| " + " | ".join(map(str, row)) + " |" for row in rows)


def farm(data):
    exact(data, ("units_sold", "unit_price_toman", "unit_variable_cost_toman",
                 "fixed_cost_toman", "price_change_pct", "yield_change_pct"))
    units, price, variable, fixed = (
        dec(data[k]) for k in ("units_sold", "unit_price_toman",
                                "unit_variable_cost_toman", "fixed_cost_toman")
    )
    pp, yp = dec(data["price_change_pct"]), dec(data["yield_change_pct"])
    if pp > 100 or yp > 100:
        raise InvalidService("scenario growth exceeds 100 percent")
    total, contribution = units * price, units * (price - variable)
    operating = contribution - fixed
    breakeven = "undefined" if price <= variable else f"{fixed / (price - variable):.2f}"
    return table([
        ("شاخص", "مقدار", "واحد"),
        ("---", "---:", "---"),
        ("فروش ناخالص", f"{total:.2f}", "تومان"),
        ("هزینه متغیر", f"{units * variable:.2f}", "تومان"),
        ("هزینه ثابت", f"{fixed:.2f}", "تومان"),
        ("مازاد عملیاتی پیش از مالیات", f"{operating:.2f}", "تومان"),
        ("تعداد واحد سربه‌سر", breakeven, "واحد"),
        ("مازاد با افزایش قیمت", f"{units * (price * (1 + pp / 100) - variable) - fixed:.2f}", "تومان"),
        ("مازاد با افزایش تعداد", f"{units * (1 + yp / 100) * (price - variable) - fixed:.2f}", "تومان"),
    ]) + "\n\nاین محاسبه برآورد ساده و فاقد مالیات، جریان نقدی و هزینه فرصت است."


def research(data):
    exact(data, ("claims",))
    claims = data["claims"]
    if not isinstance(claims, list) or not 1 <= len(claims) <= 100:
        raise InvalidService("1..100 research claims required")
    rows = [("ادعا", "منبع", "واحد", "قابل بازتولید", "نقص"),
            ("---", "---", "---", "---", "---")]
    seen = set()
    valid = 0
    for item in claims:
        exact(item, ("claim_id", "source_id", "unit", "reproducible"))
        key = name(item["claim_id"])
        if type(item["source_id"]) is not str or type(item["unit"]) is not str:
            raise InvalidService("invalid evidence reference type")
        source = name(item["source_id"]) if item["source_id"] else ""
        unit = name(item["unit"]) if item["unit"] else ""
        if key in seen or type(item["reproducible"]) is not bool:
            raise InvalidService("duplicate claim or nonboolean evidence")
        seen.add(key)
        gaps = [k for k, present in (("source", source), ("unit", unit),
                                      ("method", item["reproducible"])) if not present]
        valid += not gaps
        rows.append((key, source or "missing", unit or "missing",
                     str(item["reproducible"]), ",".join(gaps) or "none"))
    return table(rows) + f"\n\nپوشش شناسنامه داده: {pct(valid, len(claims))}. صحت علمی مستقلاً تأیید نشده است."


def irrigation(data):
    exact(data, ("area_m2", "scenarios"))
    area, items = dec(data["area_m2"], positive=True), data["scenarios"]
    if not isinstance(items, list) or not 2 <= len(items) <= 12:
        raise InvalidService("2..12 irrigation scenarios required")
    rows = [("سناریو", "مترمکعب", "عمق معادل میلیمتر", "تفاوت با مبنا"),
            ("---", "---:", "---:", "---:")]
    baseline = None
    known = set()
    for item in items:
        exact(item, ("name", "flow_m3_per_hour", "hours"))
        key = name(item["name"])
        if key in known:
            raise InvalidService("duplicate scenario")
        known.add(key)
        volume = dec(item["flow_m3_per_hour"]) * dec(item["hours"])
        if baseline is None:
            baseline = volume
        delta = "n/a" if baseline == 0 else f"{(volume - baseline) * 100 / baseline:+.2f}%"
        rows.append((key, f"{volume:.2f}", f"{volume * 1000 / area:.2f}", delta))
    return table(rows) + "\n\nدبی × زمان حجم کاربردی اسمی است، نه صرفه‌جویی واقعی یا توصیه آبیاری."


def experiment(data):
    exact(data, ("treatments", "replicates", "seed"))
    items = data["treatments"]
    if not isinstance(items, list) or not 2 <= len(items) <= 12:
        raise InvalidService("2..12 treatments required")
    names = [name(x) for x in items]
    if len(set(names)) != len(names):
        raise InvalidService("duplicate treatments")
    repeats, seed = integer(data["replicates"], maximum=40), integer(data["seed"], maximum=2147483647)
    if repeats < 2:
        raise InvalidService("at least 2 replicates required")
    rng = random.Random(seed)
    rows = [("بلوک", "ردیف", "تیمار"), ("---:", "---:", "---")]
    for rep in range(1, repeats + 1):
        order = names[:]
        rng.shuffle(order)
        rows.extend((rep, i, t) for i, t in enumerate(order, 1))
    return table(rows) + f"\n\nبذر: {seed}؛ تعداد واحدها: {len(names) * repeats}. توان آماری و تصادفی‌سازی میدانی احراز نشده‌اند."


def web_funnel(data):
    keys = ("visitors", "inquiries", "qualified", "paid_orders", "delivered")
    exact(data, keys)
    vals = [integer(data[k]) for k in keys]
    if any(a < b for a, b in zip(vals, vals[1:])):
        raise InvalidService("inconsistent downstream counts")
    rows = [("مرحله", "شمار", "تبدیل نسبت به قبل"), ("---", "---:", "---:")]
    for i, key in enumerate(keys):
        rows.append((key, vals[i], "baseline" if i == 0 else pct(vals[i], vals[i - 1])))
    return table(rows) + "\n\nپرداخت و تحویل فقط شمارش ادعایی هستند؛ تطبیق مستقل با رسید و سند تحویل الزامی است."


def seo(data):
    exact(data, ("checks",))
    checks = data["checks"]
    if not isinstance(checks, list) or not 1 <= len(checks) <= 80:
        raise InvalidService("1..80 checks required")
    cats = {"indexing", "metadata", "mobile", "performance", "structured_data",
            "canonical", "security", "content"}
    rows = [("کنترل", "حوزه", "وضعیت", "اولویت", "مدرک"), ("---", "---", "---", "---", "---")]
    known = set()
    for item in checks:
        exact(item, ("id", "category", "state", "priority", "evidence_ref"))
        key = name(item["id"])
        if (
            key in known or type(item["category"]) is not str
            or type(item["state"]) is not str
            or item["category"] not in cats
            or item["state"] not in ("pass", "fail", "unknown")
        ):
            raise InvalidService("duplicate or unknown SEO control")
        known.add(key)
        if type(item["priority"]) is not str or item["priority"] not in ("high", "medium", "low"):
            raise InvalidService("unknown severity")
        if type(item["evidence_ref"]) is not str:
            raise InvalidService("invalid SEO evidence reference type")
        ev = name(item["evidence_ref"]) if item["evidence_ref"] else ""
        if item["state"] == "pass" and not ev:
            raise InvalidService("passing check requires independent source reference")
        rows.append((key, item["category"], item["state"], item["priority"], ev or "missing"))
    return table(rows) + "\n\nبدون اسکن سایت و داده Search Console، رتبه و اثر تجاری تأیید نشده است."


HANDLERS = dict(zip(CODES, (farm, research, irrigation, experiment, web_funnel, seo)))


def generate(payload, digest):
    exact(payload, ("service_code", "data"))
    code = payload["service_code"]
    if type(code) is not str or code not in CODES:
        raise InvalidService("unknown service")
    result = HANDLERS[code](payload["data"])
    return "\n".join((
        f"# تحلیل مقدماتی {code} — واحد داخلی Mojtaba.bot.ai",
        "وضعیت: خروجی خصوصی، بدون ادعای فروش، تسویه، انتشار یا بررسی مستقل صحت ورودی.",
        "اثر انگشت ورودی SHA-256: " + digest,
        "", result, "", "## پذیرش تجاری",
        "قبل از ارائه به مشتری: رضایت و اصالت داده، بررسی کارشناس، قرارداد و هزینه مصوب، درگاه مجاز، تحویل قابل پیگیری.",
        "این برنامه هیچ شبکه، پیام، پرداخت، معامله یا استقرار انجام نمی‌دهد.", "",
    ))


def private_dir():
    directory = Path.home()
    for part in ("factory-runtime", "private", "mojtaba-bot-ai", "service-deliverables"):
        directory = directory / part
        if directory.is_symlink():
            raise InvalidService("symlink output forbidden")
        created = not directory.exists()
        if created:
            directory.mkdir(mode=0o700)
        if not directory.is_dir():
            raise InvalidService("output is not directory")
        # Never chmod an existing factory-runtime directory: other services
        # may depend on its exact existing permissions.
        if part != "factory-runtime" and (directory.stat().st_mode & 0o077):
            raise InvalidService("private directory permissions too broad")
    return directory


def main():
    p = argparse.ArgumentParser(description="Private offline service deliverable builder")
    p.add_argument("input_json")
    args = p.parse_args()
    try:
        source = Path(args.input_json)
        if not source.is_file() or source.is_symlink() or source.stat().st_size > 65536:
            raise InvalidService("unsafe input")
        raw = source.read_bytes()
        if len(raw) > 65536:
            raise InvalidService("input size")
        payload = json.loads(raw.decode("utf-8"))
        digest = hashlib.sha256(raw).hexdigest()
        document = generate(payload, digest)
        out = private_dir() / f"{payload['service_code']}-{digest[:20]}.md"
        if out.is_symlink():
            raise InvalidService("unsafe output")
        if out.exists():
            if out.read_text(encoding="utf-8") == document:
                print("ALREADY_VERIFIED " + out.name)
                return 0
            raise InvalidService("collision")
        fd, temp_path = tempfile.mkstemp(prefix=".private-", dir=out.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                stream.write(document)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temp_path, 0o600)
            os.replace(temp_path, out)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        if out.read_text(encoding="utf-8") != document:
            raise InvalidService("postwrite integrity")
        print("PRIVATE_ARTIFACT_CREATED " + out.name)
        return 0
    except (InvalidService, OSError, UnicodeError, json.JSONDecodeError, KeyError) as exc:
        print("SERVICE_INPUT_OR_STORAGE_BLOCKED " + type(exc).__name__)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
