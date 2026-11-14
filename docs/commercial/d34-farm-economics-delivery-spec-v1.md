# D34-01 | Agricultural enterprise profitability assessment — delivery specification v1
Status: INTERNAL / NOT FOR SALE / OWNER PRICE APPROVAL REQUIRED
Owner: Cycle D, scientific evidence and assumptions to be checked by Cycle B.

## Customer eligibility and scope
Only farms that voluntarily provide a production period, output quantities and units, revenue and cost records, and the right to share them. Do not solicit or store passwords, banking credentials, personal IDs or customer-level records in a public form. Accept CSV/XLSX only through an authorized secure workflow, not public query strings.

## Intake schema (mandatory)
- enterprise_id (non-identifying pseudonym), enterprise_type, accounting_period_start, accounting_period_end, reporting_currency and output_unit.
- production_quantity >= 0; sold_quantity >= 0 and <= production_quantity unless inventory reconciliation supplied.
- sales_revenue >= 0, other_revenue >= 0; variable_cost >= 0; fixed_cost >= 0; imputed_family_labor and land opportunity cost explicitly included/excluded.
- cost allocation method and provenance for each number; missing values are not silently treated as zero.
- explicit tax, inflation, subsidy, depreciation and financing treatment.

## Calculations and controls
Total revenue = sales + other operating revenue.
Contribution = total revenue - variable cost.
Operating surplus = contribution - fixed cost.
Economic profit = operating surplus - included opportunity costs.
Contribution margin per saleable unit = unit realized revenue - variable cost per unit, only if quantity > 0 and allocation justified.
Break-even output = fixed cost / positive contribution per unit; if margin <= 0 return NOT_ATTAINABLE, not infinity or zero.
Sensitivity table: output price -10%, baseline, +10%; variable input cost -10%, baseline, +10%; all other assumptions fixed and labelled. No extrapolation of causality.
Reconcile subtotals and units; reject NaN, infinity, negative quantities, inconsistent currency or impossible sold > produced absent reconciliation. Round display only; retain decimal precision in working calculations.

## Customer deliverable
A versioned Persian PDF report with: executive findings, enterprise profile, provenance/assumptions register, cost and revenue tables, contribution and economic profit, break-even, sensitivity matrix, uncertainty/limitations, action recommendations with conditional evidence, date, analyst/reviewer and source version. Machine-readable CSV calculation appendix and correction log where authorized.

## Acceptance gate
1. Source provenance complete and rights to process verified.
2. Input reconciliation signed off by analyst; unresolved values flagged, never invented.
3. Independently reproduce two numerical examples and break-even from source dataset.
4. B reviews scientific validity of assumptions; client reviews scope and data period.
5. Price/capacity approved in writing before any offer, invoice or order.
6. Final artifact hash and controlled delivery receipt verified after authorized order/payment.

## Commercial approval record (unapproved)
Proposed price: TO_BE_APPROVED. Approved price: NONE. Payment rail: NOT_VERIFIED. Lead: NONE VERIFIED. Contract: NONE. Live status: NOT_DEPLOYED.
No claim of legal, tax or investment advice. This is a delivery specification, not a paid engagement.
