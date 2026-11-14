# Mojtaba.bot.ai — precise one-message B2B contact and delivery evidence contract
2026-11-14. **Draft code only; no external message or deployment.**

## Revenue blocker isolated
Previous `external_write` grants were scoped merely to the company mailbox. The executor would select the first queued message *after* consuming the grant. The underlying send function could be called directly when the mail setting was enabled, without checking any owner grant. This creates consent, attribution and wrong-recipient risks and undermines reliable B2B sales communication.

## Twenty distinct implemented controls
1. Grant target is a `TradeEmailOutbox` record, not a generic mailbox.
2. Grant requires the exact numeric outbox ID.
3. Grant requires a valid lowercase SHA-256 fingerprint.
4. Fingerprint includes sender mailbox ID/address and intended recipient.
5. Fingerprint includes exact subject and body.
6. Fingerprint includes context and idempotency key.
7. Only queued outbox records can be approved.
8. Mailbox must be exactly `company-trade`.
9. Mailbox must be active.
10. Explicit outbound permission must be enabled.
11. Mailbox policy-gate enforcement must remain enabled.
12. Contact basis limited to consented inquiry, requested quote, existing customer.
13. A nonzero, syntax-valid evidence hash must accompany claimed contact basis.
14. No additional contact-context keys accepted.
15. Request creation requires active superuser identity and exact outbox ID.
16. Approval request reason excludes recipient/body and includes message digest.
17. Grant issuance and consumption revalidate outbox content and policy.
18. Sending directly without a valid one-time grant is rejected.
19. Specific sender address and channel must match host configuration before consuming grant.
20. State `sending` and one-time grant consumption commit before SMTP; transport errors become non-replayable `delivery_uncertain`, while success becomes `delivery_submitted_unverified` (not delivery/sale).

## Acceptance and proof distinctions
- `core/tests/test_trade_outbox_scope_20261114.py`: 40 isolated Django tests; only local-memory SMTP or mocked sends.
- Existing `core/tests/test_economic_trade_email.py`, `core/tests/test_grant_binding_20261114.py`, `core/tests/test_approval_grants.py`, and `tests/test_mojtaba_grant_policy_20261114.py` remain in scoped CI with updated fixtures.
- Source and CI are **not independent evidence** of consent, customer mailbox receipt, a reply, legal entitlement to send commercial email, settlement, paid sale, or site deployment.
- Even a nonzero consent evidence digest is an **unverified claim** about a private artifact. Human legal verification of the actual record, purpose, jurisdiction, retention and withdrawal is required before any real send.
- `delivery_submitted_unverified` means the mail transport returned one accepted message; the recipient may not receive it. Exceptions may occur after an external side effect and must never trigger blind replay.
- PR is stacked over the previous security/owner-grant Draft; do not merge to `main` or deploy or activate SMTP without explicit per-action owner permission and independent host review.
- No financial impact is claimed; outstanding commercial proof = inquiry reception, approved quotation, legal payment rail, independent settlement, private delivery and customer acceptance.
