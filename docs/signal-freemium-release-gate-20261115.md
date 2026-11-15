# Free educational signal preview + paid-plan intake preservation

Scope: **source-only**; use the existing Moj Prop `/moj-prop-intake/` persistent CSRF-protected lead API. Only one agent identity: `mojtaba.bot.ai`.

- Added a public no-price, non-actionable *historical-methodology* example on the Signal Desk. It is available without registration.
- Added an explicit one-off **free educational request** CTA, recording contact requests for manual review using the existing consent and ID/receipt contract. It does **not** activate email marketing subscriptions or promise delivery.
- Preserve exact paid SKU in the V4 buyer notes and receipt, rather than losing it to weekly/monthly/quarterly cadence only.
- Both legacy and V4 forms prefill free or allowlisted paid scope and remove untouched signal-prefill on service switches.
- Added contract regression tests to prevent phantom paid invoices, false live feed, silent plan loss and bot duplication.

**Deployment risk:** Moj Prop pages are static surfaces served by Apache; real request API may have hosting routing issues. Do not merge or deploy unless latest-head checks, main drift, manual-release triggers, backup/restore, tenant isolation, legal content review and rollback are confirmed. Existing code explicitly disables payments, publication and delivery.

**No** payment, TRX activation, customer email, live signal publishing, personalized financial advice, trade, deploy or spending authorized.
