# Moj Prop — secure no-JavaScript sales-intake recovery (16 Nov 2026)

Canonical source branch is rebased onto live GitHub main. This note does **not** authorize deployment or assert a real sale.

## Operational defect addressed
On the public static Moj Prop page, JavaScript can be unavailable under CSP, browser extensions or a network issue. The original JS-only form had no equivalent no-JS path: valid potential buyers could not save a real CRM inquiry. This fix exposes an explicit native HTML link and uses the **same** protected `MojPropRequest` database writer.

## Security and trust boundaries
1. `GET /moj-prop-intake/?format=html` returns no-cache, frame-denied, no-referrer, no-script page with genuine Django CSRF cookie and server-generated UUIDv4 idempotency key.
2. POST must be same-origin and `application/x-www-form-urlencoded`; the production single-valued form validator, allowed route/horizon checks, honeypot, email, consent, 16KiB limit and rate limiter are reused. Only actual buyer name/email/scope/consent enter CRM; no quote or payment is created.
3. A lost-response POST with the same unchanged form uses the existing DB-unique HMAC-bound request ID. Exact repeat returns HTTP 200 and the original signed private token; changed buyer/scope returns 409 with **no receipt disclosure**.
4. The HTML service selector excludes `digital` because digital products require an approved SKU and real checkout. The existing JSON API retains `digital` with its strict independent catalog restriction. Never falsely display an invoicable digital product in the HTML form.
5. `GET /moj-prop-status/?format=html` displays a CSRF-protected HTML POST-only status form; secret token never enters a URL. POST returns only public review status for an HMAC-verifiable receipt, not buyer identity or payment.
6. Existing `GET /moj-prop-intake/`, `POST /moj-prop-intake/` JSON, `GET /moj-prop-status/?receipt_token=...` (legacy compatibility) and `POST /moj-prop-status/` JSON remain available.
7. The static JavaScript form is disabled until JS handlers are initialized; the dedicated native link is accessible with JS off. Its method is POST (never an unhandled GET with buyer fields).

## Acceptance criteria / evidence
- Exact-head Django ORM/CSRF and standalone frontend contract tests must pass before merge.
- Verify the current Passenger backend actually serves this source; a static page HTTP 200 alone does **not** prove CRM persistence.
- No merge/deploy on an automatic main-push path until full DB+media backup, isolated restore, tested rollback and tenant boundaries have independent evidence. Issue #2392 and C94 capacity probe recorded `combined_capacity_preflight_passed=false`; cPanel quota API failed, therefore production backend activation remains **NO GO**.
- Manual, consented external buyer entry with confirmed CRM row and receipt is required to assert commercial intake. A paid invoice additionally requires legal terms, owner-bound verified TRON merchant and fulfillment.
- No customer contact, service price/claim, financial commitment, DNS change, token transfer, production rollout or file deletion occurs in this PR.

## Canonical transition
Old PR #2373 contained this feature against a stale backend. The new source port keeps every distinct user-facing no-JS feature, uses the current stricter validation+UUID4 replay API, and avoids copying obsolete views that would weaken typed JSON, allowed products and receipt support.
