# Virtual chief economist: tested operating analysis, not a title

## What the cycle actually computes

Run `python manage.py business_scientist_cycle` against the configured Django
database. The command queries task counts by action and status (including the
oldest task age), order totals grouped by status and currency, payment-intent
amounts grouped by provider/status/currency, internal ledger rows grouped by
entry type/currency, and the active catalog grouped by currency.

Those are attributable application records, not independent proof of settlement
or customer outcomes. The cycle therefore keeps provider settlement, market
demand, accepted factory output, production-site health, and attributable costs
unknown until a verified source adapter supplies them.

The decision order is deliberately evidence-bound:

1. If blocked work exists, investigate its blocker and required evidence.
2. Else, if work is queued, compare stage counts and age before changing capacity.
3. Else, if products exist but no orders are recorded, instrument visits,
   product views, checkout, payment, and fulfillment. Do not infer that demand
   is absent or change prices without a funnel.
4. If none of those facts establishes a constraint, report insufficient
   operating evidence and identify the missing source data.

## Financial rule

The tested helper `evaluate_unit_economics` computes:

```
contribution = reconciled_settled_cash
             - refunds
             - provider_fees
             - fulfillment_costs
             - acquisition_cost
contribution_margin = contribution / reconciled_settled_cash
CAC = acquisition_cost / new_customers
```

It requires one currency and every input. If any field is unknown, it returns
`not_computable`; it does not substitute order totals, payment intents, or
internal ledger rows for settlement. The current schema lacks an independent
provider-to-ledger settlement and cost reconciliation adapter, so the live
business contribution remains not computable.

## Experiment and expansion discipline

Before an intervention, record its source, baseline window, target customer,
primary outcome, guardrail, cost ceiling, decision date, and rollback condition.
After it, compare the same population and window; retain the change only if the
primary outcome improves without crossing a guardrail. Do not call a draft,
build, CI pass, or simulated purchase a customer outcome.

Expansion is blocked until there is evidence for a named customer problem,
willingness to pay, reliable delivery, positive contribution by currency,
repeatable acquisition, and controlled scaling with tested rollback.

## Audit and authority

`--record` writes a sanitized audit receipt. Without it, the cycle is read-only.
No automatic spending, payment, contract, personal-data use, production release,
external publication, irreversible change, or legal decision is granted. This
implementation does not claim the factory, cPanel sites, or payment provider
are connected or running autonomously.
