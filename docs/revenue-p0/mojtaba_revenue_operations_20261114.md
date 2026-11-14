# mojtaba.bot.ai — Revenue operations source remediation (2026-11-14)

**Private management objective:** provide honest, read-only evidence for existing lead and website telemetry; support scenario pricing without accidentally claiming received funds. The agent identity remains **mojtaba.bot.ai**. No second autonomous bot, payment channel or trade executor is created.

## Effective changes in this source branch

1. \`core/revenue_unit_economics.py\`: one-currency, strict Decimal financial scenario engine.
2. \`command_center/revenue_operations.py\`: private aggregate CRM + funnel truth snapshot.
3. \`command_center/commerce_funnel.py\`: bounded, non-N+1 product aggregation; event count != verified revenue.
4. \`command_center/urls.py\`: \`/staff/command-center/api/bot/revenue-operations/\` owner-only read-only endpoint.
5. \`core/management/commands/mojtaba_revenue_ops_readonly.py\`: local, no-side-effects evidence CLI.
6. \`core/management/commands/mojtaba_quote_scenario_readonly.py\`: local quote calculation CLI.
7. \`core/tests/test_revenue_unit_economics_20261114.py\`: strict, side-effect-free math regressions.
8. \`command_center/tests/test_revenue_operations_20261114.py\`: owner access, no PII, funnel and backlog regressions.

## Business controls and caveats

- A CompanyInquiry with status \`approved\` means only preliminary review; not contract signed, not buyer qualified, not invoice paid.
- \`payment_confirmed\` and \`delivery_success\` in CommerceFunnelEvent are internal observational counters. They have **no external settlement receipt or proof of buyer delivery**.
- Money outputs are **hypothetical scenario calculations**, never settled cash. Each currency is separate; no conversion between IRR/IRT, USD, TRX.
- No raw customer email, phone, subject, message, UTM, invoice or wallet data are included in the aggregate operations response.
- No network call, SMTP, SMS, webhook delivery, payment, coin movement, database write or production deploy occurs in these endpoints or commands.
- \`/staff/command-center/api/commerce-funnel/\` retains existing staff authorization. Owner-only \`/api/bot/revenue-operations/\` has superuser gate, GET restriction, no-store and bounded windows 7/30/90 days.
- Product snapshots are top 25 by event frequency, determined with 26-row probe; date filters exclude future timestamps.
- Backlog can include leads older than the reporting window; closed leads do not count as open.
- A web HTTP 200/PR/CI green is not evidence of sales, externally settled revenue, or delivery.

## Verification / execution instructions

Offline check of the pure calculator:
\`python -m unittest discover -s core/tests -p 'test_revenue_unit_economics_20261114.py' -v\`

Django isolated database tests (non-production):
\`python manage.py test command_center.tests.test_revenue_operations_20261114 core.tests.test_revenue_unit_economics_20261114 --keepdb\`

System check:
\`python manage.py check\`

Owner CLI (read-only):
\`python manage.py mojtaba_revenue_ops_readonly --days 30\`

Price CLI: pass exactly the schema shown in \`core/revenue_unit_economics.py\`, containing 10 input fields; no customer personal data. The resulting financial fields remain scenario-only and require separate owner approval.

## Known limitations / NO-GO

- Integration/database tests must be executed on a trusted exact-commit runner and logged before any merge. **Do not mark tests PASS merely because files exist.**
- This branch cannot inspect the production Passenger root, live MariaDB/SMTP, independent TRON settlement, private SKU bytes, actual buyer confirmation or contract signatures.
- No live sales fix, customer contact, invoice dispatch or collectible revenue is claimed.
- Production: verify backup/restore, runtime hashes, effective DB, release policy, secrets, exact-head CI and rollback; seek individual owner approval for deployment and financial/legal actions.
- If integrations conflict with stacked drafts #2287/#2289 or the separate private Gateway draft #23, reconcile exact file SHAs without force merges.
- This document may be published in source only; never expose real customer records or server secrets.

## Acceptance table
| Gate | Required | Present at source commit? |
|---|---|---|
| Owner-only endpoint + no PII | Code and DB regressions | code present; execution unverified |
| Event ≠ unique buyer ≠ cash | Explicit schema + tests | code present; execution unverified |
| Quote safe inputs | Decimal/units/rounding tests | code present; execution unverified |
| No mutation or external service | Code audit | code intended; runtime unverified |
| Source-to-runtime parity | SHA/provenance comparison | UNKNOWN |
| Real external settlement | Reconciled independent provider evidence | UNKNOWN |
| Real buyer delivery | Independent acknowledgement | UNKNOWN |
| Legal rights to SKU | Individual product manifest | UNKNOWN |
| Rollback and backup | Verified procedure on live host | UNKNOWN |
| Financial net profit | External receipt plus actual costs | UNKNOWN |

This source branch is a **documented code change**, not a certification of 100% readiness.
