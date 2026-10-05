# Zomorod CostKit — first revenue candidate

One product only: an offline Persian/English ingredient and complete-order costing tool for small caterers and home food businesses.

**State: tested release candidate; NOT deployed, NOT payment-certified, NOT earning revenue.**

The existing production tree `/home/zomorod2/Saeit` has roughly 25,503 pre-existing changes and the active `moj/` application is largely untracked. Do not stage that tree wholesale. This candidate is isolated in `/home/zomorod2/revenue-costkit-review`, branch `codex/first-revenue-costkit-20261005`.

## What is included

- Actual downloadable product under `product/`: original source, guide and licence; no network requests or paid model dependency.
- Django sales page, session-scoped order account, explicit terms acceptance, immutable IRR price, Zarinpal request/verification adapter, idempotent paid events, versioned artifact archive and authenticated delivery.
- Customer support/feedback/refund-request tickets and owner-only responses. Refund registration records an already completed human action; it cannot transfer money.
- First-party funnel and attributable revenue reporting. No advertising list or unsolicited communication. No profit, ROI or distributable-revenue fabrication.
- Owner identity reused through `moj.communication.auth.authenticated`; no new privileged credential.

## Test

From the parent of `revenue_stream`:

```
node --test revenue_stream/tests/calc.test.js
DJANGO_SETTINGS_MODULE=revenue_stream.test_settings /home/zomorod2/Saeit/.venv/bin/python -m unittest discover -s revenue_stream/tests -p 'test_*.py'
```

`test_settings.py` is an isolated test harness, not a production configuration. Fake gateway responses exist only in tests; production has no fake-success path.

## Human-gated integration

Read `docs/ACTIVATION.md`, `docs/REPORT_FA.md`, `docs/TEST_EVIDENCE.md` and `docs/LUNA_HANDOFF.md`.
Do not edit Passenger, production settings, cron, live routes or payment credentials until the owner approves the concrete release.

No environment, runtime database, private key, seed phrase, access token, generated customer order or full-site backup belongs in Git.
