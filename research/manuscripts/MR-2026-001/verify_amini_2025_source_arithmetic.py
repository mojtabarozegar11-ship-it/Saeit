#!/usr/bin/env python3
"""Arithmetic checks of explicitly published figures; NOT a raw-data reanalysis.

Source: Amini, Emami & Dehghanisanij (2025), Scientific Reports 15:42480.
https://www.nature.com/articles/s41598-025-26567-z
DOI: 10.1038/s41598-025-26567-z
Source locators: Methods > Study area; Results > Irrigation management
and Results > Water productivity and crop yield.
"""
from math import isclose

# Publisher Methods: 110 L/s, 3 hours, 1188 cubic metres per hectare/turn.
flow_lps = 110
duration_hours = 3
assert isclose(flow_lps * duration_hours * 3600 / 1000, 1188.0, abs_tol=1e-10)

# Reported irrigation-depth direction by monitored farm (mm treatment-control).
# Values for F3/F4/F5/F6/F7/F8 are transcribed from the publisher's narrative.
# F1/F2 are described as unchanged, not numerically re-estimated.
delta_mm = {"F1": 0.0, "F2": 0.0, "F3": -158.4, "F4": 225.8,
            "F5": -253.6, "F6": -309.0, "F7": 292.7, "F8": -41.2}
assert len(delta_mm) == 8
assert sum(x < 0 for x in delta_mm.values()) == 4
assert sum(x > 0 for x in delta_mm.values()) == 2
assert sum(x == 0 for x in delta_mm.values()) == 2

# Explicitly document contradictions; do not silently average them.
# Publisher F6: +0.15 kg/m3 in one passage, approx +0.2 in another.
# Publisher F7: -1.3, -1.4 and -0.1 kg/m3 in separate passages.
reported_wp_differences = {"F6": (0.15, 0.2), "F7": (-1.3, -1.4, -0.1)}
assert len(set(reported_wp_differences["F6"])) > 1
assert len(set(reported_wp_differences["F7"])) > 1
print("PASS: irrigation-turn volume arithmetic")
print("PASS: field direction count (4 reduced, 2 increased, 2 unchanged)")
print("FLAG: inconsistent WP differences F6 and F7 require Table 5 check")
print("LIMITATION: raw table cells, individual field data and p-values NOT audited")
