# Independent, narrow owner-only cPanel source-provenance bridge

This branch is based directly on `main` and touches **only** the existing read-only GitHub Actions → VPS → cPanel bridge. It is an alternative to merging the unrelated 115-commit checkout audit PR merely to obtain source-provenance metadata.

## Why this is needed
The currently deployed `main` does not advertise `mpw_source_provenance` in the direct bridge, and its cPanel SSH hostname uses a stale direct IP instead of the known pinned DNS host. Meanwhile sanitized UAPI inventory identified a real `mojplaywin.com` Passenger registration root which did not match the old cutover's two expected candidate path fingerprints. The effective Django template is still unknown.

## Scope
- Adds **one** allowlisted `mpw_source_provenance` operation to the already existing main-only `workflow_dispatch` choices; no new broad SSH commands or elevated capabilities.
- Corrects only the known cPanel connection hostname, retaining the pinned expected ed25519 key fingerprint, `StrictHostKeyChecking yes`, no agent forwarding and a one-hourly owner-controlled run model.
- Streams one exact immutable Git blob (pin `f93556203417399e6c099f182cddea4432260532`) to `python3 -B -` on the existing cPanel account; no source copied to server, no imports of Django, no SQL, payments, email or mutations.
- Exposes redacted category labels and 16-character file digest prefixes, never raw paths, customer information or credentials.
- The PR's own GitHub Actions uses only `ubuntu-latest` with `contents:read`; it does NOT access or authenticate to the owner's cPanel. The remote operation cannot run from a PR; requires manual workflow dispatch **from main after a separately authorized merge**.

Do **not** merge/deploy, restart, modify DNS or order systems, or spend money without explicit user approval. The branch improves an inspection capability, not storefront commercial readiness or settlement.
## 2026-11-14 — Buyer email *source evidence* integrity correction

A prior auditor used a loose substring/attribute check: a detached `<select
id="preferred-email">`, a `<textarea name="customer_email">`, a visible
label or a GET-form input could wrongly count as a ready buyer email field.
This was **not** proof of a live, user-operable checkout. The corrected
`StaticCheckoutControlInspector` now classifies only a structurally usable
required `<input type="email" name="...">` nested inside a POST form with an
exact owned `/commerce/trx-easy/start/<positive numeric SKU>/` action. It
rejects disabled/readonly/hidden/inert/ARIA-hidden fields, inaccessible
wrappers and closed template/details/dialogs, duplicate attributes,
overrides, incompatible form action or encoding, excessive/inconsistent
lengths, pattern and inputmode restrictions, and missing required email.
Invalid nested/ambiguous forms cannot be counted as clean source proof.

The read-only JSON report now separates **email hints** from **usable
source controls**, with fixed-category rejection codes only. No buyer
addresses, raw forms, server paths or credentials are disclosed. The
categories still only describe **disk source**, not active Passenger
routing, Django rendering, customer checkout or payment settlement.

The exact reviewed Git blob is `f93556203417399e6c099f182cddea4432260532`, pinned in **both existing
cPanel SSH routes**. The previous pin is superseded; the pin
verification itself remains mandatory and fail-closed.

- [Exact-head GitHub Actions run](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/43565991212): source-only 48 tests, secure bridge 9 tests and new source-integrity 60 tests — **117/117 PASS**.
- [New 54 negative cases + 6 positive/source tests](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/fix/mpw-cpanel-source-provenance-bridge-only-20261114/tests/test_mpw_cpanel_email_source_integrity_20261114.py).
- Owner acceptance still requires authenticated, read-only cPanel source/Passenger inventory, followed by explicit release approval; this PR cannot run a private cPanel operation from a PR ref.
- **Commercial and live impact remains unknown**: zero newly authorized customer POSTs, mail sends, purchases, DB writes, payment transfers or deployments were performed.
