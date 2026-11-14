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


## Presale intake security handoff — 2026-11-14

The upgraded *existing* two-offer qualifier uses the shared
`scripts/revenue_intake_io.py` strict local reader/writer. It rejects
duplicate consent keys, symlinked/non-regular input, non-finite JSON,
oversized or invalid UTF-8 input, and pre-existing output paths; newly
created anonymized reports are mode 0600. **This does not handle raw
customer PII**, establish paid orders, send email or create an invoice.

The concurrent parent branch also added a richer **10-channel** one-bot
portfolio/CLI/pricing research module. The security handoff is deliberately
layered on top rather than replacing those files. The canonical operating
identity remains `mojtaba.bot.ai`; no independent bot is deployed.

Local evidence: 15/15 strict I/O tests and 12/12 direct qualified service
CLI integration tests passed with Python 3.13.5. The original repository
test suites and live website acceptance remain separate requirements.

Review `mojtaba-single-bot-intake-security-handoff-20261114.md` and
the two `service-qc-*-template-*.md` files for scientific/technical
client deliverable acceptance. Zero real income or 100% commercial
completion must NOT be inferred from source-only passing tests.
