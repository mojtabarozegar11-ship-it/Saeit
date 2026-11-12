# Agricultural Water Budget Economics — buyer acceptance dossier

**State:** Source candidate; NOT publicly released, sold, independently agronomically certified or payment-enabled. C02 owner release approval remains required.

## Scope and buyer
For farm operators, agricultural consulting teams and greenhouse cooperatives with verified local water availability and crop-level cost assumptions. This offline analytical tool evaluates a **continuous single-water-resource linear crop allocation scenario**. It does not prescribe irrigation or determine water rights.

## Delivery packet
- `product_recipes/water_budget_economics/calculator.py`: offline Python >=3.8 scenario calculator
- `product_recipes/water_budget_economics/example_inputs.json`: synthetic illustrative data
- `product_recipes/water_budget_economics/test_calculator.py`: reproducible regression tests
- `product_recipes/water_budget_economics/README.md`: methodology and limitations
- Outputs generated locally: machine-readable JSON and CSV allocation table

## User workflow
1. Enter a consistent accounting period, currency, legally available water budget, and for each crop maximum area, positive cubic metres per hectare and nonnegative gross margin per hectare.
2. Supply measured/verified agronomic coefficients independently. Source model does not verify any of these inputs.
3. Run `python calculator.py example_inputs.json --json-output allocation.json --csv-output allocation.csv` offline.
4. Inspect the fractional hectares, total water usage, unused water, aggregate gross margin and marginal value. Do not treat results as real-farm optimality or profitability guarantees.

## Acceptance and QA
1. All inputs validated: finite, nonnegative, bounded <=1e20 and no more than six decimal places; water coefficient >0.
2. Crop labels beginning with spreadsheet formula operators or containing controls are rejected, preventing direct CSV formula injection through crop names.
3. Repeated crop labels, non-finite, invalid water budgets or over-precision values rejected.
4. End-to-end allocation does not exceed the client water budget. Zero-margin crops receive no scarce water.
5. An independent small-case reference oracle and edge-case safety tests must pass.
6. Aggregate margin derives from unrounded internal quantities; displayed row figures are rounded to six decimal places.
7. File checksums and buyer ZIP validation will be generated only after approved commercial packaging.
8. No telemetry, personal data, secrets, network access, account registration or embedded payment.

## Business rules
**Indicative project time:** Subject to data complexity; confirm delivery period after reviewing client inputs.
**Price:** Subject to owner approval after scope determination; no price or discount has been publicly authorized.
**Order channel:** An owner-approved customer request route is required before offering this service publicly.
**Payment:** BLOCKED until a lawful, validated, owner-authorized channel is available.
**Support:** Deliver a user guide, limitations notice, reproducible input/output and an agreed corrective-maintenance window only after support terms are approved.

## Non-negotiable release gate
A successful offline regression test is not equivalent to real agricultural field validation, technical suitability, legal rights, payment readiness, sale or publisher approval. No revenue is recorded without actual independently verified receipt.
