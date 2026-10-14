# Orchard Investment Decision Audit — private reference MVP

**Status**: independently coded reference prototype; not a saleable or certified product, not shipped to store, no customer/payment integrations. Not a product recommendation or profitability forecast.

## Why this is different from the two factory ZIP calculators

The first two `product_recipes` are fixed crop budgeting calculators; this new prototype compares **multiple long-term capital investment alternatives**, computes present-value financial differences over 1–30 annual periods, runs three **operator-chosen** deterministic stress scenarios and produces an annual reproducibility trace plus input source-gap audit. It does NOT claim to outperform any free competing workbook; see `docs/research/ASTRA_V2_ORCHARD_INVESTMENT_MVP_DOSSIER_20261015.md`.

## Quick start (Python 3.8+, no third-party libraries)

From the repository root, run:

```bash
python3 product_prototypes/orchard_decision_audit/decision_audit.py \
  --input product_prototypes/orchard_decision_audit/example_synthetic.json \
  --out /tmp/orchard-decision-audit-private-report.json
python3 -m unittest discover -s tests -p 'test_astra_orchard_decision_audit.py' -v
```

Choose an output path that does not already exist. The report is local and private by default (0600). The tool intentionally refuses to overwrite any file.

**CAUTION**: `example_synthetic.json` contains *entirely invented numbers for reproducibility tests*, not real yield, price, operating-cost or climate data. They must never be reused in product adverts, customer decisions or opportunity scoring. No sensitive farm information should be committed to GitHub.

## Input / calculation conventions

- Currency: one three-letter code; annual amounts are consistently per hectare, per acre or whole farm. All options must use the **same** unit, period, currency and real-versus-nominal convention.
- Year 0 is immediate. Every later annual cash flow is assumed at year-end.
- For each year, provide nonnegative revenue, variable cost, fixed cost, capital cost and terminal value.
- Cash flow = revenue × price factor × yield factor − variable cost × variable cost factor − fixed cost − capital cost + terminal value.
- NPV = sum(year-t net cash flow / (1 + annual real/nominal discount rate)^t), t=0..N.
- Discount rate field is a **percent**, not a fraction. An input of `10` means 10%.
- Break-even total-revenue multiplier = discounted net costs (at the scenario variable-cost factor) / discounted **base-model** gross revenue, where baseline revenue > 0. It does not prove that multiplier is obtainable.
- The tool reports absolute NPV of options and incremental NPV against the named comparison alternative; compare like-for-like.
- Explicit user-supplied scenarios are base (1× each variable), downside and upside. Downside and upside are hypothetical **stress calculations**, not estimated probabilities, crop forecasts or automated market data.
- JSON decimals are encoded as **strings**, preserving exact decimal arithmetic without binary floating-point noise. At presentation the output rounds cashflows and NPV to 2 decimal places, but intermediate calculations retain precision.
- `assumptions` ledger tracks which option/field is supported by a user-named record or estimate. Labeling an assumption `operator_record` is **not** proof that its source is independently validated; all commercial approval and market demand flags remain false.
- Taxes, debt financing, seasonal liquidity, inflation projections, exchange rate conversion, opportunity costs not explicitly entered, terminal fees and climatic/agronomic model dynamics are NOT computed. Do not double-count taxes/depreciation already embedded in supplied rows; have a qualified financial reviewer check the model.
- The leading option is an **arithmetic ranking under the supplied assumptions** and must not be presented as a recommended purchase or investment.

## What is already tested

- Known closed-form discounted cash flow arithmetic and alternative ordering; no double counting year-0 investment.
- 0% rate boundary; individual stressed revenue and cost values; honest decision reversal under bad conditions.
- Revenue-multiplier breakeven; missing/zero-revenue handling; negative NPV; missing source warnings.
- Strict validation for years, money units, rates, NaN/infinity, booleans, disallowed negative input, duplicate options and assumptions.
- Reproducible input hash and private local output, refusal to overwrite any input/output path.
- Output NEVER authorizes live product manufacture, store publication or payment.

## What this product is still missing (hard release blockers)

1. Real customer interviews, willingness-to-pay and independent discovery evidence (unknown).
2. UX suitable for nontechnical buyers (currently CLI + JSON, **not** consumer-ready).
3. Independent financial/economic method audit and tests on real sanitized farm histories.
4. Rights/license/support terms, help documentation, accessible localized UI, support process and security threat modeling.
5. Integration of versioned ProductBrief, the verified evidence engine, pluggable manufacturer and live safe orchestrator via Astra migration 0049 **only after** verified single-writer cutover.
6. Existing owner-governed publication and verified checkout/reconciliation. No web live catalog change.

## Safety/provenance

All reference educational material is cited only in the research dossier. No competing tools' source code, worksheets or proprietary text have been used or reproduced. The program implements conventional arithmetic independently. You may inspect every output with `input_sha256` and year-by-year cashflow traces. Do not assert it has passed commercial QA without the independent review steps.
