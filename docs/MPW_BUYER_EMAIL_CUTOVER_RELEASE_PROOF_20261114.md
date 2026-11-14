# MojPlayWin: buyer-email cutover source acceptance — no payment or production release

## Root cause and actual correction
Public buyer route probe in scripts/mpw_dynamic_store_cutover_20261108.py still invoked has_guarded_guest_invoice_form(), a legacy email-FREE-only scanner. That contradicted buyer-email server ownership and made a correct checkout look unhealthy. This branch preserves the historical scanner for regression only and replaces the *active* nine-route probe with services/mpw_checkout_release_assurance.py. The new gate delegates form checks to the actual Django rendered HTML contract, now including the hidden/disabled controls from PR #2276. It also enforces exact script-src none, form-action self, frame-ancestors none, base-uri self/none, Cache-Control no-store and Content-Type text/html. Legacy source preflight correction from PR #2278 is retained.

## Implementation boundary
Only synthetic GET responses with 64-character CSRF, required email input and working submit are accepted. Paid status and delivery are never inferred. New tests assert the source/public route probe rejects wrong SKU, missing or disabled email, hidden controls, malformed CSRF, invalid POST, unsafe CSP, missing cache and mismatched content type. Existing 47 rollback and source tests remain mandatory.

## Still blocked
Production static /store fallback and six checkout CSP mismatches were observed on 2026-11-14 via public GET; code is NOT deployed. Actual Passenger root, effective template, database migration, legal collection, buyer email server binding and private paid download require independent evidence and owner approval. No permission to merge, deploy, remove the email requirement, create an invoice or transmit TRX is granted by this branch. The old OWNER_BUYER_EMAIL_REQUIRED public publish guard intentionally remains.

Only canonical automation identity: mojtaba.bot.ai.
