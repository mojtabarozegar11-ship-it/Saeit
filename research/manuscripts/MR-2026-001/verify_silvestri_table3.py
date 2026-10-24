#!/usr/bin/env python3
"""Independent arithmetic QA of Silvestri et al. (2025), Sensors 25(23), 7188, Table 3.

This script rechecks published table entries; it does NOT reproduce model
simulations, validate field efficacy, or establish study inclusion.
Primary source: https://pmc.ncbi.nlm.nih.gov/articles/PMC12693864/#sec6-sensors-25-07188
DOI: https://doi.org/10.3390/s25237188
Reviewed 2026-10-24.
"""
from decimal import Decimal, ROUND_HALF_UP

# Rows: sector, observed baseline, Mamdani counterfactual, ANFIS counterfactual.
SECTORS = (
    (1, 4479, 1300, 975),
    (2, 11486, 5200, 4875),
    (3, 10931, 9750, 9100),
    (4, 23757, 8450, 6825),
)
PUBLISHED_TOTALS = (50653, 24700, 21775)
PUBLISHED_MEANS_ROUNDED = (12663, 6175, 5444)
PROSE_OBSERVED_MEAN = 1663  # A published prose/Table-3 mismatch, NOT corrected by us.


def percent_reduction(baseline: int, simulated: int) -> Decimal:
    return (Decimal(100) * (Decimal(baseline) - Decimal(simulated))
            / Decimal(baseline))


def run() -> None:
    totals = tuple(sum(row[col] for row in SECTORS) for col in (1, 2, 3))
    assert totals == PUBLISHED_TOTALS, (totals, PUBLISHED_TOTALS)
    for total, rounded in zip(totals, PUBLISHED_MEANS_ROUNDED):
        actual = Decimal(total) / Decimal(len(SECTORS))
        assert abs(actual - Decimal(rounded)) <= Decimal("0.5"), (actual, rounded)
    assert PROSE_OBSERVED_MEAN != PUBLISHED_MEANS_ROUNDED[0]
    mamdani = percent_reduction(totals[0], totals[1])
    anfis = percent_reduction(totals[0], totals[2])
    assert Decimal("51") < mamdani < Decimal("52")
    assert Decimal("57") < anfis < Decimal("58")
    for label, pct in (("Mamdani", mamdani), ("ANFIS", anfis)):
        print(f"{label} modeled reduction vs observed baseline (Table 3): "
              f"{pct.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}%")
    print("PASS: all four sector rows sum to the printed totals.")
    print("PASS: printed averages are rounded consistently with sector totals.")
    print("CONFIRMED SOURCE INCONSISTENCY: prose says 1,663 L/row, "
          "Table 3 says 12,663 L/row.")
    print("CAUTION: comparisons are retrospective counterfactual predictions, "
          "not measured intervention savings or observed farmer adoption.")


if __name__ == "__main__":
    run()
