"""Source-audited arithmetic checks for Okayama et al. (2025), DOI 10.1007/s10661-024-13602-1.
Read from PMC full-text HTML Table 1 and Table 3 on 2026-10-25.
Checks are for transcription/internal sums, NOT validation of original measurements.
"""
SOURCE = "https://pmc.ncbi.nlm.nih.gov/articles/PMC11732880/"
TABLE1 = [
    ("Tochihara TD1", 2362, 700, 3062),
    ("Tochihara TD2", 568, 200, 768),
    ("Tochihara TD3", 288, 80, 368),
    ("Heibara HD1", 3148, 800, 3948),
    ("Heibara HD2", 1122, 400, 1522),
    ("Heibara HD3", 74, 24, 98),
]
TABLE3 = [
    ("Tochihara irrigation", 1450, 400, 1850),
    ("Tochihara appropriate", 1848, 500, 2348),
    ("Heibara irrigation", 2162, 500, 3091),
    ("Heibara appropriate", 2226, 620, 1189),
]

def check():
    assert all(train + test == printed for _, train, test, printed in TABLE1)
    assert sum(r[1] + r[2] for r in TABLE1) == 9766
    discrepancies = [
        (name, train + test, printed)
        for name, train, test, printed in TABLE3
        if train + test != printed
    ]
    assert discrepancies == [
        ("Heibara irrigation", 2662, 3091),
        ("Heibara appropriate", 2846, 1189),
    ], discrepancies
    assert sum(r[1] + r[2] for r in TABLE3) == 9706
    assert sum(r[3] for r in TABLE3) == 8478
    assert abs((0.93 - 0.50) - 0.43) < 1e-12
    assert abs((0.88 - 0.51) - 0.37) < 1e-12
    print("PASS: six Table 1 sums, two flagged Table 3 discrepancies, totals, cross-field differences")
    for name, calculated, printed in discrepancies:
        print(f"REQUIRES PDF SOURCE CHECK: {name}: train+test={calculated}, printed={printed}")
    print("No water-saving or farmer-adoption effect is inferred.")

if __name__ == "__main__":
    check()
