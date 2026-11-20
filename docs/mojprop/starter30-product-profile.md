# MOJ PROP Starter30 operational product profile

Status: internal commercial specification; not a legal contract and not a payment release.

The English Starter30 profile now has one auditable source for the owner-configured
operational values:

| Item | Value |
|---|---:|
| Virtual starting capital | $1,000 |
| Challenge duration | 60 days |
| Maximum daily drawdown | 6% |
| Maximum risk per trade | 3% |
| Maximum open-position risk | 4% |
| Entry fee indication | 30 TRX |
| Retry discount | 40% |
| Retry fee indication | 18 TRX |
| Customer funds held by company | No |
| Trading environment | Simulation |
| Performance rewards | Real rewards may be paid under approved terms |
| Profit guarantee | None |

## Deliberate blocker

The consistency rule is not marked final in code. It must be confirmed in the
commercial terms before a paid route can be opened. The profile therefore
reports the consistency-rule blocker and does not alter the readiness gate.

This file is not legal advice. It does not define jurisdiction, eligibility,
KYC/age verification, refunds, support, invoices, reconciliation or settlement.
Those remain separate release gates.

No route, wallet, invoice, payment control, database, customer record or broker
connection is touched by this profile.
