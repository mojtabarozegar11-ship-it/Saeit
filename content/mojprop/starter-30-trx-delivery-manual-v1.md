# ⚠️ ARCHIVED NONCANONICAL DESIGN — NOT FOR BUYER OFFER OR FULFILMENT

This 2-page independent prop-rule review was an exploratory alternative concept, **not** the unique sellable 30 TRX Starter30. DO NOT quote, invoice, issue a refund policy for, deploy, or promise this document under `MOJPROP-STARTER30` or `starter-30-trx`. It is preserved solely as historical research; its descriptions and price are **superseded** and must not be used in public copy or operator proposals.

**Authoritative single SKU:** `MOJPROP-STARTER30` = **10-session simulated trading journal + deterministic risk scorecard + individual written educational feedback**, as specified by `docs/mojprop/starter30-first-product-release.md`, and represented by `templates/moj-prop-v4/starter-30-trx/index.html`. Payments, legal contract and on-chain settlement remain blocked until separately evidenced. Any two-page rules review must have a distinct independently approved product identifier and terms, without reuse of this 30 TRX price.

---

# Moj Prop Starter | one-time prop readiness and risk review

**Package code:** `starter-30-trx`  
**Public reference amount:** 30 TRX (not an invoice, not a token purchase)  
**Service type:** independent educational research and rules interpretation  
**Deliverable:** individualized two-page PDF or accessible text equivalent plus one clarification reply  
**Timing:** target within 3 business days **after** manual scope acceptance and verified lawful payment; no automatic entitlement or renewal  
**Lead route:** `blueprint` via `/moj-prop-intake/` with package code in bounded notes  
**Operating identity:** `mojtaba.bot.ai` (single agent); authorized staff may review/deliver manually

> This service **does not** sell a funded trading account or a prop-firm challenge; allocate investment capital; place trades; manage accounts; recommend personalized investments; provide broker execution; promise income, payouts or challenge success; or ask for passwords, broker keys, wallet seed phrases or signing permissions.

## 1. Binding customer offer and compliance gate

The public catalog may advertise this service as an **inquiry**, not a payment endpoint. A request is a lead only if `POST /moj-prop-intake/` creates HTTP 201, the server issues a canonical `MOJPROP-YYYYMMDD-XXXXXXXX` request ID and a private receipt token, and the customer grants consent. A local browser draft, URL visit, quote, accepted offer and paid order are different states.

Before inviting any remittance, an authorized merchant operator must verify, and document privately:

1. Seller's correct legal identity, commercial authority, tax/address/support requirements, eligibility of customer jurisdiction, and digital educational service lawfulness.
2. Customer-specific agreement: service scope, one-time 30 TRX proposed amount, network, official merchant receiver binding, receipt terms, customer cancellation/refund rights, dispute contact, service delivery cutoff and timing.
3. Valid mainnet TRON recipient **and actual wallet custody**, stable receiver-to-merchant mapping, refund capability, transaction finality and replay/double-credit protection. The `tron-mainnet` registry is a prerequisite; valid Base58Check by itself is not evidence of owner custody.
4. A supported authorized invoice type and currency with unambiguous rounding; the current `MojPropOffer` contract only accepts `USD` or `IRR`. **Do not mislabel 30 TRX as 30 USD or 30 IRR.** A manual written offer must not claim payable status, or accept TRX, until lawful quote/settlement infrastructure is approved.
5. Real isolated database/media backup, tested restore and rolling release against tenant-safe staging; production rollback has to account for migrations, not only source files.
6. A real customer contact route established with verified permission and an actual SMTP/CRM system or authorized manual channel; never send mail to guessed addresses.
7. Issue a buyer-held request/offer reference without disclosing receipt tokens in logs, URLs, analytics, social links or third-party embeds.

No payment instructions are published by this manual and no customer funds are solicited from repository prose.

## 2. Exact scope and acceptance contract

**Inputs to request:** official public URL or redacted text of the target prop program's rules; account *nominal* size for mathematical examples; daily/overall drawdown definitions; daily reset/time-zone; instrument and position constraints; objective the buyer wishes to evaluate. The customer may instead specify a generic educational example. **No trading credentials, personal financial assets, ID scans or seed phrases.** If rules are inaccessible or ambiguous, report the uncertainty and ask for clarification; never invent conditions.

**Included outputs:**
- Page 1: rule extraction, applicability/evidence table, three significant risk/failure flags, and clear limits/unknowns.
- Page 2: scenario-based risk worksheet calculating the difference between remaining daily and total loss capacity; an activity checklist and an action-oriented readiness verdict (`rules understood`, `clarification required`, or `cannot assess from supplied rules`).
- One post-delivery clarification on interpreting this written document, not open-ended consulting or a trading signal.

**Not included:** account access, trading challenge fee, deposit, profit distribution, eligibility certification, portfolio management, secret/proprietary challenge details, forecasts, ongoing reports, customized live trades, follow-up subscriptions, legal/tax advice.

**Delivery acceptance:** one private PDF/text file containing date/version, source URL or supplied document identifier, three risk flags, a worked scenario with stated assumptions, at least one limit/unknown, private request reference, reviewer and revision. The customer can make one clarification request about omissions in the described scope. Any work outside it requires fresh agreement, not an auto-charge.

**Refunds:** handling must be defined in the final lawful written agreement according to mandatory consumer rights and actual stage of performance. Do not invent a universal “no refund” policy, waive statutory rights or assume crypto payments are irrecoverable without a dispute mechanism.

## 3. Two-page delivery production template (actual operator work product)

### Page 1 — Prop rules & operational risks

```text
MOJ PROP STARTER — INDEPENDENT EDUCATIONAL RISK READINESS REVIEW
PRIVATE REPORT | REQUEST: [canonical CRM ID] | VERSION: 1
ISSUED (UTC): [ISO timestamp] | REVIEWER: [authorized operator]
TARGET RULE SOURCE: [official URL or buyer-provided redacted rule sheet]
SOURCE LAST VERIFIED: [UTC; or "buyer supplied, not independently verified"]
SERVICE: one-time starter-30-trx; no financial recommendation

1. SCOPE: [question in one sentence]
2. SOURCE / EVIDENCE TABLE:
  - [rule name]: [exact rule / bound] — source [URL, version, section]
  - [rule name]: [exact rule / bound] — source [URL, version, section]
  - [rule name]: [exact rule / bound] — source [URL, version, section]
3. MATERIAL RISK FLAGS (exactly 3):
  R1 [risk] → [trigger and potential challenge disqualification consequence]
  R2 [risk] → [trigger and consequence]
  R3 [risk] → [trigger and consequence]
4. AMBIGUITIES:
  - [which facts cannot be established from supplied evidence]
5. NOT INCLUDED: trading instruction, funded account, profit guarantee
```

### Page 2 — Worked calculation and readiness action

```text
6. ASSUMPTIONS — LABELLED (DO NOT REPRESENT A FIRM'S REAL RULES):
  Nominal demo account: 10,000 account units
  Illustrative daily loss limit: 5% = 500 units
  Illustrative overall loss limit: 10% = 1,000 units
  Illustrative hypothetical closed + floating daily P&L: -240 units
  Illustrative hypothetical closed + floating total P&L: -650 units
  Daily loss headroom = 500 - 240 = 260 units
  Overall loss headroom = 1,000 - 650 = 350 units
  Conservative illustrative remaining loss capacity = min(260, 350) = 260
  All quantities depend on whether the firm's rules use balance/equity,
  original capital/high-water mark, daily reset and floating loss.
  This simple arithmetic DOES NOT authorize any trade or imply compliance.

7. CHECKLIST (operator to mark and explain):
  [ ] Confirm loss-limit definitions against actual terms.
  [ ] Confirm clock/timezone/daily reset and whether floating P&L counts.
  [ ] Confirm leverage, concentration, stop-out and news/event prohibitions.
  [ ] Confirm maximum number of accounts and rule changes at evaluation.
  [ ] Record unknowns; do not certify success without adequate evidence.

8. READINESS CLASSIFICATION:
  [ ] RULES UNDERSTOOD FOR EDUCATIONAL PLANNING
  [ ] CLARIFICATION REQUIRED
  [ ] INSUFFICIENT EVIDENCE TO ASSESS
  Reasons: [2-4 sentences; explicit unknowns]

9. NEXT STEPS:
  - [one evidence-collection step]
  - [one risk-monitoring spreadsheet/checklist step]
  - [one question to ask provider before committing money]

10. CUSTOMER RIGHTS: [agreed scope, contact method and refund reference]
One clarification response included; no additional charge without new consent.
```

**Important:** if the real firm has trailing drawdown, daily equity reset, commissions, swap, slippage or dynamic high-water mark, recompute mathematically with the verified formula. Never use the 5%/10% example as a default rule for an actual buyer.

## 4. Operator verification and handoff

- Review the scope, official terms and screenshot provenance. If the source cannot be verified, flag the rule table as buyer-provided and incomplete.
- Validate calculations independently (e.g., spreadsheet vs second arithmetic review); include scenario units and sign conventions.
- Avoid naming or impersonating a real broker/prop firm as a partner without a written partnership.
- Generate PDF from the final filled report **after** buyer acceptance and lawful payment confirmation. If document access fails, furnish accessible text equivalent.
- Hash the final deliverable (SHA-256), retain offer version / authorized handoff / customer acknowledgement privately and in correct consent-scoped records. Do not publish customer details in the public repository or GitHub PR.
- A customer-held receipt cannot be fabricated from a 200 response, form URL or browser local draft. The CRM's status is not a payment ledger. No new “paid” or “delivered” status without independently verified evidence.
- Central execution/publishing identity remains `mojtaba.bot.ai` and cannot be bypassed by creating parallel trading bots.

## 5. Launch stop/go rubric

| Gate | Minimum evidence | If absent |
| --- | --- | --- |
| Public reachability | Real HTTPS page, request, CSRF, 201 persisted lead, private receipt | No live launch |
| Contract | Merchant jurisdiction, agreed scope/refund/support and customer identity | No invoice or collection |
| TRON | Controlled receiver, merchant match, exact amount, tx finality, replay safety | No wallet address, no transfer |
| Delivery | Original template, reviewer, secure private handoff, checksum | No paid entitlement |
| Infrastructure | Backup of actual database + tested restore, migration rollback or compatibility | No risky backend deployment |
| Operation | Monitor consented queue, accept/reject quote, document evidence | No claims of sales |

**This document provides a real report-production procedure and delivery text. It contains no payable invoice or customer-specific report until buyer scope is supplied.**
