# Mojtaba.bot.ai — non-financial service order and TRON quote boundary

**Status: code integrated in a Draft PR, not a customer-facing release.** No checkout URL is registered here and all quote issuance is disabled by default. Nothing in this package settles payments, executes investments or delivers a digital file.

## Current internal sequence

1. Internal, authenticated application code selects a **protected, owner/rights/legal-approved** non-financial service and exact tenant route.
2. `start_guest_nonfinancial_signal_purchase(buyer_email, order_id, trusted_route, trusted_offer)` checks the guest email syntax and derives a **tenant-bound HMAC digest**, not an unsalted email SHA.
3. It atomically inserts a unique, pending Django order and a one-to-one TRX invoice **proposal**, or rolls both back.
4. The invoice proposal binds the same buyer digest, offer, price in integer SUN, TRON-mainnet receiver, tenant host/path and time window into an HMAC-signed token.
5. A replay of the same buyer/order receives the same quote while valid. Cross-tenant and conflicting invoice IDs fail closed. An expired quote requires a new order.
6. On every read, the quote's signature, receiver, amount, scope and validity are rechecked. None of this is an independently verified blockchain settlement.

## Required protected configuration (not committed)

| Environment name | State by default |
| --- | --- |
| `MOJTABA_SIGNAL_TRON_QUOTE_ENABLED` | `false` (must remain false until independent release approval) |
| `MOJTABA_SIGNAL_CANONICAL_HOST` | blank, denies |
| `MOJTABA_SIGNAL_TRON_RECEIVER` | blank, denies |
| `MOJTABA_SIGNAL_TRON_QUOTE_HMAC_KEY_HEX` | blank, denies; independent 256-bit hex |
| `MOJTABA_SIGNAL_BUYER_HMAC_KEY_HEX` | blank, denies; **different** 256-bit hex |
| `MOJTABA_SIGNAL_APPROVED_SERVICE_FINGERPRINTS` | empty allowlist, denies |

The exact offer fingerprint binds the host, path, tenant, language, service type, offer ID, currency, amount and offer/route approvals. The fingerprint alone does not prove legal authorization. A trusted operator must map it to **independent contract, rights and sector approval records**. Changes to price or route require a new reviewed fingerprint.

## Critical release gates NOT completed

- Jurisdiction review and permission to sell the exact non-financial research/education service; financial buy/sell/hold recommendations remain blocked.
- Independently verified ownership and final deliverable/version of every report.
- Real mailbox-ownership confirmation, secure email delivery/outbox, refund and support handling. Email syntax alone is not mailbox proof.
- Persistent production invoice ledger, collision-safe issuance and independently verified mainnet transfer matching **recipient, exact amount, transaction hash, finality, time window and unique invoice**.
- Replay-safe, transactionally durable settlement state machine, double-entry ledger, refunds and entitlement.
- Authenticated, rate-limited public endpoint with CSRF/abuse controls, verified tenancy, secrets provisioned in protected environment, monitoring and rollback.
- Real cPanel/VPS and MariaDB migration preflight, database backup and restore exercise, live canary, owner approval to deploy.

## Evidence and retention

- CI must pass the pure contract suite, `makemigrations --check --dry-run signal_orders` and `manage.py test signal_orders`.
- Do not store raw buyer email in the order JSON or publish signed quote tokens in logs.
- Rotate HMAC keys with an explicit multi-key verification and migration plan, rather than changing the active key in-place (old quotes would fail verification).
- Audit only sanitized aggregates; never report order or invoice proposal counts as paid revenue.
