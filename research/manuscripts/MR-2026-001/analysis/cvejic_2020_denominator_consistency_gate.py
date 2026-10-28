#!/usr/bin/env python3
"""Arithmetic-only check of published Cvejic et al. 2020 rounded survey percentages.

The source reports 35 enrolled farms, elsewhere 46 farmers, and eight rounded
percentages (including 6% explicitly described as two dissatisfied farmers).
This script tests a *hypothetical common denominator*, not source-verified
respondent counts or survey microdata. No field or survey data are fabricated.
"""
import json
from pathlib import Path

DOI = "10.3390/agronomy10091238"
SOURCE = "https://www.mdpi.com/2073-4395/10/9/1238"
PERCENTAGES = [83, 71, 49, 40, 11, 6, 17, 66]
KNOWN_COUNT = {"percentage": 6, "respondents": 2}
UPPER_BOUND = 46  # sensitivity range informed by source's conflicting "46 farmers" text

def rounded_percent(k: int, n: int) -> int:
    # Conventional half-up nearest whole percent, not Python banker's rounding.
    return (200 * k + n) // (2 * n)

def possible_counts(pct: int, n: int) -> list[int]:
    return [k for k in range(n + 1) if rounded_percent(k, n) == pct]

def main() -> None:
    feasible = []
    for n in range(2, UPPER_BOUND + 1):
        if rounded_percent(KNOWN_COUNT["respondents"], n) != 6:
            continue
        counts = [possible_counts(p, n) for p in PERCENTAGES]
        if all(counts):
            feasible.append({"hypothetical_n": n,
                             "one_compatible_count_each": [x[0] for x in counts]})
    assert len(feasible) == 1 and feasible[0]["hypothetical_n"] == 35, feasible
    assert feasible[0]["one_compatible_count_each"] == [29, 25, 17, 14, 4, 2, 6, 23]
    report = {
        "doi": DOI, "publisher": SOURCE,
        "published_rounded_percentages": PERCENTAGES,
        "explicit_dissatisfied_count": 2,
        "candidate_common_denominators_tested": "2..46",
        "rounding_assumption": "nearest integer percentage, half-up",
        "conditional_common_denominator_solution": feasible,
        "scientific_verdict": "ARITHMETICALLY CONSISTENT, NOT INDEPENDENTLY VERIFIED",
        "limits": [
            "Source separately states 35 farms and 46 farmers; units may differ.",
            "Survey items may have different response bases or missingness.",
            "Published whole percentages may not follow nearest-integer rounding.",
            "Do not present inferred integer counts or 35 as observed respondent data."
        ]
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    out = Path("cvejic_rounded_denominator_consistency.json")
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
