# D — Checkout recovery service: client-ready internal delivery package (v1)
Date: 2026-11-14. Status: INTERNAL DRAFT; no offer sent, no pricing approved, no live changes.

## Scope and eligibility
Service repairs a **documented** failure in an existing merchant's browse → cart → checkout → payment confirmation → fulfillment path. The client must prove control of the storefront and provide written authorization defining staging access and allowed changes. Do not request passwords, tokens, card numbers, or customer PII in the intake. No guarantee of increased sales or payment approval.

## Client request form (private, manually reviewed)
- Business legal name, authorized representative, business contact channel, website/domain, country and currency.
- Platform and version, hosting constraints, checkout/payment provider **name only**.
- Product/service sold, fulfillment method, applicable taxes and refund policy (links).
- Reproduction steps: device, browser/version, locale, URL path without secrets, expected/actual behavior, timestamp/timezone, redacted screenshot.
- Failure class: add-to-cart / address / shipping / price/tax / payment redirect / confirmation / receipt / fulfillment / mobile RTL / accessibility.
- Whether production is affected; whether a staging copy and sanitized sample order are available.
- Consent to diagnostic read-only inspection; separately authorize any code changes and deployment.
- Do not upload live card data, credentials, session cookies, access tokens or unredacted customer records.

## Deliverables
1. Reproduction report with environment, impact, steps, redacted evidence and issue ID.
2. Root-cause assessment separating storefront, payment provider and fulfillment dependencies.
3. Versioned patch on an isolated branch; no merge or deployment without case-specific permission.
4. Regression evidence for failing and passing paths, mobile/RTL and keyboard navigation.
5. Release checklist and rollback instructions, plus unresolved risks and client acceptance record.

## Acceptance checklist
- Baseline failure reproduced in authorized test environment and linked to a specific version.
- Correct totals, currency, tax and shipping shown consistently before payment.
- No double-submit, double-charge, or duplicate fulfillment on retries; idempotency checked where applicable.
- Guest/customer flows, validation errors, back/refresh, timeout and failed payment handled safely.
- Payment success only after trusted server-side confirmation; no client-only success flags.
- No collection or storage of cardholder data by the service; provider compliance reviewed by client.
- Receipt and delivery are matched to one authorized, confirmed order.
- Keyboard focus, readable error messages, mobile widths and RTL checked without visual regression.
- Client approves staging evidence; production release requires separate authorization and rollback plan.
- Independent evidence required for LIVE, PAYMENT and FULFILLED; HTTP 200 is insufficient.

## Commercial boundaries
Suggested pricing: **not set** until scope, jurisdiction, expected effort and owner approval. No public listing, unsolicited outreach, contract, payment link, test charge, or order is authorized. Scope exclusions: payment gateway underwriting, legal/tax advice, provider credential changes, production deployment and unapproved destructive database operations.

## Delivery record template
Client reference: [redacted ID]
Issue: [ID]; baseline SHA: [SHA]; patch SHA: [SHA]; test command/result: [evidence]
SOURCE: [ ] TESTED: [ ] CI: [ ] LIVE: [ ] PAYMENT: [ ] FULFILLED: [ ]
Acceptance sign-off: [authorized client, date]; owner deployment authorization: [separate record]
Payment receipt and delivery confirmation: [independent evidence, or UNKNOWN]
Outstanding risk and rollback: [details]

## Coordination
Cycle D owns the service package and authorized storefront patch. Cycle A owns MojPlayWin checkout changes; cycle E owns lawful payment integration and the sole organizational bot mojtaba.bot.ai. No second bot or parallel scheduler is created. Personal social account Dr.mojtaba.rozegar is strictly excluded.
