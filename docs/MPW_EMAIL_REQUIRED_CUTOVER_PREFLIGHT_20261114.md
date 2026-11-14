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
