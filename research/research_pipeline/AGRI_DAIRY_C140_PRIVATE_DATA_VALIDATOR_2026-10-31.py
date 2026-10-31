#!/usr/bin/env python3
"""R-01 dairy farm-month blank-template validator. Stdlib only; no external I/O.
Usage: python3 agr_dairy_c140_validate.py path/to/private_data.csv
Never commit filled private farm data or source invoices to public GitHub.
This is a schema/logic gate, not a research ethics approval or scientific result.
"""
import csv
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

COLUMNS = ["anonymized_farm_id","month","region_code","cows_total","cows_lactating","saleable_milk_kg","discarded_milk_kg","dry_matter_feed_kg","feed_cost_local","labor_cost_local","veterinary_cost_local","energy_water_cost_local","other_variable_cost_local","milk_revenue_local","byproduct_revenue_local","fixed_cost_local","currency_code","source_record_type","source_verified","missingness_reason","consent_research_use"]
NUMERIC = ["saleable_milk_kg","discarded_milk_kg","dry_matter_feed_kg",
 "feed_cost_local","labor_cost_local","veterinary_cost_local",
 "energy_water_cost_local","other_variable_cost_local","milk_revenue_local",
 "byproduct_revenue_local","fixed_cost_local"]
ENUM_SOURCE = {"invoice","meter","farm_log","interview"}
ENUM_MISSING = {"none","not_recorded","not_applicable","withheld"}
TRUE = {"true","1","yes"}
FALSE = {"false","0","no"}

def validate(path):
    errors = []
    seen = set()
    valid_for_margin = 0
    with open(path, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != COLUMNS:
            return ["CSV header must match the published C140 schema exactly"], 0, 0
        n = 0
        for n, row in enumerate(reader, start=1):
            e = []
            if None in row or any(v is None for v in row.values()):
                e.append("column count mismatch")
            farm = (row.get("anonymized_farm_id") or "").strip()
            month = (row.get("month") or "").strip()
            if not farm: e.append("missing pseudonymous farm ID")
            if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month): e.append("invalid YYYY-MM")
            key = (farm, month)
            if key in seen: e.append("duplicate farm-month")
            seen.add(key)
            if not (row.get("region_code") or "").strip(): e.append("missing region code")
            if not re.fullmatch(r"[A-Z]{3}", (row.get("currency_code") or "")):
                e.append("currency must be 3-letter uppercase code (ISO membership not checked)")
            if row.get("source_record_type") not in ENUM_SOURCE: e.append("invalid source type")
            if row.get("missingness_reason") not in ENUM_MISSING: e.append("invalid missingness reason")
            for flag in ("source_verified", "consent_research_use"):
                if (row.get(flag) or "").lower() not in TRUE | FALSE: e.append("invalid boolean "+flag)
            if (row.get("consent_research_use") or "").lower() not in TRUE:
                e.append("research consent absent; row must not enter analysis")
            parsed = {}
            for col in ["cows_total","cows_lactating"] + NUMERIC:
                raw = (row.get(col) or "").strip()
                if raw == "":
                    if row.get("missingness_reason") == "none": e.append("blank "+col+" without missingness reason")
                    parsed[col] = None
                    continue
                try:
                    v = Decimal(raw)
                    if not v.is_finite() or v < 0: raise InvalidOperation
                    if col.startswith("cows_") and v != v.to_integral_value(): raise InvalidOperation
                    parsed[col] = v
                except (InvalidOperation, ValueError):
                    e.append("invalid nonnegative number "+col)
                    parsed[col] = None
            ct,cl = parsed["cows_total"],parsed["cows_lactating"]
            if ct is not None and ct <= 0: e.append("cows_total must be positive")
            if cl is not None and cl <= 0: e.append("cows_lactating must be positive")
            if ct is not None and cl is not None and cl > ct: e.append("lactating cows exceed herd")
            milk = parsed["saleable_milk_kg"]
            if milk is not None and milk > 0 and all(parsed[k] is not None for k in
                ["feed_cost_local","labor_cost_local","veterinary_cost_local",
                 "energy_water_cost_local","other_variable_cost_local",
                 "milk_revenue_local","byproduct_revenue_local"]):
                valid_for_margin += 1
            if e: errors.append("row "+str(n)+": "+", ".join(e))
    return errors, n, valid_for_margin

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Usage: python3 agr_dairy_c140_validate.py private_data.csv")
    try:
        errs, rows, eligible = validate(Path(sys.argv[1]))
    except (OSError, UnicodeError, csv.Error) as exc:
        sys.exit("Unable to validate CSV: "+type(exc).__name__)
    print("rows=",rows,"margin-computable=",eligible,"errors=",len(errs))
    for item in errs[:30]: print(item)
    if len(errs)>30: print("Additional errors suppressed:",len(errs)-30)
    if rows==0: print("BLANK TEMPLATE ONLY; no observations, consent or results.")
    sys.exit(1 if errs else 0)
