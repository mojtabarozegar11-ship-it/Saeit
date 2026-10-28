#!/usr/bin/env python3
"""Independent, fail-closed reanalysis of genuine 3-vintage WDI country rates.

Reads the preserved JSON from the *completed original GitHub Actions artifact*.
No synthetic data, new external downloads, inferential p-values or causal claims.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import zipfile

EXPECTED_N = 155
VINTAGES = ("2024", "2025", "2026")
PAIRS = (("2024", "2025"), ("2025", "2026"), ("2024", "2026"))
THRESHOLDS = (0.0, 0.001, 0.002, 0.005, 0.01)
EXPECTED_FLIPS = (6, 6, 10)

def load_original(path):
    data = Path(path).read_bytes()
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            files = [n for n in archive.namelist() if n.endswith(".json") and not n.startswith("__MACOSX/")]
            if len(files) != 1:
                raise ValueError("Original artifact must contain exactly one JSON source")
            original = json.loads(archive.read(files[0]))
    else:
        original = json.loads(data)
    return original, hashlib.sha256(data).hexdigest()

def audit(original, input_hash):
    block = original["same_country_2000_2019"]
    rows = block["country_level_rates"]
    if block["cohort_n"] != EXPECTED_N or len(rows) != EXPECTED_N:
        raise ValueError("Original fixed-country cohort count mismatch")
    ids = [r["iso3"] for r in rows]
    if len(set(ids)) != EXPECTED_N or sorted(ids) != sorted(block["iso3"]):
        raise ValueError("Duplicate or inconsistent economy IDs")
    for r in rows:
        if len(r["iso3"]) != 3:
            raise ValueError("Invalid country code")
        for vintage in VINTAGES:
            val = r[vintage]
            if not isinstance(val, (int, float)) or not math.isfinite(val) or val == 0:
                raise ValueError("Nonfinite/zero country growth requires separate sign rule")
    if original["same_country_2000_2023"]["cohort_n"] != 0:
        raise ValueError("Unexpected 2023 source coverage: re-audit before use")
    result = {
        "source": "Independent reanalysis of original AE-2026-001 GitHub Actions artifact 12616508530",
        "original_artifact_input_sha256": input_hash,
        "historical_archive_sha256": {
            v: original["archive_provenance"][v]["sha256"] for v in ("2024", "2025")
        },
        "fixed_2000_2019_cohort_n": EXPECTED_N,
        "sign_margin_threshold_units": "absolute annualised log growth (0.005 = 0.5 log percentage points/year)",
        "pairs": {},
        "limits": [
            "Sign changes are release-sensitive classifications, not real productivity reversals.",
            "Thresholds are sensitivity cutoffs, not statistical significance tests.",
            "Near-zero flips may be fragile; threshold choice is descriptive and not preregistered.",
            "2024 historical archive has no comparable 2023 endpoint."
        ],
        "publication_novelty": "NOT_ESTABLISHED",
    }
    for idx, (old, new) in enumerate(PAIRS):
        changes = [r for r in rows if (r[old] > 0) != (r[new] > 0)]
        old_report = block["pairwise_revisions"][old + "_to_" + new]
        codes = sorted(r["iso3"] for r in changes)
        if len(changes) != EXPECTED_FLIPS[idx] or codes != sorted(old_report["changed_country_codes"]):
            raise ValueError("Independent sign flips disagree with original archived output")
        deltas = [r[new] - r[old] for r in rows]
        robust = {}
        for threshold in THRESHOLDS:
            robust[str(threshold)] = {
                "count": sum(min(abs(r[old]), abs(r[new])) > threshold for r in changes),
                "country_codes": sorted(r["iso3"] for r in changes
                                        if min(abs(r[old]), abs(r[new])) > threshold),
            }
        result["pairs"][old + "_to_" + new] = {
            "all_sign_flips": len(changes),
            "sign_flip_codes": codes,
            "median_absolute_country_growth_revision": statistics.median(abs(x) for x in deltas),
            "max_absolute_country_growth_revision": max(abs(x) for x in deltas),
            "robust_sign_flips_both_endpoints_exceed_margin": robust,
            "flip_country_rates": [
                {"iso3": r["iso3"], old: r[old], new: r[new]}
                for r in changes
            ],
        }
    uga = next(r for r in rows if r["iso3"] == "UGA")
    if (uga["2024"] > 0) == (uga["2025"] > 0) or (uga["2025"] > 0) == (uga["2026"] > 0):
        raise ValueError("Non-monotone Uganda sign path not reproduced")
    if (uga["2024"] > 0) != (uga["2026"] > 0):
        raise ValueError("Uganda must not count as an end-to-end sign flip")
    result["non_monotone_example"] = {"iso3": "UGA", "rates": uga}
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Original artifact ZIP or JSON")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    original, source_hash = load_original(args.input)
    report = audit(original, source_hash)
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "n": report["fixed_2000_2019_cohort_n"],
        "robust_flips_at_0.005": {
            k: v["robust_sign_flips_both_endpoints_exceed_margin"]["0.005"]["count"]
            for k, v in report["pairs"].items()
        },
        "source_sha256": source_hash,
        "status": "INDEPENDENT_DESCRIPTIVE_SENSITIVITY_PASS_NOT_NOVELTY_PROOF",
    }, indent=2))

if __name__ == "__main__":
    main()
