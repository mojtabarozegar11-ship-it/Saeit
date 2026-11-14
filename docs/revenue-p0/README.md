# Revenue P0 service implementation — source-only draft (2026-11-14)
**Goal:** first verified paying, served customer. **Current state:** pre-release source, not real revenue.

Existing sites only:
- `https://mojplaywin.com/services/` — English single-problem website sales/checkout inquiry.
- `https://zomorodmelal.ir/services/` — Persian farm break-even/sensitivity inquiry.
- Canonical operations identity: **`mojtaba.bot.ai`**. No independent bot, gateway, background agent, or additional site created.

## Real changes (non-production)
1. Modern MojPlayWin `core/templates/mojplaywin/section.html` service-only manual email CTA.
2. Legacy MojPlayWin `core/templates/brands/mojplaywin/page.html` service-only manual email CTA.
3. Zomorod `core/templates/core/services.html` manual `/contact/` inquiry.
4. Deterministic, privacy-guarded qualifier `scripts/revenue_dual_offer_qualifier.py`.
5. Standalone source and CLI tests in `tests/test_revenue_*py`.
6. Both languages' bounded terms, anonymized examples and KPI acceptance process.

## Verify without network, secrets, payments or deployment
```sh
python3 -m unittest discover -s tests -p 'test_revenue_*.py' -v
python3 scripts/revenue_dual_offer_qualifier.py docs/revenue-p0/example-checkout-intake.synthetic.json
python3 scripts/revenue_dual_offer_qualifier.py docs/revenue-p0/example-farm-intake.synthetic.json
python3 product_recipes/farm_enterprise_economics/calculator.py docs/revenue-p0/example-farm-model.synthetic.json
```
The example farm model's additional `synthetic_example` field is an editorial marker ignored by the calculator; do not interpret sample results as verified market data.

## Go/no-go separation
**SOURCE** file commits and CI are not **LIVE** route proof. Inquiry CTA is not **PAYMENT** proof, and payment evidence is not **DELIVERY** proof. Before any non-draft release, review route ownership, current stylesheet and templates, mobile accessibility, authorized contact channel, data retention and compliance; demand evidence for a tested lawful invoice/receipt/download path.

Do not merge/deploy, send customer mail, issue invoices, accept TRX or other money, or disclose customer information solely because this source package exists. The customer-facing price bands are exploratory, non-binding and only for the international service; local farm price is not approved.


## 2026-11-14 isolated extension: one bot, eleven revenue candidates

The existing two website service CTAs remain the only **repository-draft inquiries**:
website checkout diagnosis/repair (MojPlayWin) and farm break-even analysis
(Zomorod). The nine additional records in
`scripts/mojtaba_revenue_portfolio.py` are **candidate ideas only**, not
products being sold, deployed routes, settled orders, verified legal
payment channels or additional bots. All eleven explicitly retain eight
release gates, and all have `commercial_release=blocked_unverified` and
`revenue_collected=null`.

Only `mojtaba.bot.ai` is the canonical bot identity. The two existing
sites are sales surfaces, not new independent agents or payments systems.

Run the new source-only and privacy gates without credentials or external calls:

```sh
python3 -m unittest discover -s tests -p 'test_mojtaba_*.py' -v
python3 -m unittest discover -s tests -p 'test_revenue_intake_io.py' -v
python3 scripts/mojtaba_revenue_portfolio.py --catalogue
python3 scripts/mojtaba_revenue_portfolio.py --synthetic-funnel docs/revenue-p0/synthetic-funnel-onebot-20261114.json
```

These are local, repeatable, **synthetic** checks. The funnel input must be
PII-free and marked `synthetic_example=true`. The scripts refuse to assert
real revenue, actual leads or nonzero conversion for unverified customers.

### New intake confidentiality and data-integrity controls

The existing `scripts/revenue_dual_offer_qualifier.py` now uses
`scripts/revenue_intake_io.py`. It declines symlink/non-regular or oversized
intake files, duplicate JSON keys (including duplicate consent), non-finite
numbers and unsafe/previously existing output destinations. A new local
result is created exclusively with POSIX mode 0600; any old file is preserved.
The output is allowlisted anonymized triage, not a quote or an invoice.
Use no real customer identifiers in local JSON. Secure disposal/retention of
original customer records is **not** provided by these source-only tools.

### First-real-sale evidence, not optimistic percentages

Verify both live site routes independently; confirm that the contact
destination works and the service can actually be delivered. Obtain an
individual owner approval for each quote, scope, price, communication, lawful
collection route and production change. Then verify accepted payment,
refundable obligations, private artifact quality and customer delivery.
Only after this independent chain can `paid_orders`, `delivered_orders`
and real collected revenue stop being UNKNOWN.

See `docs/revenue-p0/mojtaba-one-bot-multi-income-decision-record-20261114.md`.
