#!/usr/bin/env python3
"""Exploratory, noncausal, source-verified World Bank WDI panel retrieval.

AE-2026-001 is NOT a completed article. No results are generated from toy
fixtures except during --self-test; genuine results require live WDI API data.
Indicator: NV.AGR.EMPL.KD (constant 2015 USD per worker; ILO model inputs).
"""
import argparse
import csv
import json
import math
import pathlib
import statistics
import time
import urllib.parse
import urllib.request

API = "https://api.worldbank.org/v2"
INDICATOR = "NV.AGR.EMPL.KD"
YEARS = (2000, 2019, 2023)
SOURCE = "World Bank World Development Indicators and ILOSTAT"


def fetch_page(path, params):
    query = urllib.parse.urlencode(dict(params, format="json", per_page=20000))
    url = API + path + "?" + query
    last_exc = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "AE-2026-001-academic-provenance/1.0"})
            with urllib.request.urlopen(req, timeout=45) as response:
                page = json.load(response)
            if not isinstance(page, list) or len(page) != 2 or not isinstance(page[0], dict):
                raise ValueError("Malformed World Bank API response")
            if page[0].get("pages", 1) != 1:
                raise ValueError("Unexpected pagination; refuse partial data")
            return url, page[1]
        except Exception as exc:
            last_exc = exc
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"World Bank API data unavailable: {type(last_exc).__name__}: {last_exc}")


def sample_summary(rows, start_year, end_year):
    valid = [r for r in rows if r.get(start_year) is not None and r.get(end_year) is not None
             and r[start_year] > 0 and r[end_year] > 0]
    vals = [math.log(r[end_year] / r[start_year]) / (end_year - start_year) for r in valid]
    return {
        "start_year": start_year, "end_year": end_year,
        "number_countries_complete_pairs": len(vals),
        "median_log_change_per_year": statistics.median(vals) if vals else None,
        "mean_log_change_per_year": statistics.mean(vals) if vals else None,
        "country_pair_coverage_fraction": len(vals) / len(rows) if rows else None,
        "interpretation": "Descriptive observational change in real agricultural value added per worker. Not causal, not adjusted for confounders or WB/ILO estimate revisions.",
    }


def main(outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    country_url, countries = fetch_page("/country", {})
    data_url, obs = fetch_page("/country/all/indicator/" + INDICATOR, {"date": "2000:2023"})
    if not countries or not obs:
        raise RuntimeError("Empty real API results; no artifact created")
    allowed = {
        c["id"]: c for c in countries
        if isinstance(c, dict) and c.get("region", {}).get("id") not in ("NA", None)
        and len(str(c.get("id", ""))) == 3
    }
    if len(allowed) < 150:
        raise RuntimeError("Country metadata unexpectedly incomplete; refuse output")
    panel = {code: {"country_iso3": code, "country_name": c["name"], "region": c["region"]["value"],
                    "income_level": c.get("incomeLevel", {}).get("value", ""),
                    **{year: None for year in YEARS}} for code, c in allowed.items()}
    for x in obs:
        code = x.get("countryiso3code")
        try:
            year = int(x.get("date"))
        except (TypeError, ValueError):
            continue
        if code not in panel or year not in YEARS or x.get("value") is None:
            continue
        value = float(x["value"])
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"Nonfinite/nonpositive WDI indicator {code}/{year}")
        panel[code][year] = value
    sorted_rows = sorted(panel.values(), key=lambda x: x["country_iso3"])
    summary = {
        "series": INDICATOR, "source": SOURCE,
        "api_urls": {"country_metadata": country_url, "indicator_data": data_url},
        "measurement": "Agriculture, forestry and fishing value added per worker, constant 2015 US dollars",
        "all_nonaggregate_countries": len(sorted_rows),
        "year_availability": {str(y): sum(row[y] is not None for row in sorted_rows) for y in YEARS},
        "comparisons": [sample_summary(sorted_rows, 2000, 2019), sample_summary(sorted_rows, 2000, 2023)],
        "scientific_warning": "Exploratory descriptive pilot only; revisions, structural change, national accounts, ILO modeled employment, missingness, country comparability and existing convergence literature must be independently studied before a novel article claim.",
    }
    with (outdir / "observed_country_years.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["country_iso3", "country_name", "region", "income_level", "wdi_2000", "wdi_2019", "wdi_2023"])
        for r in sorted_rows:
            writer.writerow([r["country_iso3"], r["country_name"], r["region"], r["income_level"]] +
                            [r[y] for y in YEARS])
    (outdir / "source_and_missingness.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def self_test():
    toy = [{"2000": 1, 2000: 100, 2019: 200, 2023: 400},
           {2000: 100, 2019: None, 2023: 100}]
    x = sample_summary(toy, 2000, 2019)
    y = sample_summary(toy, 2000, 2023)
    assert x["number_countries_complete_pairs"] == 1
    assert y["number_countries_complete_pairs"] == 2
    assert abs(x["median_log_change_per_year"] - math.log(2) / 19) < 1e-12
    print("SELF-TEST PASSED (synthetic fixture; not empirical evidence)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--outdir", default="output/AE-2026-001")
    args = parser.parse_args()
    self_test() if args.self_test else main(pathlib.Path(args.outdir))
