#!/usr/bin/env python3
"""Read-only QC for AGR-FUT-009 pen-day dairy collection CSV.

No experimental observations supplied. Does not impute missing values,
calculate unapproved ECM, or infer causal effects. Local/private CSV only.
Usage: python3 AGR_FUT_009_DAIRY_PEN_DAY_QC_C121.py private_pen_days.csv
"""
import argparse
import csv
import datetime
import decimal
import json
import pathlib
import sys

D = decimal.Decimal
REQUIRED = (
    "study_id", "herd_code", "pen_code", "observation_date", "cow_days",
    "feed_offered_asfed_kg", "feed_refused_asfed_kg",
    "offered_dm_fraction", "refused_dm_fraction",
    "feed_intake_dm_kg", "milk_weight_kg", "quality_flag",
)

def number(row, field, issues, index, required=True):
    raw = (row.get(field) or "").strip()
    if not raw:
        if required:
            issues.append({"row": index, "field": field, "error": "missing_not_zero"})
        return None
    try:
        value = D(raw)
        if not value.is_finite():
            raise ValueError("non-finite")
        return value
    except (decimal.InvalidOperation, ValueError):
        issues.append({"row": index, "field": field, "error": "invalid_numeric"})
        return None

def check(path):
    issues = []
    seen = set()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        absent = sorted(set(REQUIRED) - set(reader.fieldnames or []))
        if absent:
            return {"status": "INVALID_SCHEMA", "missing_columns": absent, "issues": []}
        n = 0
        for n, row in enumerate(reader, start=1):
            if None in row:
                issues.append({"row": n, "error": "extra_columns"})
            key = tuple((row.get(k) or "").strip() for k in ("study_id", "herd_code", "pen_code", "observation_date"))
            if any(not part for part in key):
                issues.append({"row": n, "error": "missing_record_identity"})
            if key in seen:
                issues.append({"row": n, "error": "duplicate_pen_day"})
            seen.add(key)
            try:
                datetime.date.fromisoformat(key[3])
            except ValueError:
                issues.append({"row": n, "field": "observation_date", "error": "invalid_iso_date"})
            cow_days = number(row, "cow_days", issues, n)
            offered = number(row, "feed_offered_asfed_kg", issues, n)
            refused = number(row, "feed_refused_asfed_kg", issues, n)
            offered_frac = number(row, "offered_dm_fraction", issues, n)
            refused_frac = number(row, "refused_dm_fraction", issues, n)
            measured_dmi = number(row, "feed_intake_dm_kg", issues, n, required=False)
            milk = number(row, "milk_weight_kg", issues, n)
            if cow_days is not None and cow_days <= 0:
                issues.append({"row": n, "field": "cow_days", "error": "nonpositive_denominator"})
            for field, value in (("feed_offered_asfed_kg", offered), ("feed_refused_asfed_kg", refused), ("milk_weight_kg", milk)):
                if value is not None and value < 0:
                    issues.append({"row": n, "field": field, "error": "negative_measurement"})
            for field, value in (("offered_dm_fraction", offered_frac), ("refused_dm_fraction", refused_frac)):
                if value is not None and not D(0) <= value <= D(1):
                    issues.append({"row": n, "field": field, "error": "fraction_outside_0_1"})
            if all(x is not None for x in (offered, refused, offered_frac, refused_frac)):
                dmi = offered * offered_frac - refused * refused_frac
                if dmi < 0:
                    issues.append({"row": n, "field": "feed_intake_dm_kg", "error": "negative_calculated_dmi"})
                if measured_dmi is not None and abs(measured_dmi - dmi) > D("0.01"):
                    issues.append({"row": n, "field": "feed_intake_dm_kg", "error": "mass_balance_mismatch"})
            if not (row.get("quality_flag") or "").strip():
                issues.append({"row": n, "field": "quality_flag", "error": "missing_quality_flag"})
    return {"status": "PASS" if not issues and n > 0 else "BLOCKED", "records": n, "issues": issues,
            "note": "QC pass is not ethics approval, evidence of an experiment, ECM validation or a publication."}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=pathlib.Path)
    args = parser.parse_args()
    try:
        result = check(args.csv_path)
    except (OSError, UnicodeError, csv.Error) as exc:
        result = {"status": "BLOCKED", "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 2

if __name__ == "__main__":
    sys.exit(main())
