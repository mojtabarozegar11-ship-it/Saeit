#!/usr/bin/env python3
"""Reproduce the *conditional* respondent-denominator compatibility audit.

Source: Cvejić et al. (2020), Agronomy 10(9):1238, Results (2020
three-weekly telephone interviews), DOI 10.3390/agronomy10091238.

IMPORTANT: The paper does not explicitly identify one 2020 respondent
denominator for all eight statements. This script only asks whether one
shared denominator is arithmetically possible, assuming all reported
whole percentages were rounded to the nearest integer, and "6% (two
farmers)" describes the same response base. It does not establish that
all percentages share a response base or that 35 farmers responded.
"""
from fractions import Fraction
import json

PERCENTAGES = {
    "reported_using_IDSS": 83,
    "regularly_viewing_soil_moisture": 71,
    "unchanged_irrigation_duration": 49,
    "more_frequent_shorter_irrigation": 40,
    "did_not_use_but_followed_reports": 11,
    "dissatisfied_two_farmers": 6,
    "partly_satisfied": 17,
    "very_satisfied": 66,
}


def compatible(k: int, n: int, p: int) -> bool:
    # [p-0.5, p+0.5): integer-rounded percentage without floats.
    pct = Fraction(100 * k, n)
    return Fraction(2 * p - 1, 2) <= pct < Fraction(2 * p + 1, 2)


def evaluate():
    # "two farmers = 6%" bounds n to 31..36 under these assumptions;
    # 1..1000 is deliberately broader, with the explicit two-person constraint.
    candidates = []
    for n in range(1, 1001):
        if not compatible(2, n, 6):
            continue
        mapping = {}
        for name, p in PERCENTAGES.items():
            possible = [k for k in range(n + 1) if compatible(k, n, p)]
            if not possible:
                break
            mapping[name] = possible
        else:
            if 2 in mapping["dissatisfied_two_farmers"]:
                candidates.append({"denominator": n, "compatible_counts": mapping})
    return {
        "source": "https://doi.org/10.3390/agronomy10091238",
        "hypothesis": "one common 2020 respondent denominator, whole-percent nearest-integer rounding",
        "additional_source_constraint": "6% dissatisfied = exactly two farmers",
        "candidates": candidates,
        "inference_limit": "arithmetic compatibility only; not observed sample size or verified adherence",
    }


if __name__ == "__main__":
    out = evaluate()
    assert len(out["candidates"]) == 1
    assert out["candidates"][0]["denominator"] == 35
    assert [x[0] for x in out["candidates"][0]["compatible_counts"].values()] == [29, 25, 17, 14, 4, 2, 6, 23]
    print(json.dumps(out, indent=2, ensure_ascii=False))
