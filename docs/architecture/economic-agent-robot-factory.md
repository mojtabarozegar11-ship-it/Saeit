# Economic Agent & Robot Factory

## Mission
This is a capability of the existing site Master Agent, not a second master system. Its mission is to discover lawful revenue opportunities, create specialized agents and execution robots, validate them, deploy them, measure real outcomes, and continuously improve or retire them.

## Control plane
Owner -> Site Master Agent -> Opportunity Engine/Portfolio -> Agent & Robot Factory -> Specialized Teams -> Execution Robots -> QA/Security Gate -> Financial Core -> Settlement/Reconciliation -> Verified Revenue Ledger -> KPI/Evolution feedback -> Master Agent.

## Canonical revenue lifecycle
Every revenue workflow uses one state machine:

Opportunity -> Qualified -> Approved -> Executing -> Delivered -> Invoiced -> Paid -> Settled -> Verified Revenue.

`Paid`, an order, an invoice, a lead, a dashboard number, or an agent claim is not verified revenue. `Verified Revenue` requires externally evidenced settlement plus successful reconciliation. The canonical implementation is `core/revenue_lifecycle.py`.

## Factory lifecycle
1. Discover a lawful revenue opportunity.
2. Qualify eligibility: jurisdiction, provider/platform terms, KYC/AML where applicable, settlement route, operational capability and owner policy.
3. Define objective, tools, permissions, budget, risk class and measurable KPI.
4. Generate an AgentSpec (reasoning/coordination) and one or more RobotSpecs (execution).
5. Run sandbox/demo/canary validation.
6. Pass policy, security, financial-risk, QA and regression gates.
7. Deploy with least privilege, bounded budget, idempotency and a kill switch.
8. Observe gross revenue, collected cash, settlement, cost, net profit, ROI, errors, refunds/disputes and risk events.
9. Reconcile external evidence with the internal ledger.
10. Promote/clone/improve profitable teams; repair, pause or retire failing teams.

## Core records
Every generated unit must have: immutable ID, version, parent opportunity, owner, mission, allowed tools, denied actions, credentials references (never raw secrets), budget, risk limits, KPI targets, health, revenue, costs, profit, audit events, deployment status and rollback version.

## Agent vs Robot
Agents analyze, plan, coordinate and propose actions. Robots execute concrete operations through approved connectors/APIs/bridges. A production team is incomplete unless it has an execution path and measurable outcome.

## Autonomy classes
A0 Observe only.
A1 Draft/recommend.
A2 Execute reversible non-financial operations automatically.
A3 Execute bounded demo/sandbox financial operations automatically.
A4 Execute bounded real operations only after explicit owner enablement and within pre-approved limits.
A5 Reserved: withdrawals, external transfers, ownership/security changes and limit escalation always require owner approval.

## Financial Core
The existing `financial_core/` remains the central treasury/accounting boundary and source of truth. It provides ledger, assets, custody, deposits/withdrawals, execution, reconciliation, risk, limits, readiness, KPI and agent bridge capabilities. The revenue lifecycle does not replace it; it supplies the shared commercial state contract above it.

External providers are adapters, never the core. Removing an adapter must not destroy internal accounting, history or orchestration.

## Existing project mapping
- Site Master Agent/orchestration: `core/orchestrator.py`, `core/task_runtime.py`, `core/queue_dispatcher.py`, `core/worker_runner.py`.
- Governance: `core/approval.py`, `core/tool_gateway.py`, `core/production_gate.py`, `core/health_gate.py`.
- Audit/observability: `core/observability.py` plus task/approval audit records.
- Economic intelligence: `core/economic_master_agent.py` remains an economic research/reporting worker; it is not a second site master.
- Revenue/payment records already present: Order/OrderItem, PaymentIntent, LedgerEntry and PaymentWebhookEvent migrations/tests.
- Financial execution boundary: `financial_core/`.
- Company revenue surfaces: services, store/products, education, trade correspondence and other approved channels.
- Android admin remains a control/reporting client of the same Master Agent; it must not become an independent execution authority.

## Revenue portfolio
The factory may explore lawful and permitted revenue channels including company products/services, digital products, subscriptions, commissions, affiliate programs, marketplaces, automation/AI services, content monetization and approved financial-market activity. Each channel must expose measurable cash/revenue/cost/risk events to the Financial Core and pass eligibility checks before activation.

## Trading rollout
Real accounts remain execution-locked by default. Required progression: market data -> strategy -> risk gate -> demo execution -> reconciliation -> measured demo P&L -> owner acceptance -> bounded real enablement. No profit guarantee is assumed.

## Evolution engine
Fitness is based on verified revenue, net profit, conversion, execution cost, failure rate, refunds/disputes, settlement time, risk events and human intervention. Lifecycle: Create -> Canary -> Measure -> Promote / Repair / Kill -> Clone winner -> Retest. Agent count and task count are not success metrics.

## Definition of operational
A unit is not Active merely because a process is running. Active means it can receive a task, execute through a real or demo connector as appropriate, persist its result, emit audit evidence, update financial/KPI metrics, recover from failure and report health to the Master Agent. A revenue unit additionally must be able to progress through the canonical revenue lifecycle and provide settlement evidence before revenue is marked verified.

## Master KPIs
Verified revenue; cash collected; gross revenue; operating cost; net profit; assets; liabilities; trading P&L; ROI; drawdown/risk exposure; conversion; refund/dispute rate; settlement time; revenue and profit per agent/robot/team; failure rate; time-to-recovery; human-intervention rate.

## Rollout priority
Do not optimize for maximum robot count. First prove one lawful end-to-end revenue path from opportunity to externally evidenced settlement and Verified Revenue. Then enable the factory/evolution loop and expand to additional channels.

## Non-negotiable safeguards
No secrets in source control. Least privilege. Idempotent execution. Full audit trail. Kill switch per robot/team/connector. Budget and loss limits. Reconciliation before financial results are treated as final. Owner approval for A5 actions and any escalation beyond pre-approved real-money limits. No system component may self-report revenue as verified without settlement evidence.
