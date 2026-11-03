# Farm Enterprise Economics Toolkit — market evidence and gap register

**Evidence edition:** 2026-11-03 (UTC reference date).  
**Product:** `farm_enterprise_economics`, draft 1.3.  
**Evidence class:** first-party public product/extension descriptions only.  
**Commercial / scientific verdict:** NOT INDEPENDENTLY VERIFIED; NOT CLEARED FOR SALE.

## Defined market and fair comparison boundaries

This toolkit is a **standalone, offline contribution-margin and deterministic sensitivity calculator** for 1–100 agricultural enterprises using user-supplied quantities, prices, variable costs, fixed-cost allocations and a selling-fee percentage. It calculates whole-farm totals and nine correlated quantity/price stress scenarios. It does **not** manage accounting ledgers, depreciation, capital expenditure, finance, tax, crop insurance, weather, seasonality, market prices or actual inventory.

Its relevant comparison market is *enterprise budgeting and whole-farm planning decision support*, NOT the entire farm management platform market. The six products/resources below form a documented international **comparison sample**, not a ranked “top five” or proof that every provider serves every country. A full competitive ranking requires defined market size, adoption data, access and independent methodology.

## Six current first-party reference comparators

| Alternative and provider | Specifically documented capabilities | Relevant comparison with this toolkit | Evidence |
| --- | --- | --- | --- |
| **Farm Projection Tool / FAST, University of Illinois farmdoc (United States)** | Per-acre crop budgets, whole-farm budget, break-evens, projected financial statements, return sensitivities; crop-insurance and hedging effects. | Direct overlap in farm budgeting and sensitivity; FAST documents broader projected statements and insurance/hedging, which this toolkit omits. | [Official Farm Projection Tool](https://farmdoc.illinois.edu/fast-tools/farm-projection-tool), updated 2026-09-03 per provider. |
| **Ag Decision Maker Decision Tools, Iowa State University Extension (United States)** | Spreadsheet tools for crop and livestock enterprise costs/returns, and detailed whole-farm cash-flow budgeting. | Direct overlap in enterprise budgeting; these tools supply commodity-specific budgeting formats whereas this toolkit requires customers to supply their own unit economics. | [Official decision-tools catalogue](https://www.extension.iastate.edu/AGDm/decisiontools.html). |
| **FINPACK, University of Minnesota Center for Farm Financial Management (United States)** | Income/expense analysis by enterprise, financial projections including annual/monthly cash-flow plans, and long-range planning. | Broad farm financial planning alternative; this toolkit is materially narrower and has no cash-flow or balance-sheet module. | [Official FINPACK non-lenders page](https://finpack.umn.edu/finpack-for-non-lenders/); [official planning overview](https://finpack.umn.edu/news/which-finpack-projection-and-planning-tool-is-right-for-you/). |
| **Farmbrite farm accounting and break-even tools (commercial)** | Farm revenue/expense transactions, financial reports, and break-even cost analysis for individual plantings, animals, locations and equipment. | Competitor for some break-even decisions, but also a broader operational accounting platform; this toolkit does not post transactions or maintain an account ledger. | [Official Farmbrite break-even guide](https://help.farmbrite.com/help/cost-analysis-tracking); [official accounting overview](https://help.farmbrite.com/help/accounting-overview). |
| **AgExpert Analyst desktop accounting (Canada)** | Desktop farm accounting, commodity-specific settings, enterprise expense/income tracking, and more than 35 reports according to provider. | Relevant offline/desktop alternative with substantially more accounting scope; offline alone is **not** a unique advantage for this toolkit. | [Official AgExpert Analyst product page](https://agexpert.ca/en/products/agexpert-analyst). |
| **Teagasc Profit Monitor (Ireland)** | Enterprise-level and whole-farm financial breakdowns, targets, progress over time, and comparisons with other farm data. Full access requires Teagasc client status. | Broader historical monitoring and benchmarking; this toolkit computes only prospective user-supplied deterministic scenarios and has no peer-farm database. | [Official Teagasc Profit Monitor](https://teagasc.ie/rural-economy/farm-management/financial-analysis/farm-profit-analysis/). |

The words “documented” and “broader” above mean a stated feature on the linked first-party page. **Absence from a provider page does not demonstrate that its product lacks any unlisted feature.** No claim of superiority, ranking, accuracy or pricing advantage follows from this table.

## Applied agricultural-economics reference

Penn State Extension's [Budgeting for Agricultural Decision Making](https://extension.psu.edu/budgeting-for-agricultural-decision-making) describes enterprise budgeting as a framework for costs, receipts and profits, and explains break-even price/yield and whole-farm budgets. It also emphasizes cost categories and seasonal cash flow that the current lightweight model excludes. Our model is **contribution profit before depreciation, financing and tax**; it must not be presented as an all-inclusive production cost or a full farm profit-and-loss account.

## Reproducible comparison protocol — NOT YET EXECUTED

1. **Comparable task:** Define identical crop/livestock units, yield/sold volume, sale price, selling charges, variable costs, fixed-cost allocations and accounting boundary in every accessible alternative.
2. **Reference baseline:** Collect current official help and input-schema evidence. Save access dates and authorized local copies only when licensing permits. Do not reproduce third-party copyrighted templates inside our package.
3. **Consistent arithmetic:** For this toolkit, preserve source Decimal precision, round at the displayed result boundary, and independently recalculate revenue, variable expense, fees and contribution.
4. **Cross-product output:** Compare only like-for-like quantities. An accounting product with tax or depreciation must have those components excluded or separately reported before comparing against pre-tax contribution profit.
5. **Sensitivity:** Record whether an alternative documents an equivalent *correlated whole-farm* 3 × 3 volume/price matrix; if not determined, mark **NOT ESTABLISHED**, never “missing”.
6. **Usability/access:** Measure time to a valid first budget, errors, keyboard accessibility and report readability with permission and identical tasks; do not invent measurements or sample sizes.
7. **Independent review:** An authorized agricultural economist and independent QA assessor must sign the exact build hash, date, dataset, protocol, deviations and results.
8. **Statistics:** Pre-register repeat counts, confidence intervals and an uncertainty budget before any claim of performance or superiority. No “global best” claim until evidence supports it.

## Current evidence matrix and open quality findings

| Quality requirement | Present evidence | Outstanding proof |
| --- | --- | --- |
| Relevant market identified | Defined above; first-party reference links | External validation of market segmentation |
| At least five current alternatives | Six named, linked and described | Reconfirm source dates/availability at release |
| Feature provenance | Provider first-party documentation | Version-specific independently archived evidence |
| Independent reproducible benchmark | Written protocol only | Authorized execution, input/output captures, tool versions |
| Quantified international advantage | **NONE** | Fair task metrics and uncertainty; may establish no advantage |
| Agricultural-economics validity | Clear contribution equations, model boundaries; Penn State reference | Expert critique, model verification across real enterprise types |
| Originality/non-derivativeness | Independent standard-library Python source | Independent rights and code-provenance review |
| Support and distribution reliability | No documented post-sale support service | Actual support channel, delivery/restore evidence and service-level plan |
| Final commercial release | **BLOCKED** | Independent QC1000, owner legal/rights approval, signed receiving-cycle evidence |

This document **closes no mandatory release gate by self-attestation**. The live VPS assessment reported `RETURN_TO_PRODUCTION_CLASSIFICATION` and missing quality documentation. Recompute those results only after a new, independently supported evaluation of an exact artifact, never by editing a score field.

## Source review control

- Reviewed public first-party pages: 2026-11-03.
- Authored content is an original synthesis; no external tool code or worksheets are bundled.
- Feature/market claims are narrowly sourced. Features not explicitly documented remain **unknown**.
- No paid login, private customer data, financial transfer, artificial order, or live purchase was performed.
