# D34-02 | Digital checkout and fulfillment fault recovery — delivery specification v1
Status: INTERNAL / NOT FOR SALE / OWNER PRICE APPROVAL REQUIRED
Owner: Cycle D; coordinate checkout ownership with Cycle A and payment governance with Cycle E.

## Scope and authorization
Diagnose consented storefront checkout failures without placing real orders or handling payment secrets. Require asset ownership and written authorization defining test domains, endpoints, permitted accounts and hours before any active test. Read-only public UI checks are separate from authenticated or production testing.

## Intake
- customer business name and publicly accessible storefront URL; contact method supplied only through approved secure intake.
- exact failing step (product -> cart -> guest email -> order review -> payment -> callback -> receipt -> authorized download).
- timestamp with timezone, device, browser, reproducible steps, expected versus observed behavior.
- sanitized screenshots/logs; redact email, session cookies, authorization headers, payment references, customer addresses and tokens.
- environment classification: development/staging/production; allowed testing methods and responsible approver.

## Fault taxonomy and prioritization
P0: unauthorized delivery, wrong recipient, double charge, exposed credentials or payment confirmation bypass.
P1: legitimate paid order cannot obtain a receipt or file; guest email validation blocks all customers; persistent checkout 5xx.
P2: intermittent callback, broken recovery link, mobile form overflow, inaccessible validation errors.
P3: cosmetic defects without measurable conversion impact.
Classify separately: front-end validation, backend persistence, gateway callback/webhook, inventory/entitlement, mail/receipt, download authorization, logging/observability.

## Acceptance matrix
A. Invalid guest email rejected; valid email accepted without forced wallet connection.
B. Order ID idempotent: repeated callback cannot create duplicate entitlement or double fulfillment.
C. Payment must be independently verified server-side for amount, currency, recipient, network, confirmation status and unique transaction reference; a mock callback NEVER proves payment.
D. Download token bound to purchased entitlement and expiration; cross-account retrieval denied.
E. Failed payment cannot grant download; successful authorized payment receives receipt and repeatable recovery.
F. Mobile 390px and desktop 1366px: form focus, RTL/LTR where relevant, keyboard navigation, reduced-motion, visible errors, console clean.
G. No P0/P1 defects at acceptance; regressions linked to exact code SHA and environment.

## Delivery package
- signed scope/authorization record, environment map and redacted reproducibility evidence.
- issue register with severity, root cause, minimal diff and regression test references.
- exact revision SHA, test logs, staging before/after evidence and rollback plan.
- owner sign-off for deployment; production smoke only after separate authorization.
- fulfillment receipt and post-release measurement plan: legitimate lead -> offer -> authorized order -> confirmed payment -> entitled delivery -> repeat order.

## Commercial approval record (unapproved)
Suggested fixed-price model: diagnostic fee plus separately approved repair fee, AMOUNTS NOT SET. Price approved: NONE. Payment processing: NOT VERIFIED. Authorized clients: NONE VERIFIED. Deployment: NOT AUTHORIZED.
Never request a card number, password, private key or full transaction token through a public form.
