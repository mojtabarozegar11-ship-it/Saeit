#!/usr/bin/env python3
"""Astra V2 self-directed educational R&D production, without customer requests.

Each eligible UTC hour independently builds ONE new, internally consistent,
synthetic agricultural-economics case with questions, audited answers and a
self-test. Cases are educational *editions*, not independently validated
commercial products. No web, APIs, LLMs, payments, orders, personal data,
store publication, or reading live site databases. Called inside the existing
private factory single-writer lock. Python standard library only.
"""
from datetime import datetime, timezone
from decimal import Decimal, localcontext
import hashlib
import io
import json
import os
import re
from pathlib import Path
import shutil
import zipfile

MAX_CASE_BYTES = 64 * 1024 * 1024
MIN_FREE_BYTES = 256 * 1024 * 1024
MAX_RETAINED_EDUCATIONAL_CASES = 720
MIN_PROTECTED_AGE_HOURS = 168
CASE_FILENAME = re.compile(r"case-([0-9]{8,})-([0-9a-f]{16})\.zip\Z")
EPOCH = 1_788_739_200  # fixed epoch to make IDs stable across restarts
KINDS = ("capital_budgeting", "input_procurement", "break_even", "irrigation_allocation")
D = Decimal


def _text(v):
    return str(v.quantize(D("0.01")))


def case_for_hour(hour):
    if type(hour) is not int or hour < 0 or hour > 10_000_000:
        raise ValueError("invalid research edition hour")
    kind = KINDS[hour % len(KINDS)]
    # Each case's inputs vary in nontrivial ways and are fully synthetic.
    # The answers are computed, never hallucinated, guessed or copied.
    if kind == "capital_budgeting":
        periods = 3 + hour % 5
        rate = D(3 + (hour * 7) % 16) / 100
        capex = D(1700 + (hour * 53) % 1900)
        annual_net = D(450 + (hour * 29) % 750)
        with localcontext() as ctx:
            ctx.prec = 36
            present = -capex + sum((annual_net / ((1 + rate) ** t)
                                   for t in range(1, periods + 1)), D(0))
            stress = -capex + sum(((annual_net * D("0.8")) / ((1 + rate) ** t)
                                 for t in range(1, periods + 1)), D(0))
        givens = {"investment_now": _text(capex), "annual_cash_after_costs": _text(annual_net),
                  "discount_rate_pct": _text(rate * 100), "years": periods,
                  "stressed_annual_cash_multiplier": "0.80"}
        answers = {"base_npv": _text(present), "downside_npv": _text(stress),
                   "base_accept_if_npv_nonnegative": present >= 0}
        questions = [
            "Compute the discounted value of the project's after-cost annual flows.",
            "Compute NPV at time zero after subtracting the immediate investment.",
            "Recompute NPV if annual net cash is reduced by 20%; compare to baseline."
        ]
        method = "NPV = -I0 + sum(CFt / (1+r)^t), t=1..years. Cash is at year end."
        title = "Long-term Orchard Capital Budget Review"
    elif kind == "input_procurement":
        net_units = D(70 + (hour * 13) % 280)
        loss_a = D(1 + hour % 13) / 100
        loss_b = D(2 + (hour * 3) % 11) / 100
        p_a = D(35 + (hour * 7) % 100) / 10
        p_b = D(40 + (hour * 11) % 85) / 10
        freight_a = D(17 + (hour * 5) % 90)
        freight_b = D(22 + (hour * 7) % 80)
        with localcontext() as ctx:
            ctx.prec = 36
            gross_a = net_units / (1 - loss_a)
            gross_b = net_units / (1 - loss_b)
            total_a = gross_a * p_a + freight_a
            total_b = gross_b * p_b + freight_b
        givens = {
            "net_usable_units": _text(net_units),
            "quote_a": {"price_per_gross_unit": _text(p_a), "waste_pct": _text(loss_a * 100),
                        "freight": _text(freight_a)},
            "quote_b": {"price_per_gross_unit": _text(p_b), "waste_pct": _text(loss_b * 100),
                        "freight": _text(freight_b)},
        }
        answers = {"gross_units_a": _text(gross_a), "gross_units_b": _text(gross_b),
                   "delivered_total_a": _text(total_a), "delivered_total_b": _text(total_b),
                   "lower_cost_quote": "A" if total_a < total_b else "B" if total_b < total_a else "tie"}
        questions = [
            "Compute the gross units needed from each supplier after declared wastage.",
            "Calculate total delivered acquisition cost for each quote.",
            "Identify the lower arithmetic cost; list real-world capacity/tax checks still needed."
        ]
        method = "Gross units = net units/(1-waste fraction); delivered = gross*unit price + freight."
        title = "Farm Input Purchase and Wastage Comparison"
    elif kind == "break_even":
        fixed = D(2700 + (hour * 97) % 9000)
        price = D(150 + (hour * 9) % 260) / 10
        cost = D(40 + (hour * 13) % 100) / 10
        if cost >= price:
            cost = price / 2
        contribution = price - cost
        with localcontext() as ctx:
            ctx.prec = 36
            breakeven = fixed / contribution
            units = D(200 + (hour * 17) % 500)
            profit = units * contribution - fixed
        givens = {"fixed_cost": _text(fixed), "price_per_unit": _text(price),
                  "variable_cost_per_unit": _text(cost), "planned_units": _text(units)}
        answers = {"contribution_per_unit": _text(contribution),
                   "break_even_units_before_whole_unit_rounding": _text(breakeven),
                   "planned_profit": _text(profit), "planned_operation_profitable": profit >= 0}
        questions = [
            "Calculate unit contribution margin before fixed overhead.",
            "Find the break-even output volume; explain whole-unit rounding.",
            "Calculate operating result at the hypothetical planned unit sales."
        ]
        method = "Contribution = unit price - variable unit cost; break-even = fixed/contribution; profit = units*contribution - fixed."
        title = "Farm Enterprise Contribution and Break-even"
    else:
        water_available = D(800 + (hour * 47) % 4000)
        water_per_hectare = D(80 + (hour * 13) % 250)
        capacity = D(5 + (hour * 3) % 20)
        with localcontext() as ctx:
            ctx.prec = 36
            water_limited = water_available / water_per_hectare
            land_used = min(water_limited, capacity)
            spare = water_available - land_used * water_per_hectare
        givens = {"available_water_m3": _text(water_available),
                  "hypothetical_water_m3_per_hectare": _text(water_per_hectare),
                  "available_land_hectares": _text(capacity)}
        answers = {"water_limited_hectares": _text(water_limited),
                   "usable_hectares": _text(land_used),
                   "unused_water_m3": _text(spare),
                   "binding_constraint": "land" if capacity <= water_limited else "water"}
        questions = [
            "Calculate hectares supported by the stated water availability.",
            "Apply the farm area constraint and find maximum feasible area.",
            "Compute unused water and identify the binding constraint."
        ]
        method = "Water-limited area = supply/water per hectare; feasible area = min(water-limited area, land); unused = supply - feasible area*demand."
        title = "Irrigation Capacity and Resource Allocation"
    return {"edition_number": hour,"subject":kind,"title":title,"givens":givens,
            "questions":questions,"answers":answers,"method":method,
            "actual_market_data":False,"input_data_kind":"FICTIONAL EDUCATIONAL EXERCISE",
            "customer_order_required":False,"commercial_quality_assessed":False,
            "publication_allowed":False}


def _files(item):
    common = ("**FICTIONAL EDUCATIONAL EXERCISE — NOT A REAL FARM CASE, PRICE, "
              "YIELD, INVOICE OR AGRONOMIC RECOMMENDATION.**")
    head = "# " + item["title"] + "\n\n" + common + "\n\n"
    givens = json.dumps(item["givens"], indent=2, sort_keys=True)
    problem = (head + "## Scenario data\n\n```json\n" + givens +
               "\n```\n\n## Problems\n\n" +
               "\n".join(str(i+1) + ". " + q for i,q in enumerate(item["questions"])) +
               "\n\n## Assumptions\n\n" + item["method"] +
               "\n\nAll data are invented for education; never claim that these "
               "numbers were researched or represent a real supplier or buyer.\n")
    answers = (head + "## Independently recalculated results\n\n```json\n" +
               json.dumps(item["answers"], indent=2, sort_keys=True) +
               "\n```\n\n## Verification\n\n" + item["method"] +
               "\n\nCheck original user figures and professional guidance before a real decision.\n")
    manifest = json.dumps(item, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    selftest = (
        "import json\nfrom pathlib import Path\n"
        "x=json.loads((Path(__file__).parent/'CASE.json').read_text())\n"
        "assert x['actual_market_data'] is False\n"
        "assert x['publication_allowed'] is False\n"
        "assert x['commercial_quality_assessed'] is False\n"
        "assert len(x['questions'])==3 and len(x['answers'])>=3\n"
        "print('ASTRA_EDUCATIONAL_CASE_SELFTEST=PASS')\n"
    )
    return {"CASE_STUDY.md":problem.encode("utf-8"),
            "ANSWER_KEY.md":answers.encode("utf-8"),
            "CASE.json":manifest.encode("utf-8"),
            "self_test.py":selftest.encode("utf-8")}


def _validate_archive(path, expected_files, expected_hour):
    """A private edition must match original deterministic synthetic bytes."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 100_000:
        raise ValueError("unsafe or oversized synthetic edition")
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None or set(z.namelist()) != {
                "astra_case/" + name for name in expected_files}:
            raise ValueError("private synthetic ZIP integrity error")
        for name, expected in expected_files.items():
            if z.read("astra_case/" + name) != expected:
                raise ValueError("private synthetic ZIP content mismatch")
        content=json.loads(z.read("astra_case/CASE.json"))
        if (content.get("edition_number") != expected_hour or
                content.get("input_data_kind") != "FICTIONAL EDUCATIONAL EXERCISE" or
                content.get("actual_market_data") is not False or
                content.get("publication_allowed") is not False):
            raise ValueError("unsafe synthetic archive manifest")


def _retire_only_old_generated_cases(folder, current_hour):
    """Bound a synthetic-only cache; never remove user or other factory files.

    Only age-eligible editions with byte-for-byte original generated contents
    are retired. The caller holds the private single-writer queue lock.
    """
    candidates = []
    for path in folder.iterdir():
        match = CASE_FILENAME.fullmatch(path.name)
        if match is None:
            continue
        hour = int(match.group(1))
        if hour > current_hour - MIN_PROTECTED_AGE_HOURS:
            continue
        if path.is_symlink() or not path.is_file():
            continue
        candidates.append((hour, path))
    total = len(list(folder.glob("case-*.zip")))
    needed = max(0, total - MAX_RETAINED_EDUCATIONAL_CASES + 1)
    if needed == 0:
        return 0
    retired = 0
    for previous_hour, path in sorted(candidates):
        if retired >= needed:
            break
        try:
            old_expected = _files(case_for_hour(previous_hour))
            _validate_archive(path, old_expected, previous_hour)
        except (ValueError, OSError, zipfile.BadZipFile, KeyError, AssertionError):
            # Foreign/mutated archives are preserved for private investigation.
            continue
        path.unlink()
        retired += 1
    return retired


def build_hour(root, hour):
    """Produce at most one unique useful case per UTC hour and bounded storage.

    Caller must hold the existing .queue.lock; no additional concurrency locks.
    Failing resource checks means no fabrication of completion or external spend.
    """
    folder=Path(root)/"autonomous_education"
    if folder.is_symlink():
        raise ValueError("unsafe education directory")
    folder.mkdir(mode=0o700,exist_ok=True)
    if not folder.is_dir():
        raise ValueError("education output is not a folder")
    item=case_for_hour(hour)
    files=_files(item)
    case_sha=hashlib.sha256(b"".join(
        key.encode()+b"\x00"+hashlib.sha256(value).digest()
        for key,value in sorted(files.items())
    )).hexdigest()
    destination=folder/("case-"+str(hour).zfill(8)+"-"+case_sha[:16]+".zip")
    if destination.is_symlink():
        raise ValueError("unsafe edition destination")
    if destination.exists():
        _validate_archive(destination, files, hour)
        return {"status":"UNCHANGED","subject":item["subject"],
                "edition_number":hour,"new_private_educational_edition":False}
    retired = _retire_only_old_generated_cases(folder, hour)
    existing = sorted(folder.glob("case-*.zip"))
    if any(path.is_symlink() or not path.is_file() for path in existing):
        return {"status":"RESOURCE_REVIEW_REQUIRED","edition_number":hour,
                "new_private_educational_edition":False}
    occupied=sum(path.stat().st_size for path in existing)
    if (len(existing) >= MAX_RETAINED_EDUCATIONAL_CASES or
            occupied>=MAX_CASE_BYTES or
            shutil.disk_usage(folder).free<MIN_FREE_BYTES):
        return {"status":"RESOURCE_REVIEW_REQUIRED","edition_number":hour,
                "new_private_educational_edition":False}
    buf=io.BytesIO()
    with zipfile.ZipFile(buf,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for name,data in sorted(files.items()):
            meta=zipfile.ZipInfo("astra_case/"+name,date_time=(2020,1,1,0,0,0))
            meta.compress_type=zipfile.ZIP_DEFLATED
            meta.external_attr=0o100644 << 16
            z.writestr(meta,data)
    archive=buf.getvalue()
    if len(archive)>100_000 or occupied+len(archive)>MAX_CASE_BYTES:
        return {"status":"RESOURCE_REVIEW_REQUIRED","edition_number":hour,
                "new_private_educational_edition":False}
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        assert z.testzip() is None
        assert len(z.namelist())==len(files)
        assert z.read("astra_case/CASE.json")==files["CASE.json"]
    # Exclusive create: no accidental overwrite; hash and replay stable.
    fd=os.open(str(destination),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(archive);f.flush();os.fsync(f.fileno())
    except BaseException:
        if destination.exists():destination.unlink()
        raise
    return {"status":"PRIVATE_CASE_BUILT","subject":item["subject"],
            "edition_number":hour,"sha256":hashlib.sha256(archive).hexdigest(),
            "new_private_educational_edition":True,
            "sale_ready":False,"market_demand_verified":False,
            "retired_old_synthetic_editions":retired}


def create_current(root, now_utc=None):
    current = now_utc if now_utc is not None else datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("timezone-aware clock required")
    utc=current.astimezone(timezone.utc)
    hour=int(utc.timestamp())//3600
    return build_hour(root,hour)


if __name__=="__main__":
    import argparse
    import tempfile
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-root")
    p.add_argument("--demo",action="store_true")
    args=p.parse_args()
    if args.demo:
        with tempfile.TemporaryDirectory(prefix="astra-case-demo-") as t:
            print(json.dumps(create_current(t),sort_keys=True))
            print(json.dumps(create_current(t),sort_keys=True))
    elif args.private_root:
        # Only one-off manual demo use; cron must use pipeline .queue.lock.
        raise SystemExit("Use astra_v2_private_pipeline.py tick for locked production")
    else:
        p.error("--demo required")
