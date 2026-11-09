# Mojtaba.bot — staged growth policy

Owner: Mojtaba Rozegar — Zomorod Melal  
Decision recorded: 2026-11-09  
Status: engineering plan; **not a deployed change or purchase authorization**.

## Revenue-first operating loop — required before infrastructure purchases

Mojtaba.bot must seek **more collected business revenue**, not merely lower
infrastructure costs or describe hypothetical opportunities. The first
commercial priorities are to make existing Zomorod Melal services and
MojPlayWin digital offers actually purchasable and deliverable; do not open
new speculative storefronts while existing checkout/delivery problems remain.

1. Check pending paid orders; deliver outstanding purchases before pursuing
   new sales. Preserve guest purchase by valid email and verified server-side
   payment confirmation. Reject duplicate payment references.
2. Verify a live checkout path, an actual useful offer, and receipt-backed
   digital delivery. A 200 HTTP response or a draft listing is not revenue.
3. Record qualified interested customers from consented channels, their
   purchase conversions, and reasons for legitimate purchase dropoff. Prepare
   free acquisition work first; external marketing and publication retain
   their specific approval gates.
4. Reconcile finalized payment provider records to unique delivered orders;
   do not treat invoices, pending transactions, internal ledger counters or
   test purchases as settled collected revenue.
5. Compute a period-matched operating surplus: **reconciled settled revenue
   minus actual current costs, prior commitments and protected reserves**.
   If any input is unknown, do not claim cost coverage or spendable surplus.
6. Reinvest only after these gates and an owner-specific purchase approval;
   measure subsequent monthly recurring costs and the new capacity's effect
   on additional verified customer receipts.

`core/revenue_growth_engine.py` ranks these blockers with a fail-closed pure
decision function; it is a planning component, **not** a deployed commercial
funnel, traffic source, payment gateway, autonomous purchaser or proof of sales.

Every reporting period must separate: customer-ready offers; qualified leads;
paid orders; fulfilled orders; externally reconciled collected cash; actual
operating costs; commitments; protected reserves; available operating surplus;
and the number of orders awaiting delivery. Until read from a trusted source,
each amount is **unknown**, never guessed as zero or displayed as progress.

## Stage 1 — grow on the existing VPS

1. Confirm the actual active Mojtaba.bot/master-agent process, version, task queue,
   scheduler, error rate, verified action outcomes and rollback mechanism.
2. Run `scripts/mojtaba_vps_expansion_preflight.py` on the VPS with the **actual**
   private database path and operations directory, resolved by a privileged
   operator without logging secrets or private paths.
3. Respect the same minimum storage reserve as
   `deploy/activate_vps_master_agent.sh`: a complete database rollback copy,
   plus the greater of 2 GiB or 5% of filesystem capacity. The new preflight
   also budgets 1 GiB by default for proposed software growth.
4. If blocked, do not install packages, create another agent loop, copy large
   models, or clean unrelated files. Investigate disk usage read-only and
   prepare a specific, owner-approved recovery or migration plan.
5. Validate actual software improvements in an isolated checkout with
   reproducible tests, distinct verified outcomes, bounded resource use and
   rollback before seeking any deployment approval.
6. Preserve existing one-master lock, user permissions, owner approvals,
   zero-paid-LLM default and the no-duplicate-actions policy.

Example **read-only** invocation (paths must be supplied from the live host):

```bash
python3 scripts/mojtaba_vps_expansion_preflight.py \
  --operations-dir /path/to/operations \
  --database-file /path/to/private/database.sqlite3 \
  --planned-growth-mib 1024
```

Output contains capacities and a decision only. Neither the script nor its
output is proof of successful deployment or commercial operation.

## Stage 2 — acquire a dedicated AI server

- Trigger: measured VPS limitations, an audited workload, realistic total
  cost of ownership, collected revenue, and **specific owner approval** for
  every purchase and commitment.
- **Binding self-funding gate:** no server, hardware, component, recurring
  subscription or manufacturing equipment purchase unless actual settled and
  reconciled business income has first covered all due operating obligations,
  protected reserves, existing commitments, the full purchase amount, and a
  documented buffer for the new recurring running costs. Forecasts, expected
  token appreciation, invoices awaiting payment, simulated trades, test orders
  and unrealized revenue do not count as available cash.
- Even when the financial gate is satisfied, record the vendor, price,
  warranty, ongoing power/cooling/hosting costs, delivered capability,
  downside risk and the owner's purchase-specific approval. Never infer
  permission to spend from a generic automation or agent instruction.
- If the gate is not satisfied, continue only cost-free, reversible VPS work
  supported by the existing approved infrastructure. Do not incur new
  subscription, API, cloud, renewal or equipment charges.
- Produce an itemized bill of materials with supported accelerator memory,
  CPU/RAM/storage, networking, power, cooling, warranty, backups and data
  migration. Do not treat a GPU memory figure as sufficient by itself.
- Confirm local legal, logistical, cooling, power, data protection and
  support requirements before selecting a supplier.
- The autonomous agent may recommend products and prepare purchase requests;
  it must not place or pay for an order without approval.

## Stage 3 — expand the dedicated server

- Migrate via encrypted backups and verified recovery; retain a fallback.
- Add private/local models, memory and retrieval, tool orchestration,
  voice/vision, batch workers and observability against measured demand.
- Keep physical safety controllers independent of the language model.
- Do not declare an upgrade successful until live service acceptance tests
  and user-relevant outcomes are confirmed.

## Stage 4 — connect part-making equipment

- Integrate only compatible, documented manufacturing interfaces, for example
  OPC UA where supported; do not bypass the equipment's certified controller.
- Start with a closed-loop CAD/CAM -> approved job -> machine -> measurement
  -> acceptance record; ensure traceability for every manufactured part.
- Machine activation, toolpaths, dangerous motion, high power or hazardous
  materials remain behind safety interlocks, independent emergency-stop
  systems and appropriately qualified human approval.
- Validate against applicable industrial robot safety requirements, including
  ISO 10218-1/2:2025 where in scope.

## Stage 5 — manufacture or buy upgrade parts

- For each part on the bill of materials, classify: `make`, `buy`, or
  `research`. Record raw materials, qualified processes, tolerances,
  inspection evidence, unit cost and lead time.
- Manufacture locally only when quality, safety and cost are demonstrated;
  purchase the remainder following specific owner approval.
- Count **verified** local manufacture, not design files or queued jobs, in
  self-sufficiency metrics. No unsupported claim of 100% independence:
  semiconductor fabrication, feedstocks and energy infrastructure may still
  depend on external supply chains.

## Reporting contract

For every change: actual action, evidence/reference, error or blocker,
remaining work, a percentage only when its numerator and denominator are
measured, and explicit distinction between code prepared, tested, deployed,
live, or commercially productive.

No stage transition authorizes deletion, deployment, payment, publication,
external messages, physical machine movement or other consequential action
without the corresponding approval and safety gates.

The project is not permitted to finance its own expansion with debt, credit,
unsettled receipts, undocumented third-party funds or an assumed future
return; every phase must be funded from verified, available operating surplus.
