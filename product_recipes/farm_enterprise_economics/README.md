# Farm Enterprise Economics Toolkit — Edition 2.0 (offline browser + Python)

A working, offline agricultural enterprise calculator for a modern browser or Python 3.8+.
It estimates contribution margin, annual operating result, break-even sales
quantity, nine price/quantity sensitivity cases for each enterprise, and
optional land/water resource-efficiency calculations and a separate twelve-month
cash-flow budget showing liquidity shortages and end-of-month balances.
All numerical assumptions are entered by the user. No external data feeds,
API keys, payment accounts or network connections are required.

## Getting started — no software installation

1. Extract the product ZIP into a folder on your own device. **Keep the HTML and two JavaScript files together.**
2. Open `offline_calculator.html` in a modern browser (Chrome, Edge, Firefox or Safari with BigInt support).
3. Replace every **illustrative** enterprise input with your own measurements and prices. Add other farm activities if required.
4. In the 12-month cash plan, enter opening cash and monthly receipts and payments in the same currency. Defaults of zero mean **no cash has been modeled**; they must not be interpreted as validated forecasts.
5. Select **Calculate results**. Inspect the portfolio, break-even thresholds, scenarios, and **separate** month-end liquidity warnings.
6. Use **Save inputs as JSON**, **Save full report as JSON**, **Save scenarios as CSV**, **Save 12-month cash plan as CSV** or **Print / save as PDF** as needed.

This interface runs locally, with no network requests, account, analytics, cookies,
external scripts, price feeds or cloud storage. It does not save your data unless
you choose a download. Input JSON can be imported from your computer and is
checked before replacing the current form. Treat exported files as sensitive
business data; store them privately. A very small negative profit can display
as `-0.00` due to two-decimal monetary rounding.

The browser uses exact rational arithmetic internally, with decimal input
limited to 30 fractional places and without scientific `e` notation. This
matches the Python money and break-even outputs for supported inputs; use the
Python engine for other numeric notation. Do not mix long-period investments,
annual budgets and monthly prices: all input amounts must describe the same
accounting period and currency. If the exact break-even unit count exceeds the
safe JavaScript integer range it is exported as decimal **text**, not rounded.
When editing or importing JSON, quote fractional and large numbers as strings,
such as `"unit_price": "1234.567"`: browsers cannot preserve every decimal
digit of arbitrary unquoted JSON numbers. The bundled example uses this format.

## Alternative — Python command line

1. Install Python 3.8 or later (no third-party packages).
2. Copy example_inputs.json and replace ALL illustrative values with your own.
3. Run:

   python calculator.py example_inputs.json --json-output results.json --csv-output scenarios.csv --cashflow-csv-output monthly_cash.csv

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
| land_area_hectares | Optional **positive** cultivated area assigned to the same enterprise and accounting period | 2.5 |
| irrigation_water_m3 | Optional measured irrigation consumption for the same enterprise and period; zero is permitted for rainfed farming | 500 |

Set currency to a consistent label such as USD, CAD, IRR, EUR or AED. The tool
never performs currency conversion.

## Optional farm resource analysis

When `land_area_hectares` is supplied, the output reports sold units per
hectare and operating profit per hectare. When positive `irrigation_water_m3`
is supplied, it reports sold units and operating profit per cubic metre of
irrigation water. Water use of exactly zero is recorded, but ratios with a zero
denominator remain `null` rather than claiming infinite productivity.

For example, the illustrative enterprise with 1,000 sold units and 2,500
currency units of modeled operating profit uses 2.5 hectares and 500 m³ of
irrigation water if the operator **explicitly provides** those two quantities.
It would then display 400 sold units/ha, 1,000 currency units profit/ha,
2 sold units/m³, and 5 currency units profit/m³. These are mathematical
illustrations, not independent agronomic measurements.

`resource_coverage` identifies how many enterprises supplied each resource.
It reports portfolio resource totals **only when all enterprises** supplied
the corresponding quantity. A missing resource observation is not treated as
zero. Costs related to land and irrigation must already be allocated into the
existing variable or fixed cost fields; this extension does not add them again.
Portfolio land and water totals retain the precision entered by the operator;
they are physical quantities and are **never rounded to monetary cents**.
Do not interpret profit per hectare/water as an estimate of marginal value,
water-saving potential, hydrological impact, or recommended irrigation rates.

## Twelve-month liquidity planner (Edition 2.0)

The browser includes twelve editable monthly rows. The Python engine supports
the same optional top-level JSON input:

```json
"cashflow_plan": {
  "opening_cash": "1000.00",
  "months": [
    {"cash_receipts": "500.00", "operating_payments": "300.00",
     "asset_purchases": "0.00", "loan_receipts": "0.00",
     "loan_repayments": "0.00", "other_payments": "0.00"}
  ]
}
```

This is a *schema illustration only*: actual input requires **exactly twelve**
month objects, one for each month, each containing all six fields. The example
JSON shipped with the product contains the full twelve-month structure.

- Cash receipts are actually received customer cash, not billed sales or harvest.
- Operating payments are expenses actually paid, not accrual expense estimates.
- Asset purchases are cash spent on capital assets; they are *not* also entered
  as operating payments. Loan cash received is cash financing, *not* revenue.
- Loan repayments include principal and interest **cash paid**; other payments
  can include owner drawings and taxes, entered just once.
- Monthly net change = cash receipts + loan receipts − operating payments −
  asset purchases − loan repayments − other payments.
- Month-end cash = opening cash plus cumulative monthly net changes.
- The additional liquidity needed to avoid a **negative month-end balance** is
  the absolute size of the lowest negative month-end cash position. This is not
  a loan recommendation and does not model intra-month payment timing.

Every monthly monetary input must be nonnegative, finite, at most 10^20, and
expressible to at most two decimal places. The month-end balance **may be
negative** to flag a shortfall. The planner is separate from the enterprise
profit output; the two totals are intentionally not added together. Seasonal
timing is entered by the customer rather than guessed by the software. This
does not calculate opening receivables/payables, a balance sheet, loan amortization,
depreciation, tax liability, interest accrual, NPV or a lender-approved plan.

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

### Profitability ratios and consistent break-even outputs

For each enterprise, contribution margin percent = contribution margin / revenue × 100
and operating profit margin percent = operating profit / revenue × 100.
The portfolio ratios use **total portfolio contribution and profit divided by
total portfolio revenue**—not the arithmetic mean of enterprise percentages.
This matters when a small low-revenue enterprise has a large percentage margin.

If recorded sales revenue is zero, both percentages are `null`, not zero or
infinity. They are planning ratios and should not be interpreted as collected
cash, profit after taxes, or full return on invested capital.

**Operational margin of safety** is modeled sold quantity minus the *whole-unit,
rounded-up* break-even sales count. Both Python and browser engines follow this
rule to avoid reporting contradictory safety quantities. The continuous
(non-rounded) theoretical threshold is still used to derive the required
break-even *unit price*, not the inventory/sales count. For the supplied sample
of 1,000 sold units, unit contribution 5.50 and allocated fixed cost 3,000,
the break-even unit count is 546 and the safety is 454 units / 45.40%.

The offline product accepts ordinary Persian names including the zero-width
non-joiner. Unicode bidirectional override, embedding/isolating characters
and line separators are rejected in names to prevent CSV/spreadsheet display
spoofing; do not remove those checks.

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

The **enterprise-profit model** still excludes depreciation, borrowing costs,
tax, working capital, capital investment, inflation, yield-risk distributions,
discounted valuation and financing structure. The distinct monthly plan now
handles **user-entered cash movements** only, including asset purchases and
loan cash receipts/payments. Consequently, results are contribution accounting
and month-end liquidity illustrations, not full investment appraisal, tax
accounting, credit approval, or professional financial advice.

Each numeric input must be finite, no longer than 64 characters, and have
absolute magnitude no greater than 10^20; this prevents unbounded precision,
resource exhaustion and obscure decimal runtime failures. Internal arithmetic
uses 80 significant digits to support aggregate totals for high-unit currencies,
including IRR, without failing during cents rounding. Monetary displays are
rounded to two decimal places; this is not an exchange-rate conversion.

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

## Further reading (optional, online)

- Penn State Extension, *Budgeting for Agricultural Decision Making*:
  https://extension.psu.edu/budgeting-for-agricultural-decision-making
- Penn State Extension, *Product Pricing: What Do I Charge?*:
  https://extension.psu.edu/product-pricing-what-do-i-charge

These explain agricultural enterprise budgeting and break-even concepts.
They are reference reading, **not** sources of the synthetic sample values or
an endorsement or independent review of this product.

## Verification and support

To run the included automated tests (Python only, no Node needed):

   python -m unittest discover -v -p 'test_*.py'

The independent browser-versus-Python arithmetic comparison is an additional
source-repository CI check, intentionally separate from the buyer ZIP so
extracted private packages remain testable on a machine without Node.js.

No telemetry is collected; all inputs and outputs remain on the device.
The software rejects negative quantities/costs, non-finite numeric values,
duplicate enterprise labels, and fee percentages outside 0–100%.

## Editorial / commercial status

This toolkit is a technical candidate generated within the Saeit factory.
Its examples and calculation methods must receive final product QA, security,
owner licensing, commercial pricing, support-channel and distribution approval
before it is represented as a commercially released product. Do not present
this internal build as already available for sale.
