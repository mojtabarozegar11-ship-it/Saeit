#!/usr/bin/env python3
"""AE-2026-001: fail-closed WDI vintage panel revision gate; standard library only.

Input manifest JSON: {"archives":[{"vintage":"2024-12-16",
"archive_sha256":"64 lowercase hex chars","verified":true,"original_url":"...",
"final_url":"..."}, ...]} for 2024-12-16, 2025-12-19, 2026-10-08.
Input CSV columns: vintage,country,indicator,year,value. Missing: blank/NA/..
The manifest is a signed-off statement of independently checked local archive bytes,
not an HTTP URL proof. This tool does NOT download data or validate the ZIP itself.
"""
import argparse
import csv
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

VINTAGES = ("2024-12-16", "2025-12-19", "2026-10-08")
REQUIRED = {"vintage", "country", "indicator", "year", "value"}
MISSING = {"", "NA", ".."}
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", required=True)
    p.add_argument("--panel", required=True)
    p.add_argument("--out", required=True)
    a = p.parse_args()
    manifest = json.loads(Path(a.manifest).read_text(encoding="utf-8"))
    archives = manifest.get("archives", [])
    if len(archives) != len(VINTAGES) or {x.get("vintage") for x in archives} != set(VINTAGES):
        raise ValueError("exactly three distinct official vintages required")
    for x in archives:
        if x.get("verified") is not True or not SHA256.fullmatch(x.get("archive_sha256", "")):
            raise ValueError("unverified archive bytes or invalid SHA-256: " + str(x.get("vintage")))
        if not x.get("original_url", "").startswith("https://") or not x.get("final_url", "").startswith("https://"):
            raise ValueError("both original and final archive URLs required")
    panel = {}
    with open(a.panel, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if not REQUIRED.issubset(reader.fieldnames or []):
            raise ValueError("missing panel columns")
        for line, row in enumerate(reader, 2):
            vintage = row["vintage"].strip()
            country, indicator = row["country"].strip(), row["indicator"].strip()
            year = row["year"].strip()
            if vintage not in VINTAGES or not country or not indicator or not re.fullmatch(r"\d{4}", year):
                raise ValueError("invalid key at CSV line " + str(line))
            key = (vintage, country, indicator, int(year))
            if key in panel:
                raise ValueError("duplicate vintage-country-indicator-year: " + str(key))
            raw = row["value"].strip()
            if raw in MISSING:
                val = None
            else:
                try:
                    val = Decimal(raw)
                except InvalidOperation as exc:
                    raise ValueError("invalid decimal at line " + str(line)) from exc
                if not val.is_finite():
                    raise ValueError("nonfinite decimal at line " + str(line))
            panel[key] = val
    if not panel:
        raise ValueError("no observed panel rows")
    cohorts = sorted({(c, i, y) for _, c, i, y in panel})
    revisions = []
    for country, indicator, year in cohorts:
        vals = [panel.get((v, country, indicator, year)) for v in VINTAGES]
        if any(v is None for v in vals):
            revisions.append({"country": country, "indicator": indicator, "year": year,
                              "status": "MISSING_VINTAGE_OR_VALUE", "deltas": None})
            continue
        revisions.append({"country": country, "indicator": indicator, "year": year,
                          "status": "COMMON_OBSERVED_COHORT",
                          "deltas": [str(vals[1] - vals[0]), str(vals[2] - vals[1])]})
    result = {"status": "PROVENANCE_DECLARED_NOT_INDEPENDENTLY_AUTHENTICATED_BY_SCRIPT",
              "vintages": list(VINTAGES), "panel_rows": len(panel),
              "common_cohort_rows": sum(x["status"] == "COMMON_OBSERVED_COHORT" for x in revisions),
              "revisions": revisions,
              "note": "No imputation, no independent ILOSTAT validation, no causal inference."}
    Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Validated", len(panel), "input rows;", result["common_cohort_rows"], "complete cohorts.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print("BLOCKED:", exc, file=sys.stderr)
        sys.exit(2)
