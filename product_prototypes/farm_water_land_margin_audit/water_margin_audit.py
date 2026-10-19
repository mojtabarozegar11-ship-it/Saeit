#!/usr/bin/env python3
"""Farm Water & Land Margin Audit — independent two-resource LP calculator.

Third independent source-built prototype in Astra V2. Solves continuous crop
hectares with individual area ceilings and total water/land limits by exact
Decimal vertex enumeration. No numerical solver, paid API, weather or yield
prediction; all agricultural parameters are user-provided and NOT verified.
"""
import argparse
from decimal import Decimal, InvalidOperation, localcontext, ROUND_HALF_EVEN
from itertools import combinations, product
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

D = Decimal
LIMIT = D("1000000000")
EPS = D("0.000000000000000000000001")
MONEY = D("0.01")
AREA = D("0.0001")


class ModelInputError(ValueError):
    pass


def dec(value, label, maxval=LIMIT, positive=False):
    if type(value) not in (str, int):
        raise ModelInputError(label + " must be a string decimal or integer")
    try:
        x = D(str(value))
    except InvalidOperation as exc:
        raise ModelInputError(label + " decimal invalid") from exc
    if not x.is_finite() or x < 0 or x > maxval or (positive and x == 0):
        raise ModelInputError(label + " outside supported range")
    return x


def fmt(x, unit=MONEY):
    return str(x.quantize(unit, rounding=ROUND_HALF_EVEN))


def validate(payload):
    required = {"currency", "land_hectares", "water_m3_available",
                "drought_water_fraction", "crops"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise ModelInputError("exactly five input keys required")
    currency = payload["currency"]
    if not isinstance(currency, str) or not re.fullmatch("[A-Z]{3}", currency):
        raise ModelInputError("currency must be three uppercase letters")
    land = dec(payload["land_hectares"], "land_hectares", positive=True)
    water = dec(payload["water_m3_available"], "water_m3_available")
    drought = dec(payload["drought_water_fraction"], "drought_water_fraction", D(1))
    crops = payload["crops"]
    if not isinstance(crops, list) or not 2 <= len(crops) <= 5:
        raise ModelInputError("require 2-5 crops")
    parsed = []
    seen = set()
    fields = {"name", "max_hectares", "water_m3_per_hectare",
              "revenue_per_hectare", "variable_cost_per_hectare",
              "source_reference", "source_status"}
    for row in crops:
        if not isinstance(row, dict) or set(row) != fields:
            raise ModelInputError("crop fields invalid")
        name = row["name"]
        if not isinstance(name, str) or not name.strip() or len(name) > 90 or name in seen:
            raise ModelInputError("distinct crop names required")
        seen.add(name)
        src = row["source_reference"]
        if not isinstance(src, str) or len(src) > 240:
            raise ModelInputError("source reference too long or invalid")
        if row["source_status"] not in ("operator_estimate", "operator_record"):
            raise ModelInputError("source status must declare record or estimate")
        parsed.append({
            "name": name,
            "max_area": dec(row["max_hectares"], "max_hectares"),
            "water": dec(row["water_m3_per_hectare"], "water_m3_per_hectare", positive=True),
            "margin": (dec(row["revenue_per_hectare"], "revenue_per_hectare")
                       - dec(row["variable_cost_per_hectare"], "variable_cost_per_hectare")),
            "source_ref": src,
            "source_status": row["source_status"],
        })
    return currency, land, water, drought, parsed


def solve(crops, land, water):
    """Enumerate every possible vertex of the bounded two-resource LP.

    For a linear objective with two pooled constraints and independent box
    bounds, an optimal extreme point exists with at most two non-bound
    variables. Generate endpoints for others; solve one shared equality for
    one free variable and both shared equalities for two free variables.
    """
    n = len(crops)
    bounds = [c["max_area"] for c in crops]
    ws = [c["water"] for c in crops]
    ms = [c["margin"] for c in crops]
    best = None
    tested = 0

    def visit(candidate):
        nonlocal best, tested
        tested += 1
        xs = []
        for i, x in enumerate(candidate):
            if x < -EPS or x > bounds[i] + EPS:
                return
            xs.append(max(D(0), min(bounds[i], x)))
        land_used = sum(xs, D(0))
        water_used = sum((xs[i] * ws[i] for i in range(n)), D(0))
        if land_used > land + EPS or water_used > water + EPS:
            return
        val = sum((xs[i] * ms[i] for i in range(n)), D(0))
        # Prefer smaller land allocation for true ties, then deterministic order.
        selector = (val, -land_used, tuple(-v for v in xs))
        if best is None or selector > best[0]:
            best = (selector, xs, land_used, water_used, val)

    with localcontext() as ctx:
        ctx.prec = 48
        indices = range(n)
        for nf in (0, 1, 2):
            for free in combinations(indices, nf):
                blocked = [i for i in indices if i not in free]
                for state in product((0, 1), repeat=len(blocked)):
                    current = [D(0)] * n
                    for i, flag in zip(blocked, state):
                        current[i] = bounds[i] if flag else D(0)
                    L = land - sum(current, D(0))
                    W = water - sum((current[i] * ws[i] for i in blocked), D(0))
                    if nf == 0:
                        visit(current)
                    elif nf == 1:
                        i = free[0]
                        for x in (L, W / ws[i]):
                            proposed = list(current)
                            proposed[i] = x
                            visit(proposed)
                    else:
                        i, j = free
                        det = ws[j] - ws[i]
                        if abs(det) <= EPS:
                            # Singular vertices are caught by one-free cases.
                            continue
                        xj = (W - ws[i] * L) / det
                        xi = L - xj
                        proposed = list(current)
                        proposed[i], proposed[j] = xi, xj
                        visit(proposed)
    if best is None:
        raise RuntimeError("model should always allow zero planted area")
    _, xs, land_used, water_used, val = best
    return {"areas": xs, "total_margin": val,
            "land_used": land_used, "water_used": water_used,
            "vertices_tested": tested}


def audit(payload):
    currency, land, water, drought, crops = validate(payload)
    baseline = solve(crops, land, water)
    stressed = solve(crops, land, water * drought)

    def present(solution, water_cap):
        return {
            "allocation": [{
                "crop": c["name"],
                "hectares": fmt(solution["areas"][i], AREA),
                "gross_margin_per_hectare": fmt(c["margin"]),
                "gross_margin_contribution": fmt(solution["areas"][i] * c["margin"]),
                "water_m3_used": fmt(solution["areas"][i] * c["water"]),
                "source_label": c["source_ref"],
                "source_verified_independently": False,
            } for i, c in enumerate(crops)],
            "total_gross_margin": fmt(solution["total_margin"]),
            "allocated_land_hectares": fmt(solution["land_used"], AREA),
            "unused_land_hectares": fmt(land - solution["land_used"], AREA),
            "water_m3_used": fmt(solution["water_used"]),
            "unused_water_m3": fmt(water_cap - solution["water_used"]),
            "vertices_tested": solution["vertices_tested"],
            "optimal_for_given_linear_model": True,
            "agronomic_or_market_optimum_verified": False,
        }

    changes = baseline["total_margin"] - stressed["total_margin"]
    normalized = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    warnings = [
        "OPERATOR_CROP_REVENUES_WATER_USE_AND_COSTS_NOT_VERIFIED",
        "LINEAR_CONSTANT_MARGIN_ASSUMPTION_ONLY",
        "NO_ROTATION_SOIL_DISEASE_WEATHER_YIELD_OR_ECOLOGICAL_CONSTRAINTS",
        "NO_HYDROLOGICAL_PERMITS_OR_WATER_RIGHTS_CHECKED",
        "GROSS_MARGIN_IS_NOT_NET_PROFIT",
        "DO_NOT_USE_AS_UNREVIEWED_IRRIGATION_OR_CROP_RECOMMENDATION",
    ]
    for c in crops:
        if not c["source_ref"].strip():
            warnings.append("INPUT_SOURCE_MISSING:" + c["name"])
    return {
        "schema_version": 1,
        "product": "farm_water_land_margin_audit_private_reference_mvp",
        "currency": currency,
        "area_unit": "hectares",
        "water_unit": "m3",
        "input_sha256": hashlib.sha256(normalized.encode()).hexdigest(),
        "baseline": present(baseline, water),
        "water_scarcity": present(stressed, water * drought),
        "drought_water_fraction": fmt(drought, AREA),
        "hypothetical_gross_margin_loss_under_water_scarcity": fmt(changes),
        "warnings": sorted(set(warnings)),
        "market_demand_verified": False,
        "sources_independently_verified": False,
        "quality_score": None,
        "sale_ready": False,
        "store_publication_authorized": False,
        "payments_authorized": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    args = p.parse_args(argv)
    raw = Path(args.input).expanduser()
    target = Path(args.output).expanduser()
    if raw.is_symlink() or not raw.is_file() or raw.stat().st_size > 250_000:
        raise ModelInputError("unsafe input")
    if target.is_symlink() or target.exists():
        raise ModelInputError("output must be a new file")
    source, dest = raw.resolve(strict=True), target.resolve()
    if source == dest or not dest.parent.is_dir():
        raise ModelInputError("invalid output location")
    model = json.loads(source.read_text(encoding="utf-8"), parse_float=str)
    report = audit(model)
    fd, temp = tempfile.mkstemp(dir=str(dest.parent), prefix=".water-margin-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(report, f, sort_keys=True, indent=2, ensure_ascii=False)
            f.write(chr(10)); f.flush(); os.fsync(f.fileno())
        os.chmod(temp, 0o600)
        os.link(temp, dest)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    print("ASTRA_WATER_LAND_TECHNICAL_AUDIT=COMPLETE")
    print("ASTRA_WATER_LAND_COMMERCIAL_APPROVAL=false")


if __name__ == "__main__":
    main()
