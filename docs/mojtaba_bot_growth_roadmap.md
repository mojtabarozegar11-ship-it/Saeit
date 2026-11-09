# Mojtaba.bot — staged growth policy

Owner: Mojtaba Rozegar — Zomorod Melal  
Decision recorded: 2026-11-09  
Status: engineering plan; **not a deployed change or purchase authorization**.

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
