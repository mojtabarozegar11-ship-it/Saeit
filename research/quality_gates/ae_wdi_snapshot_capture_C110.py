#!/usr/bin/env python3
"""AE-2026-001: preserve a *current* World Bank WDI API response with SHA-256.

This captures one immutable local response, never calls it a historical WDI
vintage, and does not assert independent ILOSTAT replication. Python 3.11 stdlib.
Usage: python ae_wdi_snapshot_capture_C110.py --country CAN --year 2023 --outdir ./private-ae
Run outside the public repo for raw output if there are any access restrictions.
"""
import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import urllib.request
from urllib.parse import quote

INDICATOR = "SL.AGR.EMPL.ZS"
SOURCE = "https://data.worldbank.org/indicator/SL.AGR.EMPL.ZS"

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--country", required=True, help="ISO-3 country code")
    p.add_argument("--year", required=True, type=int)
    p.add_argument("--outdir", required=True)
    args = p.parse_args()
    country = args.country.upper()
    if not re.fullmatch(r"[A-Z]{3}", country):
        p.error("country must be exactly three ASCII letters")
    if not 1960 <= args.year <= dt.datetime.now(dt.timezone.utc).year:
        p.error("invalid year")
    folder = pathlib.Path(args.outdir)
    folder.mkdir(parents=True, exist_ok=True)
    rawfile = folder / f"wdi_{INDICATOR}_{country}_{args.year}_current_api.json"
    manifestfile = folder / f"wdi_{INDICATOR}_{country}_{args.year}_manifest.json"
    if rawfile.exists() or manifestfile.exists():
        raise SystemExit("REFUSE_OVERWRITE: choose a fresh private output directory")
    url = (f"https://api.worldbank.org/v2/country/{quote(country)}/indicator/"
           f"{INDICATOR}?date={args.year}&format=json&per_page=1000")
    request = urllib.request.Request(url, headers={"User-Agent": "AE-2026-001-source-capture/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"HTTP {response.status}")
        raw = response.read(5_000_001)
        if len(raw) > 5_000_000:
            raise RuntimeError("response exceeds bounded size")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, list) or len(data) != 2 or not isinstance(data[1], list):
        raise RuntimeError("unexpected World Bank API schema")
    if len(data[1]) != 1:
        raise RuntimeError("ambiguous or absent country-year observation")
    row = data[1][0]
    if (row.get("indicator", {}).get("id") != INDICATOR
            or row.get("date") != str(args.year)
            or row.get("countryiso3code") != country):
        raise RuntimeError("returned indicator/year/country mismatch")
    value = row.get("value")
    if value is not None and (not isinstance(value, (int, float)) or not 0 <= value <= 100):
        raise RuntimeError("invalid percent value")
    retrieved = dt.datetime.now(dt.timezone.utc).isoformat()
    sha = hashlib.sha256(raw).hexdigest()
    manifest = {
        "study": "AE-2026-001", "source": SOURCE, "api_url": url,
        "retrieved_utc": retrieved, "raw_sha256": sha, "raw_bytes": len(raw),
        "country_iso3": country, "indicator": INDICATOR, "year": args.year,
        "value_percent_total_employment": value, "source_system": "World Bank WDI",
        "upstream": "ILOEST; NOT an independent replication",
        "vintage": "CURRENT_API_AT_RETRIEVAL; historical archive not verified",
        "interpretation": "modeled agriculture/forestry/fishing share of total employment",
        "empirical_panel_status": "BLOCKED_PENDING_HISTORICAL_ARCHIVE_AND_ILOSTAT_RELEASE"
    }
    rawfile.write_bytes(raw)
    manifestfile.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if hashlib.sha256(rawfile.read_bytes()).hexdigest() != sha:
        raise RuntimeError("readback SHA mismatch")
    print(json.dumps({"raw": str(rawfile), "manifest": str(manifestfile), "sha256": sha,
                      "value": value, "status": "CAPTURED_CURRENT_ONLY"}))

if __name__ == "__main__":
    main()
