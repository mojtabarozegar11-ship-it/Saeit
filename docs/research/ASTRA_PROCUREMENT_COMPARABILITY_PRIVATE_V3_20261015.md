# Astra V2 — Procurement Quote Comparability Gate V3 — implementation and expert acceptance

**Date:** 2026-10-15  
**Branch:** feature/astra-v2-0048-integration-canary-20261015  
**Scope:** reviewed private factory, never the live cPanel store, sales, payments or original factory SQLite schema.

## What changed in the actual product

V2 had already added exact Decimal calculation for indivisible bags/wholesale packs and prevented claiming an arithmetic price gap as realized savings.

V3 fixes a different, material buyer problem. A simple cost comparison can name a
cheaper supplier even if the offered fertilizer formulation/grade differs from
the buyer's requested product, delivery terms differ, the quotation has expired
or the document's basic provenance cannot be reconciled.

The new optional strict mode requires a buyer-declared comparison contract:

- required_product_spec_id: one stable grade/specification reference
- delivery_basis: delivered_to_farm or buyer_collection
- as_of_date: explicit buyer comparison date, not inferred current clock time

Each seller may supply metadata with product_spec_id, delivery_basis,
quoted_on, valid_until and a lowercase SHA-256 for the quotation document.
For strict evaluation, unmatched, expired, future-issued or missing metadata
makes that supplier INELIGIBLE for the arithmetic winner/runner-up ranking.
Syntactically invalid IDs, calendar dates or digests are rejected outright.

**No external document or signature is opened or authenticated in this engine.**
Matching self-asserted specification identifiers does not prove chemical grade
equivalence, supplier identity or legal validity. This is deliberately reported
as "buyer_supplied_metadata_not_independently_authenticated". The legacy
format remains supported but now explicitly warns that equivalence was not
checked. The exact comparable quote dates, supplier source labels and
capacity/lead-time bounds must still be independently validated.

## Mathematical and reproducibility evidence

Input quality tests cover:

1. Mismatched cheap fertilizer grade excluded, regardless of superficially lower price.
2. Buyer-collection and delivered-to-farm offers cannot masquerade as equal terms.
3. Expired/future-dated offers excluded; same-day valid issuance accepted.
4. Missing quote metadata excluded under strict mode.
5. Malformed calendar dates, unknown delivery terms, missing or malformed
   SHA-256 and bad specification identifiers fail closed.
6. Fully backward-compatible legacy quote arithmetic with an explicit warning.
7. Mixed strict quote and 20 kg whole-pack price is still correctly billed.
8. Zero eligible quotes produce no winner and no invented savings.
9. User-reported SHA-256 never grants a verified quote or market demand.
10. Print-friendly HTML discloses that legacy equivalence was not assessed or
    strict matching was operator-declared, not independently authenticated.

[Integrated CI 38691401741](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38691401741):
**224 independent private source tests and 19 Django database tests passed.**

[Private VPS candidate run 38691401764](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38691401764):
**43 independent procurement tests** passed both in runner and on VPS.

[Actual running private source upgrade 38691576397](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38691576397):
**43 procurement tests and 31 private factory pipeline tests** passed;
the factory identified a revised specialist source, produced an immutable new
package and marked it PRIVATE_QA_PASSED while preserving exactly three
existing builder families. The original factory remained on 0048; live
commerce and payment workflows were left unchanged.

[Post-deployment independent release gate 38691691284](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38691691284):
all three source/ZIP/QA manifest/SQLite integrity checks passed after
updating the running private specialist. Commercially qualified count: **zero**.

## Scientifically and commercially unresolved criteria

- Exact seller-provided product composition, fertilizer nutrient analysis,
  batch grade, certificate of analysis, registration, delivery terms and
  shipping/duty/freight conditions on **genuine** quotations.
- Operator-supplied SHA-256 must be reconciled to an authorized original
  document, with independent issuer and date confirmation. Hash metadata
  alone is not independently verified provenance.
- Independent farm-manager or agricultural-economics expert must sign off
  on true product substitution, chemical and agronomic comparability,
  tax treatment, rounding, lead time, uncertainty and regulatory boundaries.
- Real target users must consent to anonymized workflow testing; compare
  effort and errors against a free spreadsheet; evidence of genuine buyer
  demand and willingness to pay must be documented.
- Accessibility, rights, support, refund, accurate pricing and settlement
  require a **separate** commercial approval gate, not an optimistic
  100/100 score and not an artificial 90% discount.

## Sample offline validation protocol (no invented interviews)

Take a consented, anonymized file containing at least two independently
reconciled quote documents for the same commodity grade and delivery terms.
Compute exact gross order units, indivisible packs, tax, freight and discount
by hand, compare with JSON output, and record any data mismatch or
ambiguous field interpretation. Repeat an expired quote, mismatched grade,
unavailable quantity and missing provenance to confirm no false winner.
Record actual user time on the original process versus this method and
cost of support/error correction. **Until these observations exist, this
remains a research-only technical prototype.**

## Commercial status

- Active *private* procurement builder: source revision V3.
- Distinct specialist source families: **3**, unchanged.
- Genuine quotes independently verified: **not yet established**.
- Independent demand validated: **not established**.
- Commercial products newly approved: **0**.
- Retail deployment, checkout and payments: **untouched**.
