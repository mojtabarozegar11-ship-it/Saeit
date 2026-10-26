# Farm Enterprise Economics Toolkit — Edition 1.0

A working, offline agricultural enterprise calculator written in Python 3.8+.
It estimates contribution margin, annual operating result, break-even sales
quantity, and nine price/quantity sensitivity cases for each enterprise.
All numerical assumptions are entered by the user. No external data feeds,
API keys, payment accounts or network connections are required.

## Getting started

1. Install Python 3.8 or later (no third-party packages).
2. Copy example_inputs.json and replace ALL illustrative values with your own.
3. Run:

   python calculator.py example_inputs.json --json-output results.json --csv-output scenarios.csv

4. Review the outputs. Never treat scenarios as guaranteed forecasts.

## Inputs

Each item in the enterprises list must provide:

| Field | Definition | Example (illustrative only) |
| --- | --- | --- |
| name | Unique enterprise label | Illustrative Orchard |
| units_sold | Annual or period units actually sold | 1000 |
| unit_price | Price received per sold unit, same currency as all costs | 10 |
| variable_cost_per_unit | Incremental cost per unit sold | 4 |
| allocated_fixed_cost | Fixed cost assigned to that enterprise for the same period | 3000 |
| selling_fee_percent | Optional percent of gross sales charged as fees | 5 |

Set currency to a consistent label such as USD, CAD, IRR, EUR or AED. The tool
never performs currency conversion.

## Formulas

Revenue = units_sold * unit_price.

Selling fees = revenue * selling_fee_percent / 100.

Variable cost = units_sold * variable_cost_per_unit.

Unit contribution = unit_price * (1 - selling_fee_percent / 100)
                    - variable_cost_per_unit.

Operating profit BEFORE depreciation, financing and taxes =
revenue - selling fees - variable costs - allocated fixed costs.

Break-even units = ceil(allocated_fixed_cost / unit contribution), provided
unit contribution is greater than zero. Otherwise break-even quantity is
undefined: selling more units at that unit contribution will not cover
positive fixed costs. When fixed costs are zero and unit contribution is
positive, the mathematical threshold is zero; commercial feasibility still
depends on real sales and constraints.

Nine stress tests per enterprise vary realized volume by -20%, 0%, +20%
and unit selling price by -10%, 0%, +10%. Selling-fee percentage, variable
cost per sold unit, and fixed cost remain unchanged.

## How to interpret a scenario

- The best-case sensitivity row is **not** a projected outcome.
- Never combine quantities, production yields and selling prices with
  inconsistent accounting periods or units.
- Allocate shared overhead consistently: do not charge the same shared cost
  to multiple enterprises unless intentionally apportioning shares.
- Sales volume is not harvest volume; account separately for unsold, damaged,
  wasted, lost or inventory-held output before preparing the input data.
- Unit variable costs can change with yield, volume and input prices. The
  sensitivity engine holds them constant as an explicit simplifying assumption.
- Verify that data quality, permits, market access, liquidity and seasonality
  are satisfactory before making investments.

## Model boundaries

This version intentionally excludes depreciation, borrowing costs, tax,
working capital, capital investment, inflation, land appreciation, yield-risk
distributions, cash flow timing, discounted valuation and financing structure.
Consequently, results are **contribution accounting illustrations**, not full
investment appraisal, tax accounting, or professional financial advice.

Each numeric input must be finite, no longer than 64 characters, and have
absolute magnitude no greater than 10^20; this prevents unbounded precision,
resource exhaustion and obscure decimal runtime failures. Internal arithmetic
uses 80 significant digits to support aggregate totals for high-unit currencies,
including IRR, without failing during cents rounding. Monetary displays are
rounded to two decimal places; this is not an exchange-rate conversion.

Input numbers in the supplied example are synthetic and are **not** claims
about agriculture in any particular country or market. The tool does not
pretend to use scientific sources or current prices.

## Verification and support

To run the included seven automated tests:

   python -m unittest -v test_calculator.py

No telemetry is collected; all inputs and outputs remain on the device.
The software rejects negative quantities/costs, non-finite numeric values,
duplicate enterprise labels, and fee percentages outside 0–100%.

## Editorial / commercial status

This toolkit is a technical candidate generated within the Saeit factory.
Its examples and calculation methods must receive final product QA, security,
owner licensing, commercial pricing, support-channel and distribution approval
before it is represented as a commercially released product. Do not present
this internal build as already available for sale.
