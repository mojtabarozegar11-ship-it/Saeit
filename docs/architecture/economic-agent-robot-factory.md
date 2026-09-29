# Economic Agent & Robot Factory

## Mission
This is a capability of the existing site Master Agent, not a second master system. Its mission is to discover lawful revenue opportunities, create specialized agents and execution robots, validate them, deploy them, measure real outcomes, and continuously improve or retire them.

## Control plane
Owner -> Site Master Agent -> Opportunity Portfolio -> Agent/Robot Factory -> Specialized Teams -> Execution Robots -> Financial Core -> Ledger/Audit -> KPI feedback -> Master Agent.

## Factory lifecycle
1. Discover a lawful revenue opportunity.
2. Define objective, tools, permissions, budget, risk class and measurable KPI.
3. Generate an AgentSpec (reasoning/coordination) and one or more RobotSpecs (execution).
4. Run sandbox/demo validation.
5. Pass policy, security, financial-risk and regression gates.
6. Deploy with least privilege and bounded budget.
7. Observe revenue, cost, net profit, cash collected, ROI, errors and risk events.
8. Improve/replicate profitable teams; pause or retire failing teams.

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
The Financial Core is the central treasury and source of truth. It must provide multi-asset double-entry ledger, account/wallet registry, balances, receivables/payables, revenue/cost attribution, P&L, cash collection, reconciliation, risk limits, approval records and immutable audit history.

External providers are adapters, never the core. LiteFinance/cTrader/MT5 may be used initially for demo and approved trading connectivity. Removing an adapter must not destroy internal accounting, history or orchestration.

## Revenue portfolio
The factory may explore lawful and permitted revenue channels including company products/services, digital products, subscriptions, commissions, affiliate programs, marketplaces, automation/AI services, content monetization and approved financial-market activity. Each channel must expose measurable cash/revenue/cost/risk events to the Financial Core.

## Trading rollout
Real accounts remain execution-locked by default. Required progression: market data -> strategy -> risk gate -> demo execution -> reconciliation -> measured demo P&L -> owner acceptance -> bounded real enablement. No profit guarantee is assumed.

## Definition of operational
A unit is not Active merely because a process is running. Active means it can receive a task, execute through a real or demo connector as appropriate, persist its result, emit audit evidence, update financial/KPI metrics, recover from failure and report health to the Master Agent.

## Master KPIs
Cash collected; gross revenue; operating cost; net profit; assets; liabilities; trading P&L; ROI; drawdown/risk exposure; revenue and profit per agent/robot/team; failure rate; time-to-recovery.

## Non-negotiable safeguards
No secrets in source control. Least privilege. Idempotent execution. Full audit trail. Kill switch per robot/team/connector. Budget and loss limits. Reconciliation before financial results are treated as final. Owner approval for A5 actions and any escalation beyond pre-approved real-money limits.
