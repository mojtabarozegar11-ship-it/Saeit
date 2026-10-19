# Astra 2.0 — first product opportunity/competition dossier (2026-10-15)

Status: **Primary-source methodology and competitor existence checked; willingness to pay, customer interviews, pricing and commercial demand NOT VERIFIED.** This dossier is not production authorization. All URLs below were inspected as public HTML pages; this file does not imply live API/source retrieval on VPS.

## Hypothesis

Agricultural operators evaluating an orchard investment, change in production method or replacement decision need to compare risk-adjusted cash-flow options using their own data, assumptions and source traceability. A distinct, still-*unvalidated* product proposition is **Orchard Investment Decision Audit**, a transparent review tool that independently recomputes discounted cash-flow differences, deterministic price/yield/cost stress scenarios, input-unit checks and an assumption/evidence ledger. It is NOT an agronomic advice generator or a guarantee of return.

### Evidence: verified educational need for the **method**, not buying intent

1. Penn State, `Top-Working Decision Workbook`, https://agsci.psu.edu/research/centers-facilities/extension/frec/resources/self-help/top-working-decision-workbook . University already provides an existing 12-sheet orchard investment decision workbook comparing do-nothing, grafting and replanting using annual cashflows, NPV, IRR and cumulative cashflows. **Competition exists and is substantive.** No source-backed claim of unmet demand or paid uptake.
2. University of Florida IFAS, `Getting Started with Enterprise Budgets and Sensitivity Analysis`, https://ask.ifas.ufl.edu/publication/FE1175 . Establishes farmer-specific cost/revenue assumptions, opportunity costs, price/yield and input sensitivity; highlights that representative budgets can mislead if unadjusted. Supports the problem domain and methodological requirements, NOT willingness to pay.
3. University of Wisconsin Extension, `Partial Budgeting`, https://farms.extension.wisc.edu/articles/partial-budgeting/ . Four quadrants of changing revenue/cost; a useful distinct baseline for scenario assumptions. NOT independent proof of buyer purchases.
4. Government of Alberta, `Crop Returns enterprise analysis tool`, https://www.alberta.ca/crop-returns-enterprise-analysis-tool . Free Excel reference tool with breakeven and sensitivity analysis, customizable costs, scenarios and opportunity margins. Its copyright/terms expressly forbid redistributing and reverse engineering. **Do NOT copy its spreadsheet, formulas expressed as code, text or proprietary materials.** Mathematical facts of NPV/enterprise finance can be independently implemented from first principles.
5. Penn State Extension, `Budgeting for Agricultural Decision Making`, https://extension.psu.edu/budgeting-for-agricultural-decision-making . Describes enterprise budgets, variable versus fixed costs, break-even, sensitivity and need for local adjustments.

### Serious competition / qualification finding

- The base product class (farm cost calculator, orchard NPV spreadsheet, basic sensitivity tool) already has free reputable substitutes. It is not justified to claim the first sale, differentiation or commercial pricing from these references.
- A genuinely differentiated auditable decision review MUST be demonstrated independently: reproducible first-principles computation, comparison of at least 2 options, transparent assumptions ledger, explicit user-input provenance gaps, sensitivity inversion/break-even, currency/unit checks, no invented farm data, reproducible plain-JSON/CSV reporting, meaningful install/use instructions.
- Treat product as a **private reference MVP** until real buyer trials and evidence of value versus those free alternatives emerge. Existing factory two recipes are retained unchanged; this is a genuinely separate tool/module if actually built.
- Market qualification fields: customer_interviews=0; verified_willingness_to_pay=FALSE; verified_public_competitor_existence=TRUE; legally_sellable=UNKNOWN; price=NULL; commercial_approval=FALSE. No numerical market score asserted.
- Operating limits: uses user-provided observations only; no calls to LLMs, paid data sources, external APIs or real VPS worker; no automatic storefront publication.

## Technical product brief — reference MVP acceptance

**User story**: A farm manager provides 2–5 alternatives over 1–30 annual periods, same units/currency, and sees discounted cash-flow rankings under a stated rate, plus 3 deterministic stress scenarios (base, downside, upside) and annual traceable intermediate calculations. If inputs conflict or are missing, it fails closed or warns, never manufactures positive profit numbers.

**Data contract**: explicit nonnegative revenues (before stresses), variable costs, fixed costs, capital costs and terminal receipts per year. Year 0 corresponds to immediately committed cost/investment; years 1..N cash flows accrue at period ends. Cost/benefit multipliers are deterministic perturbations, not probability distributions. Discount rate must specify nominal-vs-real convention (report warns no automatic inflation/tax/financing assumptions). All amounts are user-entered. One ledger entry per major assumption with source label and confidence; unverified source entries flagged.

**Required outputs**: full per-year cashflow trace, baseline and scenario NPVs, delta NPV versus do-nothing/reference, break-even revenue factor where defined, deterministic ordering and strong missing-evidence warnings. Both input and output can be hashed. Never emit a claim of verified farm economics or a validated retail product.

**Non-negotiable tests**: known exact NPV arithmetic; no initial cost double-counting; 0% rate; variable/fixed stress separation; missing variable and units; boundary/malicious inputs; option ranking and reversal in downside; negative NPV honest; no fabricated input prices; failed evidence status blocks commercial flag; deterministic repeated output; no website/store/db modification.

**External proof before public sale**: at least 3 independent grower/advisor walkthroughs, independent financial-method review and correction of defects, documented advantages over cited free tools, a license and user support channel, UI accessible to non-programmers, and explicit release approval. No such proof is claimed today.

This dossier is source material for design only. Research references describe established methods, not commercial purchase intent.
