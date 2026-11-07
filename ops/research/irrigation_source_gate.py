#!/usr/bin/env python3
"""Source-gated irrigation arithmetic: no sample observations or inferred source truth.

Usage: python ops/research/irrigation_source_gate.py measurements.json
Input: {"source_id":"DOI-or-archived-source","verified_by":"reviewer","rows":[
 {"id":"DSS","yield_kg":1,"water_m3":1}],"expected_wue":{}}
No network, no writes, no implicit conversion. Source metadata is a declaration,
not independent proof of provenance. Exit nonzero on invalid input.
"""
import json
import math
import sys
from decimal import Decimal, InvalidOperation

def positive(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError(field + " must be a positive finite number")
    try:
        d = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(field + " is not numeric") from exc
    if not d.is_finite() or d <= 0:
        raise ValueError(field + " must be positive and finite")
    return d

def validate(data):
    if not isinstance(data, dict) or not all(isinstance(data.get(k), str) and data[k].strip() for k in ("source_id", "verified_by")):
        raise ValueError("nonempty source_id and verified_by required; not proof of source verification")
    if "expected_wue" in data:
        raise ValueError("expected_wue is unsupported: silent comparison would misrepresent validation")
    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("nonempty rows required")
    result, seen = [], set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row["id"].strip():
            raise ValueError("each row needs an id")
        canonical_id = row["id"].strip()
        if canonical_id in seen:
            raise ValueError("duplicate row id after whitespace normalization")
        seen.add(canonical_id)
        y = positive(row.get("yield_kg"), "yield_kg")
        w = positive(row.get("water_m3"), "water_m3")
        result.append({"id":canonical_id, "wue_kg_per_m3":str(y/w)})
    return {"source_id":data["source_id"], "reviewer_claim":data["verified_by"], "computed":result,
            "source_authenticity_independently_verified":False}

def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: irrigation_source_gate.py measurements.json")
    try:
        with open(sys.argv[1], encoding="utf-8") as f:
            print(json.dumps(validate(json.load(f)), ensure_ascii=False, indent=2))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit("INVALID INPUT: " + str(exc)) from exc

if __name__ == "__main__":
    main()
