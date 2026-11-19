# MOJ-PROP-01 canonical consent bridge — operator runbook (2026-11-16)

**Scope:** Real funded prop challenge Plan 1, not educational Starter30. 30 native TRX (30,000,000 SUN), simulated two-stage evaluation for 28 days after confirmed payment, at least 50 independently verified closed positions across the challenge and 6 verified trading days per phase. Conditional real $100 account only after passing and independently funded broker capital; 70/30 eligible profit share, conditional 14 levels. Social: one original Instagram plus one original Facebook post per challenge **only where legal and platform policies permit**, with proper ad disclosure, and no use/scraping of owner's Dr.mojtaba.rozegar or associated Facebook accounts.

## Source of truth and integration decision

- Canonical model: `prop_firm.lead_models.PropInterest` and migration `0008_prospect_contact_intake.py` in Saeit parent PR #2310; the former child PR #2552 merged into that parent. This is *contact interest*, not paid enrollment.
- Main's generic `/moj-prop-intake/` CRM notes tag is **not** proof of Plan 1 informed consent, verified age, country, KYC or contract signature. Never auto-import from free-form notes or email alone.
- The B-owned `plan1_canonical_interest_bridge.py` is pure/read-only. It checks a canonical record snapshot and independently signed consent-lineage evidence for the **exact** record PK, request ref, Plan 1 SKU, contract version, consent version, one-to-one contact purpose, original inquiry digest, and evidence digest. No PII is emitted, no ORM write, invoice, order, email, entitlement or TRON transfer.
- `match_private_review_to_canonical_interest` further joins that verified lineage to B's existing authenticated nonpayable contract review by exact request, inquiry digest, SKU, version, native amount, chain and blocked payment flags. This is not a durable database relation.

## Safe migration of legacy consented leads — no writes authorized in this cycle

1. Read-only export an **allowlisted** set of legacy CRM records, with no public logs or GitHub PII. Verify precise capture timestamp, specific Plan 1 purpose, affirmative consent wording/version, source host, withdrawal status and source email verification. An email or `MOJ-PROP-01` note tag alone is insufficient.
2. Resolve duplicate identity records and pre-existing opt-outs in an access-controlled private registry. Never overwrite existing `PropInterest` identity, never resurrect withdrawn consent; quarantine conflicts for human review. Do not assume the existing unique-email constraint can represent multiple independent consents across offers.
3. Obtain independent legal confirmation of the controller, privacy notice, lawful processing basis, jurisdiction, retention/deletion and rights to contact. No transfer to another purpose by default.
4. For genuinely consenting leads, issue a new server-owned opaque request ref; store exact consent text/version, time, request, authenticated provenance and withdrawal state in a protected immutable/audited consent service. The separate server-held HMAC key must never be supplied by a browser, PR, log or public static page.
5. A protected adapter must read the *current* canonical row, compare it with the independent consent registry under a transaction/lock, and check latest opt-out again immediately before any permitted one-to-one communication. The current B pure module **does not implement this DB transaction** and cannot authorize outreach.
6. Import only after documented dry-run totals, PII-minimized diff, backup, restore rehearsal, migration ownership and explicit deployment authorization. Do not run `0008` on production merely because a GitHub CI passed.
7. On withdrawal, block further contact and revoke/expire outstanding private review material. Preserve lawful audit metadata without continuing marketing. No batch promotion via `QuerySet.update()`.
8. Never treat a legacy CRM row, opt-in, signed HMAC or contract PDF hash as proof of KYC, customer signature, legal seller eligibility, $100 capital reserve or payable invoice.
9. After verified eligibility, prepare the legally reviewed, accessible customer contract and fair refund/withdrawal terms. Independently verify both signatures and their exact version. Disclose simulation, real-capital contingency, price, 28-day clock, trading counts, social/ad rules and territorial exclusions before payment.
10. Invoice and settlement remain owned by Cycle C: native TRX mainnet only, unique order, exact amount, custody proof, finality, replay resistance and refund/rollback. Never wire the merged educational 30 TRX SKU or offline wallet validator directly to this funded challenge.
11. `PropChallengeEnrollment` must be created only by the independently verified invoice→solidified payment→versioned executed contract chain; phase 2 must depend on phase 1 completion. Never activate a real broker account before legal and reserve proof.
12. **No release until independent gate review**: merchant legal authority, buyer age/country/KYC, independently attested consent, executed contract/refunds, funding/broker authorization, wallet custody, finality, production backup/restore, and customer support.

## Current limitation and nonclaims

The canonical `PropInterest` schema currently has email, plan code, consent version, language, status and timestamps. It does **not** store the original Plan 1 request ref, immutable consent evidence digest, exact reviewed terms acceptance or signed reviewer provenance. Therefore the bridge cannot be connected to a real live buyer from that table alone. It requires the protected consent registry and secure adapter; this cycle does not create a second CRM table or fake consent. A synthetic test attestation proves only that the code rejects mismatches; it does not attest a real buyer. A green CI does not prove revenue or deployment readiness.

**HOLD:** no merge, production migration, live payment link, invoice, email, contact, KYC upload, account creation, public social post, real trade or new expense from this run.
