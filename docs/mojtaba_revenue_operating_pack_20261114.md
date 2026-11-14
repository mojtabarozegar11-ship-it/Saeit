# Mojtaba.bot.ai — revenue operating pack (2026-11-14)

**Owner:** one canonical orchestration identity: `mojtaba.bot.ai`. No second bot,
autonomous trader, duplicate cron, public deployment, paid tool or purchase is
authorized by this document or the repository gate.

**Status:** actionable service preparation and SOURCE audit only. Nothing here
proves a live client, paid transaction, recoverable checkout or fulfilled order.
The accountable business metric is **received cash with lawful evidence and an
accepted, privately delivered customer-specific result**.

## 1. Reuse the existing sales channels — do not launch parallel sites

| Lane | Existing source | Offer type | Commercial rule |
| --- | --- | --- | --- |
| Website Doctor | `/earn/website-doctor/` + `/earn/inquiry.php?service=website-doctor` | Scoped web diagnosis/repair | Quote after intake; do not promise increased conversion |
| Farm enterprise break-even | `product_recipes/farm_enterprise_economics/` | Expert-reviewed analytical report | Custom quote only after validated farm records and lawful payment route |
| Chess PDF — 72 | Existing MojPlayWin store | Digital delivery | Do not claim live paid checkout until email, TRX settlement and private file verified |
| Illustrated book — 225 | Existing MojPlayWin store | Digital delivery | Same payment and delivery rules |
| Atelier kit — 879 | Existing details page; unresolved rights/QC | Availability inquiry | No premature direct checkout or guaranteed fulfillment |
| Remaining 11 MojPlayWin services | Existing `/earn/` hub, detail pages and `inquiry.php` | Mixed scoped services/previews | Classify individually; listings or indicative prices are not orders |

### Website Doctor — bounded offer for a real client

**Scope before quote:** one client-controlled site and one concrete problem
(such as a broken guest checkout, service inquiry path or slow landing page).
The client supplies the URL, authority to inspect and any redacted evidence.
The work is a technical diagnosis with reproducible observations; repairs
require separate authorized access, agreed scope, backup and rollback.
Source-visible indicative ranges on existing website are not accepted quotes.

**Deliverable — ready-to-fill report structure:**

1. Client-approved scope; date/time and system environment.
2. Evidence register: exact URL, request method, status, controlled screenshot
   or sanitized response excerpt, and reproduction instructions.
3. Classification: **confirmed defect / unverified / not reproducible**.
4. Risk to checkout, leads, data security and availability, without invented
   monetary-loss calculations.
5. Ranked remedy plan with implementation prerequisites, estimated effort
   qualified as a proposal, and non-destructive rollback.
6. Explicit tests after a separately approved fix, plus limitations.
7. Version/hash of final PDF or private report and a customer acceptance note.

**No guarantee:** no automatic login, server changes, third-party accounts,
SEO ranking gains, conversions or legal/financial advice.

### Farm profitability and break-even — bounded offer for Iran

**Inputs requested with consent:** reporting period and currency, verified
quantity actually sold, unit sale price, variable cost per unit, attributable
fixed costs, selling fee rate, optional area/irrigation and an explicit list of
omitted costs. Decline a firm profitability conclusion without consistent
units, dates, fees and source records.

**Computations:** for uniform units,
`net_unit_contribution = unit_price - variable_cost - (unit_price * fee_rate)`;
`operating_profit = units_sold * net_unit_contribution - fixed_cost`.
Break-even units are rounded **up** from
`fixed_cost / net_unit_contribution` when the denominator is positive.
Use the existing original `farm_enterprise_economics` calculator as the
implementation, not a new parallel calculator. The report must distinguish
profit from cash flow and must not invent sales demand.

**Purely illustrative worked example — NOT client data:**

| Input | Example value |
| --- | ---: |
| Units sold | 1,000 |
| Price / unit | 10.00 (single hypothetical currency) |
| Variable cost / unit | 4.00 |
| Selling fee | 5% of sales |
| Fixed costs for same period | 3,000.00 |
| Unit contribution after fee | 5.50 |
| Total contribution | 5,500.00 |
| Operating profit | 2,500.00 |
| Break-even | 546 units (round up from 545.4545...) |

The example does not establish a farm's profitability, loan suitability,
exchange rate or price forecast. Deliver an assumptions table, nine
price/quantity scenarios if inputs permit, a separately documented cash-flow
plan, a review checklist and a limitations statement. Do not label an
automated score as expert certification.

## 2. One-bot internal assignment — no bot multiplication

`mojtaba.bot.ai` is the **only** canonical identity. Existing A–E streams,
Django roles, PHP agent records and VPS tasks are mission modules and historical
registries, not permission to create separate bots or turn on new schedulers.
Read-only topology evidence from Nov 12 reports a source role inventory and
partial cPanel observation, not a verified count of live workers or a completed
cutover. Consolidation requires live task/receipt and cron mapping, a preserved
history, rollback and case-specific approval. Never set the progress to 100%
solely from the number of source-defined roles.

### Evidence-driven customer funnel

`qualified inquiry` → `consented scope` → `written, accepted quote` →
`legal payment route` → `independently reconciled paid receipt` →
`QC-approved exact deliverable SHA-256` → `private delivery and access proof`
→ `customer acknowledgement or documented resolution`.

Every arrow is a separate gate. An inquiry is not an order; an order is not a
settled payment; a repo build is not a downloadable customer artifact.
Do not paste private buyer messages, keys, addresses or raw receipts into
public PRs or issues. Use aggregate counts and non-reversible evidence IDs.

### Status semantics for managers and reports

- `SOURCE_PRESENT`: a code path exists and can be checked; not live.
- `UNVERIFIED`: missing independent live source or manual approval.
- `BLOCKED`: rights/payment/backup/safety prerequisite missing.
- `VERIFIED`: evidence and exact scope/version/receipt were checked.
- `REVENUE_RECEIVED`: transaction value, date and lawful settlement are
  independently reconciled. Refund/chargeback exposure must be retained.
- `DELIVERED`: exact version given privately to the paying client and
  accessible, with delivery receipt and quality/rights gates complete.

If the live revenue numerator or denominator is unavailable, report `UNKNOWN`,
not 0%, not a made-up progress ratio. Keep source coverage, runtime readiness
and realized cash in **three separate charts**.

## 3. Deployment and expense restrictions

No production deploy, merge, workflow dispatch, deletion, outbound marketing,
invoice or payment without case-specific approval. No new financial obligations,
subscriptions or credit consumption. Source changes stay in a Draft PR.
Zero approved spending is not zero actual business expenditure; cashbook must
be reconciled independently. Do not misuse unsupported country identities,
borrowed payout accounts or fake merchant KYC.

## 4. Use the executable source gate

```bash
python3 scripts/mojtaba_revenue_source_gate_20261114.py --format json
python3 scripts/mojtaba_revenue_source_gate_20261114.py --format markdown
python3 -m pytest -q tests/test_mojtaba_revenue_source_gate_20261114.py
```

Its checks cover 12 service details, 12 hub links, 12 PHP allowed service slugs,
HTML link integrity, CSRF/email/encrypted storage markers, two existing checkout
source routes, SKU879 details, farm toolkit and canonical bot. It intentionally
**does not POST**, invoke payment providers, send emails, read buyer records or
inspect the live cPanel server. The only credible live next step is an already
authorized **read-only** cPanel/Passenger, PHP intake and payment/fulfillment
inventory. New tools, hosts and workflows cannot substitute for an independently
verified real order.

## 5. Evidence inventory for this cycle

- 12/12 service detail paths found in `main` and each contains its own source
  inquiry route; price fragments are marketing *offers*, not realized prices.
- `mpw_revenue_20261020/earn/inquiry.php`: 13 allowed service/general keys;
  code contains CSRF, email validation, encrypted private storage and
  honeypot. Its public live status is not established.
- Existing `runtime/mojtaba_bot_disposition_sources_v1.json` declares the
  canonical bot identity, whereas runtime observation leaves the verified
  active-worker count and whole-company consolidation unknown.
- Source code `factory_config/active_quality_1000_policy.json` explicitly
  disables automatic quality certification. Do not claim 1000/1000 by fiat.
- No verified received cash, paid invoices or delivered SKU evidence has been
  produced by this source-only package.

**The operational acceptance criterion is one independently evidenced, legal,
paid and privately delivered order, not the number of actions, tests or pages.**
