# Agricultural Water Budget Economics — Offline Decision Aid

A real, working Python 3.8+ scenario calculator to allocate a **user-supplied**
irrigation water budget across crops with different gross margins per hectare
and water requirements per hectare.

## Use

1. Edit `example_inputs.json` with your **own locally verified values**.
2. Run `python calculator.py example_inputs.json --json-output allocation.json --csv-output allocation.csv`.
3. Review feasible fractional crop areas and water use. No API or packages are needed.
4. Run product QA: `python -m unittest -v test_calculator.py`.

Inputs: consistent `currency`, `water_available_m3` and 1–100 crop
records with `name`, `max_area_ha`, `water_m3_per_ha` (> 0), and
`gross_margin_per_ha` (>= 0). Keep the accounting horizon identical
across all crops. Use crop gross margins measured **before allocated
fixed costs, financing and tax**.

## Model

Rank crops by gross margin / required water (currency/m³). Allocate each
crop up to its maximum area using the remaining water. Partial hectare
allocation is allowed; zero-margin crops are not allocated.

This is optimal for the **restricted continuous one-resource linear model**
only, under constant gross margin and water consumption per hectare.
It does **not** optimize real irrigation schedules or agronomic suitability,
rotation constraints, crop complementarities, land limits beyond crop-specific
caps, water rights, production uncertainty, crop quality, market access,
labor, seasonality or investment finance.

The example is fully **illustrative and synthetic**. No live market or crop
water coefficients are asserted. The user must independently verify actual
water availability, legal permissions, and all crop-specific assumptions.
Use as a planning aid, not agronomic, regulatory, or investment advice.

## Privacy and release

Works completely offline; no telemetry, remote requests, customer order,
subscription or payment. Factory output is a PRIVATE QA candidate.
Technical tests do not establish scientific, market or commercial fitness.
Final licensing and public release need review and authorization.

## C02 input safety and numerical precision

All numeric inputs must be finite, nonnegative, at most 10^20 and have
no more than six decimal places. Per-hectare water demand must be positive.
These constraints prevent runaway numeric exponents, invalid CSV results
and quantization exceptions. Arithmetic uses 80 significant decimal digits.

Crop names must begin with a Unicode letter/number, contain no embedded
control characters, and cannot start with spreadsheet formula operators
(=, +, -, @). This blocks a common CSV formula-injection vector.
Downstream spreadsheet imports still require ordinary data-security review.

The aggregate gross margin uses unrounded allocation quantities. Displayed
row outputs are rounded to six decimal places; their visible sum can differ
very slightly from the rounded aggregate because of rounding.

Buyer acceptance dossier:
`deliverables/products/water_budget_economics/commercial_package.md`.
Preliminary non-sensitive customer data contract:
`deliverables/services/water-production/client_intake.schema.json`.

**State:** Technical hardening in a draft branch only; no deployment,
third-party field validation, paid order or sales-readiness attestation.
