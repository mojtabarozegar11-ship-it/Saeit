# Farm economics service — client intake and delivery acceptance v1

Status: INTERNAL DRAFT / NOT PUBLISHED / PRICE NOT APPROVED. Owner: Cycle D. Related implementation: `tools/commercial/farm_economics_validator.py` and `farm_economics_cli.py` on `work/d-cycle32-service-offers-20261114`. Scientific sign-off belongs to cycle B; payment to E.

## Client request (complete before quoting)
- Business / farm name or pseudonymous enterprise ID:
- Authorized requester and secure reply channel (do not place personal data in GitHub):
- Crop or enterprise activity, region, production system, output unit:
- Reporting start/end dates (ISO YYYY-MM-DD), currency (ISO 4217):
- Decision requested (profitability, break-even, scenario comparison):
- Source records available and their provenance (invoices, production logs, accounting exports):
- Deadline, intended decision use, data-sharing restrictions:

## Minimum input fields (one enterprise-period per CSV row)
`enterprise_id,enterprise_type,period_start,period_end,currency,output_unit,production_quantity,sold_quantity,sales_revenue,other_revenue,variable_cost,fixed_cost,opportunity_cost`

All monetary values must use one consistent currency; quantities must use one consistent output unit. Monetary amounts are nonnegative decimal figures, not localized thousands-separated strings. Never include names, phone numbers, bank details, or client secrets in repository CSVs. Client supplies an explicit explanation of what is included in each cost category and whether unsold inventory is valued. A production period may not overlap another period for the same enterprise.

## Scope and exclusions
Deliver: input validation results, documented operating surplus and economic profit, break-even result only where model permits, assumptions and caveats, concise management interpretation, and a client review copy. The existing validator is an internal calculation aid, not a verified scientific or accounting opinion. No guarantee of profits, subsidy eligibility, tax compliance, or financing approval. Where production exceeds sold quantity, the existing model does **not** allocate unsold inventory cost to cost of goods sold and suppresses unit break-even; this is a material limitation to disclose. Other revenue is excluded from unit contribution margin. Independent scientific review is mandatory before a paid analytical conclusion.

## Intake acceptance gate
1. Requester confirms authority to share the data and permission for the specified processing purpose.
2. Period, unit, currency and enterprise identity are complete and internally consistent.
3. Costs are classified and source documents or evidence of estimates are described.
4. Data privacy handling and retention terms are approved separately; do not upload real client data to GitHub.
5. Quote is a **proposal only** until owner approves price and lawful collection/fulfillment channel; no payment request or external message is authorized by this document.

## Delivery acceptance gate
- Record exact source revision and executed command, input checksum (not raw client data), test outcome, and analyst/reviewer identity in private client records.
- Show monetary figures with units, reporting basis, exclusions, caveats, and source provenance.
- Verify a representative sample manually against primary documents; reconcile all anomalies with client before final delivery.
- Cycle B signs off scientific assumptions; cycle E confirms lawful payment only if approved; client explicitly accepts delivered report.
- Do not mark LIVE, PAYMENT or FULFILLED based on this document or an HTTP status alone.

## Unapproved commercial terms
Price: **PENDING OWNER APPROVAL**. Turnaround: **PENDING CAPACITY CONFIRMATION**. Public listing: **BLOCKED**. External outreach: **BLOCKED**.
