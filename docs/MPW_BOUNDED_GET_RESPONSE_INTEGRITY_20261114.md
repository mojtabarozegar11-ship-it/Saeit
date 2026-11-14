# MojPlayWin response-integrity gate for cutover — 2026-11-14

## Confirmed source defect
The cutover GET probe previously read only 250,000 bytes from each page. A response larger than the cap could be silently accepted from its valid prefix. Python HTTPMessage.get() can also return only one of multiple conflicting Content-Security-Policy headers. A misleading checkout looked usable under these conditions.

## Applied source correction
- Bounded reader now asks for 250,001 bytes and categorically rejects any body over 250,000, plus conflicting/malformed Content-Length and duplicated security headers.
- The GET verifier uses the same checked bytes for title, CTA and rendered form acceptance; it never marks truncated HTML as complete.
- Security header reader rejects invalid controls, missing directives, duplicate headers, cache weaknesses, and inconsistent declared response length.
- All previous mandatory buyer email, CSRF, CSP, no-store and order ownership checks retained.
- Public static fallback and current production CSP are NOT changed. This branch does not access cPanel, POST an order, create invoices, send emails or pay TRX.

## Operational dependency
Even with 428 successful offline tests, production release is NOT authorized. The existing cPanel Passenger UAPI inventory reports mappings but does not independently prove which source/template serves the checkout. Current public GET evidence still shows one static /store fallback and six checkout responses without the exact CSP target. A separate owner-approved deployment, migration, settlement, delivery and rollback plan is required.

Single canonical robot: mojtaba.bot.ai.