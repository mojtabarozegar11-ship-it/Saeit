# Mojtaba.bot.ai — one operational identity, multi-income source-only commercial gate
**Date:** 2026-11-14 / 23 Aban 1405
**Scope:** isolated follow-up to draft Saeit PR #2268 (`work/revenue-dual-offer-readiness-20261114`).
**New review branch:** `audit/mojtaba-income-portfolio-offline-20261114`.
**Canonical bot identity:** `mojtaba.bot.ai` — NO additional autonomous bot, scheduler, VPS service, payment gateway or trading execution.
**Environments:** all changes source-only and local Python. No live server mutation, owner expense, outreach, invoice, transfer, merge or release.

## Existing evidence and choice of first offer
- **Existing edited inquiry draft (EN):** `mojplaywin.com/services/` — website checkout diagnosis and bounded repair. Service pricing shown in previous source is USD 29–49 and 79–149 as *exploratory non-binding ranges*, not current binding approved prices. The CTA is a request for a manual quote; it is NOT a checkout.
- **Existing edited inquiry draft (FA):** `zomorodmelal.ir/services/` — farm break-even and sensitivity analysis; **no owner-approved price**, so the price remains unknown rather than invented. CTA uses existing `/contact/`.
- **Live website status:** unverified. Attempts to read the two real URLs and `mojtaba.bot.ai` through the public browsing tool failed; there is no independent HTTP/visual/sales acceptance in this cycle.
- **Source-only evidence:** PR #2268 service templates, intake code, tests and protocol. PR #2267 contains other inquiry paths, and PR #2263 is a separate Draft commerce acceptance track. Their existence does not prove any live sales.
- **Prioritize first actual customer opportunity:** one well-defined checkout issue or one farm enterprise break-even study, with genuine opt-in request and individually approved scope. Both are only ready for source review, not production or accepting money.

## Eleven possible income models (one bot, two existing site families)
| Code | Revenue model | Proposed sales surface | Repository status | External readiness |
|---|---|---|---|---|
| website_checkout_repair | diagnosis, limited technical repair | MojPlayWin | existing Draft inquiry | Unknown / not saleable |
| farm_break_even | crop/farm enterprise economics | Zomorod Melal | existing Draft inquiry | Unknown; price not approved |
| research_consulting | applied research/feasibility | Zomorod Melal | conceptual candidate | Unverified |
| digital_books | books and manuals | Zomorod Melal | conceptual candidate | Unverified |
| english_digital_guides | English guides | MojPlayWin | conceptual candidate | Unverified |
| training | educational advisory packages | Zomorod Melal | conceptual candidate | Unverified |
| licensed_templates | licensed reusable reports/templates | MojPlayWin | conceptual candidate | Unverified |
| subscriptions | recurring digital access | MojPlayWin | conceptual candidate | Unverified |
| sponsorship | qualified partner placements | MojPlayWin | conceptual candidate | Unverified |
| b2b_supply | real supplier B2B goods | Zomorod Melal | conceptual candidate | Unverified |
| game_content | rights-cleared downloadable gameplay content | MojPlayWin | conceptual candidate | Unverified |

No row above represents a completed SKU audit, legal approval, deployed route, merchant onboarding, settled revenue, or operating bot. No additional domain or agent was created.

## Eight non-bypassable release gates per model
1. `source_and_rights`: actual licensed/owned product, allowed publication and terms
2. `verified_deliverable`: final file/service definition, accepted QC, provenance, minimum user value
3. `owner_price_approval`: fixed price, scope, taxes, refund obligations, customer disclosure
4. `lawful_payment_and_tax`: independently confirmed legal settlement channel and tax compliance
5. `refund_terms`: usable refund/cancellation policy and payment dispute route
6. `customer_support_route`: genuine reachable support/consent and data retention controls
7. `real_live_route`: authorized production HTTP/render/contact journey with source attribution
8. `receipt_to_delivery_test`: unique settled receipt → licensed/private deliverable → customer access, without duplicate claims

**Status in the source portfolio:** 0 of 8 independently verified on every row, because this package cannot authorize or attest external evidence. 11/11 remain blocked for commercial activation. This does not say the businesses have zero progress in reality; their external verification is simply absent from this source review.

## Concrete first-customer service acceptance
**Website checkout diagnosis, EN:** customer selects one reproducible problem without secrets; operator records environment/browser and sanitized reproduction, severity, root cause, screenshots with PII removed, bounded list of accepted changes, before/after behavior, rollback and final service report. Repair is priced and delivered only after owner accepts written scope and lawful payment; a live merchant transaction must be independently verified before a paid service is marked paid.

**Farm break-even service, FA:** customer supplies crop/area, production window, seed/input/labor/water/energy costs, actual expected and stress yield, selling price assumptions, units and source/date; operator verifies completeness and computes break-even and sensitivity using the existing scientific calculator. Deliverable: defensible assumptions, formula/units, threshold, sensitivity table, limitations and owner QC. No actual market prices, profit guarantee or yield are assumed from the synthetic example. A separate approved quote and data confidentiality agreement precede paid engagement.

## Results actually executed in this cycle
- Local Python **3.13.5**, no internet/Django/production database.
- `21/21` new model/funnel/CLI tests passed.
- `15/15` new strict intake file I/O security tests passed.
- `12/12` direct integration tests of the existing two-service CLI passed.
- **48/48** new local tests passed in the latest consolidated run, with six changed/created Python source and test files re-read from GitHub and matched to local `git hash-object` SHA.
- Two CLI commands ran: `--catalogue` returned **11** candidates, **2** repository-draft inquiry sources and **null** collected revenue; `--synthetic-funnel` returned illustrative ratios for a 100→10→5→4→2→1 fake cohort, not real conversion.
- Reviewed existing two site CTA code and the isolated source-only workflow; **no new GitHub Actions workflow was triggered** by writing to the new branch. The workflow definition was updated for eventual review, but no CI success is inferred.
- No real user data, support message, sale, receipt, payment, payout, broker order, email, database migration, PR merge or deployment occurred.

## Local command and acceptance evidence
```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py' -q
# Ran 48 tests — OK (isolated local fixture of the six changed/created Python files)
python3 scripts/mojtaba_revenue_portfolio.py --catalogue
python3 scripts/mojtaba_revenue_portfolio.py --synthetic-funnel docs/revenue-p0/synthetic-funnel-onebot-20261114.json
```
Existing repository-wide/Django source tests were **not** executed in the local minimal fixture. Source contract check is a separate read-only GitHub inspection and never equals an independently running production environment.

## Privacy, financial constraints, and why the new code matters
- The actual service qualifier still accepts **only** its original seven allowlisted fields and two existing services, and returns anonymous non-binding triage.
- The helper rejects file symlinks, FIFOs, overly large intake, invalid UTF-8, duplicate keys including an overridden `consent_to_contact`, and nonfinite JSON numbers. It will not clobber a pre-existing output file; a new result file uses 0600 mode.
- The portfolio tool accepts **only synthetic same-cohort aggregates**; a fake/unknown zero denominator is returned as null, and real collected cash remains null.
- Customer identifiers, financial wallet addresses, raw inquiry messages, account IDs, remote transaction numbers and email contents are neither imported nor written to the public repo by these tools.
- Future real orders need lawful collection and independent receipts; do not alter any product's live availability or collect payment automatically.
- Model status: `commercial_release=blocked_unverified`; manual owner approval remains binding for each charge, communication, contract and production change.

## Progress denominators (do not confuse with total business completion)
| Evidence class | Baseline at this cycle | Final source state | Correct meaning |
|---|---:|---:|---|
| Source-audited candidate revenue models | 0 in new module | 11/11 catalogued | 100% of *new catalogue* only |
| Existing source inquiry drafts recognized | 0 | 2/2 | Both pre-existing draft CTAs, **not live verified** |
| Release gates independently verified here | 0 | 0/88 | 0% evidence gates in this isolated audit; not proof no prior progress |
| New tested local executable tests | 0 | 48/48 PASS | 100% of newly created offline test suite |
| Site HTTP/checkout proof verified | UNKNOWN | UNKNOWN | Public GET attempts failed; no live claim |
| Collected real revenue | UNKNOWN | UNKNOWN | No trustworthy payment, balance or settlement data |
| Deployments/merges/payment/expenses | 0 | 0 | None undertaken |
| Enterprise-wide real readiness | UNKNOWN | UNKNOWN | No mathematically defensible percentage |

## Next income-focused work
1. Obtain allowed GET-only verification of two service routes, website versions, human-readable CTA and inbox/form delivery without contacting customers or spending; preserve approved design.
2. Confirm that the owner-approved lawfully accessible payment/receipt process can support *one* small fixed-scope service sale; never claim a gateway exists from a URL.
3. Produce final, privacy-safe two-service QC report templates and implement receipt-to-private-delivery reconciliation once real authorized integrations are available.
4. Resolve upstream Draft PR review and CI only after full source branch and legal finance gate; no auto-merge, no release.

#مجتبی_روزگار
