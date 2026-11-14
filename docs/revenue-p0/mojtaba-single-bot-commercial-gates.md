# Mojtaba.bot.ai — single-bot revenue gatebook (source-only)

**Canonical identity:** `mojtaba.bot.ai`. The two sites are distribution channels, NOT separate bots. The portfolio module and CLI are deterministic **capabilities**, not background workers, connected payment gateways or independent agents.

**Current disposition:** DRAFT / NO-GO for production activation. No current-session proof of DNS, HTTPS, hosted runtime, customer order, settled payment, or delivery on `mojtaba.bot.ai`. Never claim source checks equal revenue. No new fee, paid model, exchange order, wallet transfer, email, customer submission, deployment or deletion has been authorized.

## Ten revenue routes and exact truth levels

| Code | Channel | Route | Commercial model | Source truth | Customer action | Release blocker |
|---|---|---|---|---|---|---|
| farm_economics | Zomorod | /services/ | Contracted economic analysis | Draft source | Official /contact/ inquiry | Verified route, scope/data, local quote, consent |
| website_diagnosis | MojPlayWin | /services/ | Bounded diagnosis | Draft source | Manual support email | Live source, service terms, manual collection approval |
| website_bounded_repair | MojPlayWin | /services/ | Fixed-scope repair | Draft source | Manual support email | Real defect, reproducible test, signed scope, authorization |
| cafe_b2b | Zomorod | /ghanadi/cafe-shiraz/ | Repeated wholesale inquiry | Existing source | Opt-in form | Actual supply capacity, food-law compliance, quote |
| company_catalog | Zomorod | /store/ | Product pre-sale inquiry | Existing source | Official intake | Enabled SKU, stock, rights, lawful payment route |
| industrial_feasibility | Zomorod | /industry/ | Project feasibility | Existing source | Official /contact/ | Data, qualified scope, signed contract |
| research_contract | Zomorod | /research/ | Applied research contract | Existing source | Official /contact/ | Rights to data, method, ethics, delivery approval |
| digital_publication | MojPlayWin | /store/ | Licensed digital file | Proposed, NOT listed | Internal review only | Finished file, verified copyright, QC, secure delivery |
| game_license | MojPlayWin | /games/ | Game license | Proposed, NOT listed | Internal review only | Running game, license, fulfillment, anti-abuse and payment |
| trading_education | MojPlayWin | /services/ | Educational training only | Proposed, NOT listed | Internal review only | Written educational material and jurisdictional review; NO trading or signals sold |

The last three are deliberately **not** public product offers. An idea, SKU, title, token, or file path alone is not a deliverable.

## Workflow — strict evidence before paid fulfillment

1. Receive an **opt-in** customer inquiry in an already approved service channel. Never send unsolicited bulk messages.
2. Quarantine identity/contact information in the authorized private CRM. Do **not** put names, email, wallets, passwords, addresses, raw customer messages or receipts in GitHub or the portfolio CLI.
3. Send to the offline single-bot policy only metadata (offer code, bounded issue/evidence counts, consent boolean, document counts). Document counts are **unverified assertions**.
4. Review scope, reproducible evidence, commercial rights, physical inventory or digital artifact, shipping/delivery capability and lawful jurisdiction.
5. Owner separately approves **the individual written quote** and lawful payment method. The portfolio does not issue invoices or accept money.
6. Receive actual settlement evidence through a compliant provider or signed ledger, independently verify it against an order, and check duplicates/refunds/fees.
7. Only after verified payment and quality-control delivery, fulfill entitlement and obtain buyer confirmation. Keep a redacted immutable audit trail.
8. Report receipts and net earnings from independent business/accounting evidence only — never from Python unittest, CI, sample KPI, HTTP 200, clicks, or mock orders.

### Unit economics before a manually authorized quote

The additional `scripts/mojtaba_revenue_margin.py` capability uses exact `Decimal`
arithmetic on **synthetic-only** example costs and correctly distinguishes IRR
whole units from USD cents. For an assumed direct cost `C`, overhead `H`,
proportional processing fee `f` and target pre-tax contribution margin `m`:

```text
P_min = ceil_to_currency_unit((C + H) / (1 - f - m))
```

This is a **decision-support floor, not a final price**. The model deliberately
excludes tax, fixed processing charges, refunds, price sensitivity, inventory
cost uncertainty and legal compliance. It never authorizes a quote, invoice,
transaction or delivery, even if the calculated margin is positive. Actual
costs must be independently verified and an individual owner-approved quote
issued through the existing lawful channel before any sale.

### Monetary constraints

Existing MojPlayWin checkout service page displays **indicative, non-binding** USD 29–49 diagnosis and USD 79–149 bounded repair bands. These do not constitute owner-approved transaction prices. **All other listed models remain manual quotation without invented amounts**. The company site cannot present an operational payment gateway until contractual/identity/compliance gates are satisfied.

### Canonical one-bot consolidation

Legacy Django, PHP and VPS agents may remain recorded as source-defined roles, not independent bot names. No legacy scheduler or database identity may be deleted/deactivated until **both-host runtime evidence, accepted task-delivery receipts, pending-work reconciliation, rollback plan and a specific approval** exist. The 10 revenue codes are internal capabilities, not 10 autonomous workers.

### Local operator commands — dry, offline

```bash
python3 scripts/mojtaba_revenue_cli.py --catalog
python3 scripts/mojtaba_revenue_cli.py --qualify docs/revenue-p0/mojtaba-portfolio-inquiry.synthetic.json
python3 scripts/mojtaba_revenue_cli.py --synthetic-kpis docs/revenue-p0/mojtaba-portfolio-kpi.synthetic.json
```

No network, API keys, email sending, host changes or customer transactions. `--output` creates a new file with mode `0600`; it never overwrites a file.

### Data & percentage dashboard contract

- `source_tests_passed / source_tests_run`: engineering ratio; not order conversion.
- `route_views`, `opted_in_inquiries`, `qualified_unique_leads`: UNKNOWN until first-party non-duplicated evidence.
- `quote_rate = approved_quotes / qualified_unique_leads`: UNKNOWN for missing/zero denominator.
- `paid_close_rate = independently_settled_paid_orders / approved_quotes`: UNKNOWN for missing/zero denominator.
- `fulfillment_rate = independently_accepted_deliveries / settled_paid_orders`: UNKNOWN for missing/zero denominator.
- `net_collected = settled receipts - actual verified refunds - actual processor fees`, with unique order-to-payment reconciliation and matching currency. Do not compute by combining currencies without an authorized conversion.
- Progress may be **100% of this cycle's completed code/test actions** while deployment or earnings remain UNKNOWN. Unobserved income is **UNKNOWN, not 0**.

### Current NO-GO evidence checklist

- [ ] DNS/HTTPS and hosted code for `mojtaba.bot.ai` positively attested
- [ ] Main and legacy site service routes matched to actual deployed files
- [ ] Intake acceptance and private persistence tested with consent on authorized infrastructure
- [ ] Qualified leads measured without personal data leakage
- [ ] Price/terms, right to sell, stock and delivery evidence reviewed
- [ ] Specific owner approval for any paid action, checkout or production deployment
- [ ] Payment provider compatibility, tax requirements and settlement evidence verified
- [ ] Production seller/customer acceptance observed, independently and redacted
- [ ] Single-scheduler cutover and rollback proved before shutting down any legacy role

**Never remove the NO-GO gate merely because a workflow is green.**
