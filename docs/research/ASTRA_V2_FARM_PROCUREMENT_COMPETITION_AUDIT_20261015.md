# Market/competition audit — Farm Input Procurement Quote Audit

**Date:** 2026-10-15. **Status:** verified *existence of real decision need and free competing tools* from public pages; **zero independently documented buyer intent to purchase this particular software**. No claim of sellability, market share, fair price, profitable demand or verified user interviews.

## First-party background and competitor evidence

1. **Michigan State University Extension — Input Purchasing Plan Template (Excel)**, Jonathan LaPorte, Oct 29, 2022: https://msu-prod.dotcms.cloud/resources/input-purchasing-plan-template-excel
   - Describes decisions about input purchasing plans, storage, high-volume purchases, supply risk and buying timing.
   - Already offers a free structured planning spreadsheet.
2. **Michigan State University Extension — Crop Budget Estimator (Detailed)**, updated Aug 20, 2024: https://msu-prod.dotcmscloud.com/resources/crop-budget-estimator-tool-detailed
   - Provides product purchasing lists, input quantities and customizable crop budget.
   - Existing procurement planning functionality is NOT an unsolved universal problem.
3. **University of Maryland Extension — 2026 Field Crop Budgets**, updated Feb 2, 2026: https://extension.umd.edu/resource/field-crop-budgets
   - Official extension input benchmark planning emphasizes that farm costs differ by operation and must use operator-specific figures.
   - The prototype therefore intentionally accepts only operator-supplied quotes. Listed public benchmark prices are NOT inserted into the example as purported actual supplier offers.
4. **University of Missouri Extension — Free online tools help farmers manage costs**, May 20, 2026: https://extension.missouri.edu/news/free-online-tools-help-farmers-manage-costs-forage-challenges
   - Free Feedstuff Finder helps with sourcing and comparing delivered feedstuff costs; relevant incumbent for some potential buyer tasks.
5. **Tools for Procurement — Quote, Landed Cost & TCO Tools**: https://toolsforprocurement.com/
   - Offers free browser-local worksheet for quote/landed cost/lead times.
   - This means a basic quote comparison is a commodity capability, not an established exclusive value proposition.

## What the prototype actually adds, with honest boundaries

Implemented offline reference tool `product_prototypes/farm_procurement_audit`:
- Gross-to-net usable quantity/waste normalization and minimum-order checks.
- Capacity/lead time failures shown with explicit machine-readable reasons.
- Exact Decimal arithmetic for discount, fixed fees, declared tax convention and delivered cost; bounded adverse price/freight/waste stress.
- Deterministic local JSON input, auditable explanation fields, standalone HTML print report with escaped supplier text.
- No provider calls, rate forecasts, actual quotes or commodity price defaults; refuses to authorize purchase or public sale.

**Differentiation is an unproven hypothesis.** Similar features and free alternatives exist. No independent claim that this tool outperforms any incumbent; tests only establish defined mathematical behavior.

## Commercial discovery blockers (separate from code QA)

| Area | Evidence | Decision |
| --- | --- | --- |
| Input purchasing is a real farm-management workflow | MSU Extension documentation | Confirmed broad topic, not buyer intent |
| Farm cost inputs need customization | Maryland Extension | Confirmed methodological requirement |
| Free relevant alternatives exist | MSU, MU and other free procurement tools | Confirmed competitive pressure |
| Buyer willingness to pay for this prototype | No actual buyer interviews or sales | **NOT VERIFIED** |
| Per-user measurable benefit over free incumbents | No randomized user testing, time or error benchmarks | **NOT VERIFIED** |
| Legal/support/license and accessibility independent sign-off | Not completed | **BLOCKED** |
| Commercial quality 90+/100 | No qualified independent review | **NOT SCORED** |
| Public price, discount or sales claims | No credible market value established | **DO NOT SET** |

## Minimum independent validation package before release

- Three real eligible operators/procurement advisers try their own **private data** on both prototype and selected free alternatives.
- Validate totals manually with independent invoices; test actual fee/tax jurisdiction, delivery constraint, waste assumption and quantity conversions.
- Record time-to-correct-decision, net cost calculation errors and improvements versus reference spreadsheets, with informed permission to use anonymized results.
- Determine whether independent users would purchase or regularly use this tool, not merely agree it looks good.
- Complete license/rights, accessible interaction design, security, documentation and operator support plan, with genuine source evidence attached to release decision.

**Never treat this research dossier itself as qualification to sell.** Its purpose is to block false claims and focus design on independently testable value.
