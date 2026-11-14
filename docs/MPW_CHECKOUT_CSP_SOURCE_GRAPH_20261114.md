# MojPlayWin actual revenue blocker: checkout source graph + Django CSP source fix

## Verified problem
Public GET-only inspection previously observed 3 product detail pages with CTA, 1 `/store/` static fallback and 6 buyer checkout GET pages without the required `script-src` CSP. This is not proof of payment or a live Django source. The reviewed `main` source has `core/commerce_views.store_home -> core.mojplaywin_views.store -> core/templates/mojplaywin/store.html` but its `config/urls.py` contains NO explicit `/store/product/<id>/checkout/`, `/commerce/book/<id>/`, `/commerce/trx-easy/start/<id>/` routes. The reviewed GitHub root does not contain the full `mpw_commerce` package nor migration `core/migrations/0049_mpw_guest_email_recovery.py`, even while the guest adapter depends on these resources. This is a VERSIONED SOURCE integration gap, not proof that such files do not exist in another cPanel application.

## Implemented direct source-level header correction
- New `core/mpw_checkout_security_middleware.MojPlayWinCheckoutSecurityMiddleware` wired in `config/settings.py` immediately after Django SecurityMiddleware.
- Only the EXACT GET or HEAD URLs `/store/product/<positive id>/checkout/` and `/commerce/book/<positive id>/` on `mojplaywin.com` or `www.mojplaywin.com` with successful **200 text/html** responses receive fixed `Content-Security-Policy` including `script-src 'none'`, `form-action 'self'`, `object-src 'none'`, `frame-ancestors 'none'`, and a bounded same-origin policy.
- Privacy headers `private, no-store, max-age=0`, `Pragma: no-cache`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` and `Vary: Host` are added, preserving existing other Vary dimensions.
- Does NOT alter cookies, body, API JSON, company-domain requests, redirects, errors, POST invoices, the `/store/` catalogue, download routes or TRX finality. It **cannot** apply to Apache static fallback or independent Passenger applications that do not run this Django settings module.

## Implemented explicit versioned-source release NO-GO
- Read-only `scripts/mpw_checkout_source_coverage_20261114.py` enumerates 11 fixed reviewed source prerequisites and 4 explicit `config/urls.py` path declarations via AST, plus `INSTALLED_APPS` and new middleware registration. Restricts file reads to fixed regular bounded paths, refuses symlinks/oversized inputs and emits only fixed relative path identifiers, not secrets.
- Missing `mpw_commerce` modules, templates, buyer migration, or named checkout route declarations classify the **GitHub tree** as incomplete. This is not a statement about the actual cPanel filesystem or URL resolution because production may be a distinct codebase. The gate never auto-authorizes a release and reports revenue `null` (unknown).
- 55 isolated middleware tests + 50 independent source graph tests execute in a no-credentials GitHub Actions job. Tests do not contact the live site or create orders.

## Production path still gated
Before commercial release: independently attest the effective cPanel Passenger root, WSGI and template, recover required real buyer-email app and migrations from their authoritative versioned source, resolve source URL/checkout provenance, plan backup & rollback, and obtain separate owner approval for the controlled deployment. Then GET-verify all 10 live buyer routes, independently settle actual payment and deliver the entitled download. No bypass of email validation, CSRF, signed order ownership, RPC finality, anti-replay or paid fulfillment.

**Sole organizational bot:** `mojtaba.bot.ai`. No second bot, costs, transfers, invoices, emails, merges or live deployment in this PR.