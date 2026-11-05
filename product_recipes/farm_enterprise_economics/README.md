# Farm Enterprise Economics Toolkit — Edition 1.3

A working, offline agricultural enterprise calculator written in Python 3.8+.
It estimates contribution margin, annual operating result, break-even sales
quantity, nine price/quantity sensitivity cases for each enterprise, and nine
correlated portfolio-wide stress scenarios. It can export an accessible,
self-contained HTML management report for offline viewing or printing.
All numerical assumptions are entered by the user. No external data feeds,
API keys, payment accounts or network connections are required.

For a practical first-use walkthrough, worked farm example, file explanations, and
pre-decision checklist, see the [Customer Guide](CUSTOMER_GUIDE.md).

## Getting started

1. Install Python 3.8 or later (no third-party packages).
2. Copy example_inputs.json and replace ALL illustrative values with your own.
3. Run:

   python calculator.py example_inputs.json --json-output results.json --csv-output scenarios.csv --three-factor-csv-output joint-stress.csv --html-output management-report.html

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

JSON decimal literals are read directly as exact decimal numbers, without
conversion through binary floating-point. For example, an entered unit price
of `0.123456789012345678901234` retains all its digits in the exact-value
report field; displayed monetary totals are still rounded to 0.01 currency
units. Numeric inputs remain subject to the documented magnitude limits.

## Formulas

Revenue = units_sold * unit_price.

Selling fees = revenue * selling_fee_percent / 100.

Variable cost = units_sold * variable_cost_per_unit.

Unit contribution = unit_price * (1 - selling_fee_percent / 100)
                    - variable_cost_per_unit.

Operating profit BEFORE depreciation, financing and taxes =
revenue - selling fees - variable costs - allocated fixed costs.

For fractional commodity sales (for example, 1.8 tonnes), the mathematical
break-even quantity is `allocated_fixed_cost / unit contribution`, provided
unit contribution is positive. The JSON field `break_even_quantity_continuous`
preserves this threshold at model precision; likewise,
`margin_of_safety_quantity_continuous` and
`margin_of_safety_percent_continuous` measure the fractional quantity cushion.
The offline HTML report displays these continuous values.

The legacy `break_even_units` field deliberately rounds the break-even
quantity UP to the next whole unit, and the legacy `margin_of_safety_units`
and `margin_of_safety_percent` fields use that whole-unit threshold for
compatibility with existing integer-piece consumers. This can misleadingly
show a negative cushion for profitable fractional sales, so use the continuous
fields for kilograms, litres, tonnes and other fractional trade units. When
unit contribution is nonpositive and fixed costs are positive, break-even
quantity is undefined: selling more units cannot offset those costs. If both
unit contribution and fixed costs are zero, every quantity is exactly at
break-even; the reported minimum threshold is zero and margin-of-safety
fields are `null` because there is no positive contribution cushion. With
zero fixed costs and positive contribution, the threshold is also zero, but
the margin of safety can be calculated normally. Commercial feasibility still
depends on real demand and constraints.

The original nine stress tests per enterprise vary realized sales volume by
-20%, 0%, +20% and selling price by -10%, 0%, +10%; those legacy outputs remain
unchanged for existing consumers. The new `three_factor_scenario_results` and
`three_factor_portfolio_results` add 27 combinations of volume (80/100/120%),
selling price (90/100/110%) and **variable cost per unit** (90/100/110%).
For example, an adverse combination of less sold product, a lower farm-gate
price and more expensive inputs can be evaluated jointly. The whole-farm figure
applies each common shock across all enterprises and deducts each allocated
fixed cost once. Fixed costs and selling-fee rates stay constant in all
scenarios. The HTML report includes the 27 whole-farm outcomes. The optional
`--three-factor-csv-output joint-stress.csv` export contains all 27 scenarios
for **each enterprise** plus all 27 **whole-farm** scenarios, with an explicit
`scope` column distinguishing enterprise and portfolio rows. This supplements
rather than changes the backward-compatible `--csv-output` (nine two-factor
enterprise scenarios). All CSV fields are quoted for spreadsheet safety.

These figures are scenario arithmetic, not estimated probabilities, yield
forecasts or predictive confidence intervals. Price, output and input-cost
changes can interact in reality; this deterministic model holds all other
factors fixed. Penn State Extension discusses enterprise budgets and the
importance of input-cost and sale-price sensitivity:
https://extension.psu.edu/budgeting-for-agricultural-decision-making
https://extension.psu.edu/cost-of-production-the-most-important-number-on-your-farm

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
absolute magnitude no greater than 10^20. Nonzero magnitudes finer than 1e-24
are rejected; zero with exponent notation is canonicalized to 0. This avoids
short exponent strings (for example, `1e-1000000000`) expanding into enormous
fixed-point report fields and exhausting memory. The 24-decimal-place lower
bound is a supported engineering precision limit, not a farming measurement
claim. It also limits resource exhaustion and obscure decimal runtime failures. Internal arithmetic
uses 80 significant digits to support aggregate totals for high-unit currencies,
including IRR, without failing during cents rounding. Monetary displays are
rounded to two decimal places; this is not an exchange-rate conversion.

## Reproducibility fingerprint and read-only report verification

The JSON and offline HTML outputs contain `input_fingerprint_sha256`, a
SHA-256 digest of the *accepted and normalized economic inputs*: currency,
enterprise name, quantity, exact input price, exact variable unit cost,
exact allocated fixed cost and fee percentage, in enterprise order. It is
independent of whitespace, unrelated metadata and JSON object key order.
No input file is uploaded, and the fingerprint is computed offline.

To check a saved JSON report against the original assumptions and the
currently installed calculator version:

   python calculator.py example_inputs.json --verify-json results.json

This read-only operation recomputes all results and compares the entire
stored report with the newly calculated report, including the scenarios.
It exits with an input error when anything differs; it neither rewrites
the original inputs nor modifies the saved report. Do not combine
`--verify-json` with report-generation output flags.

**Limits:** This digest is NOT a digital signature, independent peer review,
proof of intellectual-property ownership or evidence that user-provided
prices/costs match real markets. A malicious actor can edit both the inputs
and result file and then recompute a matching digest. Retain a separately
controlled copy of the input and the installed software version for genuine
external audit. Different calculator versions can legitimately generate
different report fields even when input fingerprints match.

## Customer data and report file safety

Keep your original input JSON. The CLI refuses to use the same resolved path for
its input and any of its JSON, CSV or HTML outputs; it also refuses to assign
the same destination to two different output formats. Such collisions exit
with `INPUT_ERROR` before any output file is written. Use separate filenames
for each report. Reusing an existing, distinct output filename still replaces
that previous report, so select your destination deliberately.

The software now fully stages ALL requested JSON/CSV/HTML report files in
temporary files on their destination filesystems, flushes the content, and
only then begins to atomically replace each destination. A failure while
staging one format leaves all existing report files untouched and removes
temporary staging files. Each replacement is atomic, so a destination
never contains a half-written report. **Multiple destination files are not
one cross-file transaction:** if a filesystem fails between final renames,
some new complete reports and some old complete reports may remain; the
saved input fingerprint and read-only verification help identify such a
mixed-version set. Maintain backups of valuable existing reports.

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

## International market and scientific comparison

A six-provider, first-party-sourced comparative evidence register and honest
quality-gap list is maintained in [BENCHMARKS_2026-11-03.md](BENCHMARKS_2026-11-03.md).
It is documentary research only; no independent market superiority or QC1000
acceptance is claimed.

## Verification and support

To run the included automated tests:

   python -m unittest -v test_calculator.py

No telemetry is collected; all inputs and outputs remain on the device.
The software rejects negative quantities/costs, non-finite numeric values,
duplicate enterprise labels, and fee percentages outside 0–100%.

### Product-bound technical evidence (offline)

The factory can create a fresh, immutable technical evidence folder without
GitHub Actions, APIs, external accounts, or production deployment:

    python -B build_technical_evidence.py --evidence-dir /path/to/new-private-evidence-folder

The capture re-runs every calculator unit test, generates and hashes the four
illustrative customer-facing report formats, and records exact recipe and test
source hashes. Six candidate technical criteria (Q035, Q036, Q037, Q061, Q063,
Q064) receive distinct evidence records. The manifest is written last; a
failed run cannot create a completion receipt. Use a **new empty folder** for
each edition so old evidence cannot be silently overwritten.

These records cover internally reproducible technical checks only. They do
**not** award quality points, verify real customer assumptions, authenticate
three independent reviewers, certify 1000/1000, or authorize sale or handoff.
The factory's separate signed release and receiving-cycle gates remain intact.

## Editorial / commercial status

This toolkit is a technical candidate generated within the Saeit factory.
Its examples and calculation methods must receive final product QA, security,
owner licensing, commercial pricing, support-channel and distribution approval
before it is represented as a commercially released product. Do not present
this internal build as already available for sale.

