#!/usr/bin/env python3
"""Reproduce only arithmetic implied by Holt et al. (2025) publisher abstract.
No source tables, raw data or independent experiment were reanalyzed.
Publisher: https://acsess.onlinelibrary.wiley.com/doi/abs/10.1002/saj2.70101
"""
from fractions import Fraction
farm_years = (10, 9, 6)  # study farm-year participations, NOT unique farms
cuttings = 47  # across repeated fields and years; NOT independent farms
affected = 5
positive = 3
negative = 2
assert sum(farm_years) == 25
assert positive + negative == affected
assert 0 <= affected <= cuttings
assert Fraction(affected, cuttings) == Fraction(5, 47)
assert round(100 * affected / cuttings, 2) == 10.64
assert round(100 * positive / cuttings, 2) == 6.38
assert round(100 * negative / cuttings, 2) == 4.26
print("PASS: seven arithmetic assertions")
print("25 farm-year participations (not 25 unique farms); 5/47 cuttings = 10.64%.")
print("No statistical independence, uncertainty, causal effect, or pooled water savings inferred.")
