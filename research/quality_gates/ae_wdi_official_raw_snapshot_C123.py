#!/usr/bin/env python3
"""Capture byte-exact public World Bank WDI responses with SHA256, off factory VPS.

Example: python ae_wdi_official_raw_snapshot_C123.py --outdir ./wdi_raw_private
Never use this on the paused factory. Captures CURRENT vintage, not historical vintage.
Requires network access to api.worldbank.org. Never publishes data automatically.
"""
import argparse
import hashlib
import json
import pathlib
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

COUNTRIES = ("IND", "CAN")
INDICATORS = ("SL.AGR.EMPL.ZS", "NV.AGR.TOTL.ZS")
YEARS = ("2023", "2024")


def capture(outdir: pathlib.Path) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    manifest = {"schema": "AE-WDI-RAW-C123", "source": "World Bank API v2",
                "vintage": "CURRENT_API_NOT_HISTORICAL_ARCHIVE",
                "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                "observations": [], "files": []}
    for country in COUNTRIES:
        for indicator in INDICATORS:
            url = ("https://api.worldbank.org/v2/country/" + country
                   + "/indicator/" + indicator + "?format=json&date=2023:2024")
            req = urllib.request.Request(url, headers={"User-Agent": "R01-research-evidence-capture/1.0",
                                                       "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=25) as response:
                if response.status != 200:
                    raise RuntimeError("WDI HTTP status " + str(response.status))
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise RuntimeError("Unexpectedly large response")
            parsed = json.loads(raw)
            if not isinstance(parsed, list) or len(parsed) != 2 or not isinstance(parsed[1], list):
                raise RuntimeError("Unexpected WDI JSON schema")
            entries = parsed[1]
            if len(entries) != 2:
                raise RuntimeError("Expected exactly two annual observations")
            dates = {str(e.get("date")) for e in entries}
            if dates != set(YEARS):
                raise RuntimeError("Wrong WDI year set: " + str(dates))
            for e in entries:
                if e.get("countryiso3code") != country or e.get("indicator", {}).get("id") != indicator:
                    raise RuntimeError("WDI identity mismatch")
            name = country + "_" + indicator + "_2023_2024.raw.json"
            (outdir / name).write_bytes(raw)
            sha = hashlib.sha256(raw).hexdigest()
            manifest["files"].append({"name": name, "sha256": sha, "bytes": len(raw),
                                      "source_url": url, "metadata": parsed[0]})
            for e in entries:
                manifest["observations"].append({"country": country, "year": str(e["date"]),
                    "indicator": indicator, "value": e.get("value"),
                    "source_raw_file": name, "source_sha256": sha,
                    "status": "MISSING" if e.get("value") is None else "OBSERVED"})
    manifest_path = outdir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", required=True, type=pathlib.Path)
    args = parser.parse_args()
    result = capture(args.outdir)
    print("Captured", len(result["files"]), "raw WDI responses;",
          len(result["observations"]), "country-year-indicator records.")
    print("Manifest:", args.outdir / "manifest.json")
    print("NOTE: current API snapshots are NOT historical WDI vintages or ILOSTAT microdata.")


if __name__ == "__main__":
    main()
