# MOJPROP-STARTER30 — private contract, consent and refund approval gates

**Review draft only — not an offer, invoice, published terms, legal opinion, or authorization to accept TRX.** Owner's sole product here: **10-session simulated trading/risk journal + deterministic scorecard + individual educational risk feedback**, exactly **30 native TRX = 30,000,000 SUN**. Never describe as a funded account, prop challenge, brokerage service, profit guarantee, trading signal subscription, or investment-management mandate. **No customer-specific data or wallet address appears in this source document.**

## Mandatory fields to complete before a lawful customer contract exists

| Evidence field | Source/proof required | Fail-closed behavior |
|---|---|---|
| Legal seller identity | Verifiable legal person, registration/authority, jurisdiction and contact | No seller authorization, no invoice |
| Seller's ability to contract in native TRX | Relevant jurisdiction and professional tax/consumer review | No payable invoice |
| Controlled receiving wallet | Owner custody and exact TRON-mainnet binding, independently verified | No payment instructions |
| Buyer identity and capacity | Private, documented verification with lawful handling and a stable lead ID | No personalized contract |
| Specific buyer request | Timestamped inquiry for this exact SKU | No unsolicited offer |
| Purpose-specific consent | Buyer explicitly opted in to quotation for this SKU/channel, not only marketing | No outreach |
| Contract version & digest | Immutable actual PDF/text version, digest, exact deliverables | No signature inference |
| Buyer signature evidence | Authenticity review and timestamp bound to this order/contract | No authorization |
| Seller signature evidence | Authorized representative, same order/contract, timestamp | No authorization |
| Invoice reference | Server-created canonical \`MOJPROP30-...\`; atomic DB uniqueness | No reuse or duplicate invoice |
| Quote units | Exactly native TRX, **30,000,000 SUN**; no USD/IRR imitation | Refuse currency substitution |
| Draft issue/expiration | Trusted server timestamps, issue < expiry ≤ issue + 86,400 seconds | Expired = unusable |
| Refund/withdrawal rights | Applicable mandatory law, jurisdiction, start-of-service rule and refund mechanics signed | No final offer |
| Customer data policy | Retention, deletion, purpose, breach response and data subject rights | No real PII in Git |
| Delivery acceptance | Secure private educational report, recipient identity, date/proof of access | No automatic delivered status |
| Settlement | Independent mainnet solidified finality, native transfer, correct receiver/payer/amount | Unverified claim ≠ payment |
| Anti-replay | Atomic unique (network,txID) claim and order attribution | Never double-credit or resend paid order |
| Operational readiness | Real DB+app+media backup, isolated restore, tenant isolation, rollback and CI/security | NO DEPLOY |
| Disputes & support | Verified merchant support address, response expectations and jurisdiction | No customer contact |
| Marketing truthfulness | No guarantee, trading/funded account or field-performance claims | No public sales language |

These twenty fields are **approval requirements**, not twenty passed checks. Actual seller jurisdiction and consumer-rights exceptions must be decided by qualified reviewers; do not invent a blanket "non-refundable digital content" clause. The **24-hour limit is the validity of a private invoice draft**, not an arbitrary consumer withdrawal window or delivery SLA.

## Draft customer-facing commercial clauses — **NOT APPROVED FOR USE**

1. **Service identity.** The buyer requests one educational simulated-risk review package: ten-session simulation journal, scoring and feedback. No real-funded capital, brokerage account, investment return, or live trades are included.
2. **Price and unit.** One order is quoted at exactly 30 native TRX (30,000,000 SUN) on TRON Mainnet. This is not a conversion of 30 USD/IRR and there is no auto-renewal. Any applicable taxation, network fee allocation and statutory price disclosure require a lawful seller contract and explicit approval before charge.
3. **Acceptance.** No contract is formed merely by an unverified form submission, SHA digest, software-generated draft or checkbox. The authenticated buyer's request, signed terms, legal seller and authentic signatures must be reconciled against the immutable order.
4. **Expiry.** A non-payable private draft may expire in at most 24 hours. Expiration does not waive legal cancellation or consumer rights. Expired drafts must not accept funds or trigger delivery.
5. **Delivery.** The service consists of a private educational evaluation of the agreed simulation inputs. Delivery channel, turnaround and satisfaction/acceptance process need mutual consent in the final lawful contract; no fabricated delivery acknowledgment.
6. **Refunds and disputes.** The lawful seller must disclose applicable cancellation/withdrawal rights, consequences of service starting, handling of materially nonconforming digital services, complaint channel, resolution deadline and refund process under applicable law. Never silently deduct network fees, make irreversible on-chain refunds, or deny statutory rights without authority. Every refund requiring network fees or transfer needs separately specified owner consent.
7. **Limitations.** Educational simulations do not constitute investment advice, a prop trading challenge or evidence of profit; scores cannot predict actual market performance.
8. **Privacy.** Identity and signature material remain in access-controlled systems. Git receives only anonymous test fixtures and source code. A mere SHA-256 hash does not prove the existence or authenticity of the underlying document.

## Technical separation of duties

- \`research/starter30_b/private_invoice_preview.py\`: first-stage source-only, non-payable preview; its boolean flags are not real verification.
- \`research/starter30_b/verified_draft_packet.py\`: **additional** HMAC-authenticated reviewer attestation and strict binding to source-owned order, lead, request, product, price, consent/contract/identity document digests and issue/expiry. The verifier key and identifiers must originate from server-controlled independently reviewed records. **Any caller-provided key is NOT trust establishment.**
- No key, credential, customer name, email, signature content, actual wallet, SMTP credentials, txID or invoice link is stored in code, test fixtures or this document.
- Neither module writes the DB, issues payment instructions, creates a live contract, verifies a real identity, marks paid, grants entitlement or sends email.
- The database migration in PR #2544 remains **source-only** and draft-only. Runtime atomic uniqueness of order and evidence attestation, real restore, lawful settlement and merchant/wallet authority are not proved by this Python function or local unit tests.

**STOP decision:** Until the real seller, buyer, consent, signed legally reviewed contract, verified wallet, isolated restore, exact-HEAD CI/security and independently finalised ledger are proved, there shall be **no payable invoice, live-site release, email, transfer, payment capture, or asserted revenue**. No costs or commitments were authorized.