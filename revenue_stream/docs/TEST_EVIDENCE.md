# Test evidence and limits

## Executed

- 16 Python core tests: private password hash, order idempotency, immutable amount, concurrent payment-request claim, unpaid download denial, amount mismatch, reference validation, concurrent callback replay, reference reuse denial, uncertain request fail-closed, artifact binding/download quota, support response, refund accounting/access revocation, rate limits, event deduplication, no invented profit, order authentication.
- 13 Django integration tests in an isolated temporary database: pending-config gate, CSRF, full order → mocked gateway → server verification → valid ZIP, callback does not grant outsider access, failed provider prevents delivery, nonce/terms, relogin/logout, escaped ticket content, owner boundary, no-store/noindex, historical artifact delivery, asset allowlist, no secrets in downloadable package.
- 12 Node calculation tests: documented example, unit conversion, incompatible units, invalid yield, invalid margin/fee, negative/nonfinite input, loss reporting, invalid portion count, backup whitelist, CSV formula neutralization, input bounds, JSON round trip.
- Python compile and JavaScript syntax checks passed.
- ZIP build is deterministic and contains six product files. Initial SHA-256: `e649c9303d4182962250865ab229f5ca7e93795bb51411811e48203b0c112e6c`; size 11,772 bytes. Recompute before release; the configuration binds approval to the exact artifact hash.
- Sales CSS is approximately 3.7 KB and uses no external font, analytics SDK, framework or image request. Product is offline and has no network API calls. These are payload facts, not measured Core Web Vitals.

## Not executed / blocking claims

- No real Zarinpal request/payment/refund, merchant sandbox transaction or live sale occurred. Tests use a clearly isolated fake provider; they are not payment certification.
- Local browser test was attempted but Playwright's Chromium executable is not installed. Desktop/mobile browser rendering, real-device ZIP opening, accessibility audit, actual download interaction and Core Web Vitals are **not certified**. Responsive CSS and labels are implemented but do not substitute for browser QA.
- No production deployment, security-secret rotation, customer outreach or money transfer occurred.
- No customer willingness-to-pay validation, use telemetry or proven conversion exists.
- Existing site regression tests and payment provider integration must run against the approved staging deployment before production.

## Release QA checklist

1. View sales/checkout/order/support at 390px and desktop widths; no horizontal scrolling, clipped prices or unreadable controls. Test keyboard and screen-reader form labels.
2. Test actual browsers in Persian RTL and English tool mode; add/remove/save/load, import malformed/valid JSON, CSV injection strings, print/PDF and quota errors.
3. Use real sandbox credentials in a separated harness, then one owner-approved live purchase. Check amount in IRR, cancellation, timeout, replay, session loss, refund request and artifact SHA.
4. Confirm production service worker/cache excludes `/costkit/`; ensure no secrets/customer data in logs, public static files, source archives or third-party requests.
5. Verify public canonical/schema and noindex/private routes; add only the live sales URL to the sitemap.
6. Owner verifies consumer terms, seller identity, support mailbox, fulfilment and backup/retention procedure.
