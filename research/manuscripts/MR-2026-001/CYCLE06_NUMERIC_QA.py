"""MR-2026-001 cycle 06: arithmetic checks of numbers printed by source authors.
No raw data reanalysis or scientific effect estimation. Run: python CYCLE06_NUMERIC_QA.py
"""
from math import isclose

# Monteiro et al. 2025, Methods: sample-size worked example.
n0 = (1.28 ** 2) * 0.5 * 0.5 / (0.05 ** 2)
reported_rounded_n0 = 164
finite_corrected = reported_rounded_n0 / (1 + reported_rounded_n0 / 371)
sample = 131
assert isclose(n0, 163.84, rel_tol=0, abs_tol=1e-9)
assert isclose(finite_corrected, 113.72710280373832, rel_tol=0, abs_tol=1e-9)
assert sample > finite_corrected
assert sample <= 371

# Nxumalo et al. 2026, Table 3 and §3.2.1:
# FAO-56 reference mid-season Kc=1.20, site range 1.25-1.35.
low_pct = 100 * (1.25 / 1.20 - 1)
high_pct = 100 * (1.35 / 1.20 - 1)
assert isclose(low_pct, 4.166666666666667, abs_tol=1e-9)
assert isclose(high_pct, 12.5, abs_tol=1e-9)

print(f"PASS: Monteiro n0={n0:.2f}; finite correction={finite_corrected:.3f}; actual responses={sample}")
print("NOTE: source prints 113 for corrected n; conventional rounding of 113.727 is 114,")
print("but this does not affect the claim that 131 completed questionnaires exceed either.")
print(f"PASS: Nxumalo Kc relative increases={low_pct:.2f}% to {high_pct:.2f}%.")
print("These are arithmetic audits of printed values, NOT field validation.")
