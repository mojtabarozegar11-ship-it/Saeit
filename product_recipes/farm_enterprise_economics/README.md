# Farm Enterprise Economics Toolkit — Edition 1.3

A working, offline agricultural enterprise calculator written in Python 3.8+.
It estimates contribution margin, annual operating result, break-even sales
quantity, nine price/quantity sensitivity cases for each enterprise, and nine
correlated portfolio-wide stress scenarios. It can export an accessible,
self-contained HTML management report for offline viewing or printing.
All numerical assumptions are entered by the user. No external data feeds,
API keys, payment accounts or network connections are required.

## Getting started

1. Install Python 3.8 or later (no third-party packages).
2. Copy example_inputs.json and replace ALL illustrative values with your own.
3. Run:

   python calculator.py example_inputs.json --json-output results.json --csv-output scenarios.csv --html-output management-report.html

4. Open management-report.html in any browser, including without an internet
   connection. Review the outputs; never treat scenarios as forecasts.

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

## Precision of unit prices and unit costs

Edition 1.3 preserves per-unit quantities at the actual user-entered decimal
precision. This matters when a commodity is priced per gram, litre fraction,
seed, kilowatt-hour, or another small unit: `0.005` must not be displayed as
`0.00` and mistaken for a zero price in the offline management report.

Each enterprise JSON result includes additive fields:

- `unit_price_exact`: entered unit selling price without cents rounding.
- `variable_cost_per_unit_exact`: entered unit variable cost without cents rounding.
- `contribution_per_unit_exact`: derived unit contribution at model precision.
- `break_even_unit_price_unrounded`: model-precision break-even selling price
  at the planned sold volume, or null when undefined.

The pre-existing `unit_price`, `variable_cost_per_unit`, `contribution_per_unit`
and `break_even_unit_price_at_planned_volume` fields remain cents-rounded for
existing consumers. Do NOT use those legacy display fields to make decisions
about sub-cent commodities. The HTML table uses the precision-preserving values.
Portfolio monetary totals still display two decimals in the declared currency;
this is a presentation choice, not a claim about minor currency units or
rounding rules in a particular country. Portfolio revenue, expenses, contribution
and profit are summed from original Decimal quantities and costs **before**
final display rounding. As a result, the portfolio total can differ by a few
minor units from the sum of the individually rounded enterprise display rows.
This is intentional: the model does not silently discard sub-cent values.
The unshocked portfolio scenario must equal the portfolio operating profit.
Calculations use unrounded Decimal inputs, subject to the documented 80-digit
model precision.

## Whole-farm portfolio risk overview

The JSON output contains `portfolio_scenario_results` with nine stress rows.
Each row applies the SAME sales-volume multiplier (0.80, 1.00 or 1.20) and
selling-price multiplier (0.90, 1.00 or 1.10) across every enterprise.
For each enterprise, the selected sold-volume, received unit price, variable
unit cost, allocated fixed cost and selling fee determine operating profit;
portfolio totals add enterprise operating profits once. The middle scenario
must equal the baseline portfolio operating profit.

The correlated model is deliberately conservative about shared movements but
does not estimate probabilities, correlations from data or risk-adjusted returns.
It cannot establish likelihoods or investment suitability. It is useful for
spotting portfolio exposure to the same shock.

## Offline HTML management report

`--html-output management-report.html` creates a complete HTML document with
portfolio key figures, enterprise operating results, and a whole-portfolio
stress table. It contains no remote links, scripts, trackers or external
resources. User-entered labels are HTML-escaped; the report works offline,
supports browser printing and has horizontally scrollable tables on narrow
screens. Keep the generated report private when it contains sensitive business
assumptions or financial information.

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

## Customer data and report file safety

Keep your original input JSON. The CLI refuses to use the same resolved path for
its input and any of its JSON, CSV or HTML outputs; it also refuses to assign
the same destination to two different output formats. Such collisions exit
with `INPUT_ERROR` before any output file is written. Use separate filenames
for each report. Reusing an existing, distinct output filename still replaces
that previous report, so select your destination deliberately.

## Spreadsheet security

Enterprise names must start with a Unicode letter or number and may not
contain control characters. This deliberately rejects labels that could be
interpreted as spreadsheet formulas when exported to CSV (including initial
\`=\`, \`+\`, \`-\`, \`@\` and their full-width forms). CSV fields are always
double-quoted. These safeguards protect against a common spreadsheet injection
class; do not disable them when modifying the export code. Negative modeled
profits are generated numeric results, not user-supplied formula strings.

Input numbers in the supplied example are synthetic and are **not** claims
about agriculture in any particular country or market. The tool does not
pretend to use scientific sources or current prices.

## Verification and support

To run the included automated tests:

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
