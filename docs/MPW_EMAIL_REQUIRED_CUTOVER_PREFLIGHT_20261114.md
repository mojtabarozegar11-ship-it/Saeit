# MojPlayWin buyer-email cutover: remove obsolete SOURCE blocker, not production approval

2026-11-14 — sole canonical identity: mojtaba.bot.ai. Source branch only.

## Defect found
The dynamic /store/ cutover candidate expected an email-free guest invoice, while current owner policy and actual guest order adapter require validated real buyer email plus immutable GuestOrderEmail claim. The incompatible gate prevented source preflight of the legitimate checkout.

## Real correction
Current source preflight now calls the independent read-only email-required module before importing Django. It demands reviewed guest, recovery, claims, model-registration, migration and rendered form code. It does not prove applied migration or active Passenger root. The existing public publishing denial require_owner_email_policy_before_cutover(PUBLIC) remains unchanged; the legacy email-free publisher is still permanently denied.

## Commercial gates still unverified
1. Actual cPanel Passenger app registration and effective template origin.
2. Actual SQL migration 0049 and one-claim-per-order unique constraint (read-only, private).
3. Dynamic catalog after owner-approved rollout; current public GET evidence remains static fallback.
4. Current checkout CSP script-src policy mismatches across six public routes.
5. Server-side valid buyer email binding in order POST, without real order creation by this tool.
6. Lawful and owner-approved TRX collection with independent chain finality.
7. Authorized paid download, QC and customer acknowledgment.
8. Explicit owner deployment approval, immutable backup, exact rewrite-rule, rollback.

The source-only report never opens a network connection, database, sends email, issues invoice, trades, modifies cPanel or receives money. Source passing is not production commerce readiness.

## 2026-11-15 recovery POST ambiguity fix (source branch; no mail sent)
- The receipt/recovery email form now requires exactly one canonical `email` field. Duplicate identical addresses, multiple conflicting addresses, empty duplicate values and legacy checkout aliases fail closed; the customer sees the same generic response rather than an email-existence oracle.
- The recovery-code form similarly requires exactly one `code` value; multiple codes never select the last `QueryDict.get` result or consume a one-time token.
- Request method, POST interface, maximum length, type and ASCII control characters are validated before any rate-limited lookup or token consumption. The existing Django email validator, token expiry and database guards still run afterward.
- `tests/test_mpw_recovery_post_ambiguity_20261115.py` supplies 43 offline unique test methods, using the actual helper AST from the current production-source module. Source workflow and broader public audit both invoke this test suite; success proves input classification only.
- **Production hold:** both opt-in flags and the live sender/domain/SMTP configuration, applied migrations, CSP, effective Passenger root, static fallback removal, payment finality and protected download must still be independently verified. Prior owner authorization to prepare emails/TRON never permits emitting customer mail, transferring money or deploying this Draft PR before these concrete gates pass.
- Customer recovery must not encourage paying again after a missing browser cookie. Never describe a created invoice, a green test, or an HTTP 200 response as a completed sale.
