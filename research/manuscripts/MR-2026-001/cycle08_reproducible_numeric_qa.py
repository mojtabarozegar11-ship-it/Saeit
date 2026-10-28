"""Cycle08 arithmetic checks for published counts, NOT source-data reanalysis.
Source: Portoghese et al. 2025 DOI 10.1007/s11269-025-04316-1
and Nsoh et al. 2024 DOI 10.3390/s24237480.
No publisher datasets were downloaded. Python standard library only.
"""
from math import isclose

def pct(a, b):
    assert b > 0
    return 100.0 * a / b

# Portoghese §3.2, §3.4, §4.1, §5
assert isclose(pct(263, 300), 87.66666666666667, abs_tol=1e-10)
assert round(pct(191, 263)) == 73
assert isclose(pct(79, 263), 30.03802281368821, abs_tol=1e-10)
assert isclose(pct(19, 79), 24.050632911392405, abs_tol=1e-10)
assert isclose(889 - 790.5, 98.5, abs_tol=1e-10)
# The 98.5 EUR is a gross illustrative difference from another study,
# NOT net economic benefit; excludes control costs and transaction costs.

# Nsoh §2 reported literature review flow: initial and final counts differ
assert 1485 >= 462 >= 123
assert 166 - 123 == 43
assert isclose(pct(462, 1485), 31.11111111111111, abs_tol=1e-10)
# 43 is an arithmetic net increase; it does not independently establish
# the number of unique supplementary records or PRISMA flow.

print("cycle08 numeric QA: 8 assertions passed; source values publisher-reported")
