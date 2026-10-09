# ADR: Evidence-Based Wealth Mission and Operational Autonomy

- **Status:** Accepted owner directive
- **Scope:** Architecture boundary only; this ADR does not implement economic ledgers, sales operations, treasury automation, or a Wealth Engine.

## Decision

The Factory's long-term economic mission is **CREATE REAL WEALTH**: create and grow lawful, productive assets, products, and businesses with measurable economic value for the company. Product count, token supply, self-assigned prices, fabricated transactions or liquidity, wash trading, self-dealing, fake users, and vanity metrics are not wealth evidence.

Economic evidence must distinguish collected revenue, costs, refunds and fees, gross and net profit, and cash flow from estimates and unrealized asset-value assessments. Any material KPI must retain its source, timestamp, currency, calculation method, and confidence where applicable. Estimates must never be represented as collected cash or realized value.

The opportunity pipeline should **validate cheaply before building expensively**: research and evidence, reproducible opportunity scoring, low-cost validation, small MVP, real market test, then improve, scale, maintain, or stop based on measured results. No single economic metric is sufficient to select an opportunity.

The existing Factory remains the sole execution system. Economic strategy, opportunity comparison, and later feedback from market outcomes extend its existing Master, Research, Evidence, Task, and Release flows; they do not create a parallel Factory or runtime. A capability lane may be selected only when its required executor, independent verification, security, localization, and eligibility controls exist.

The long-term operating objective is zero human labor for normal Factory operations. Given an owner-defined goal, policy, and boundaries, the Factory should schedule, resume, recover, replan, verify, monitor, and operate supported product lifecycles without ChatGPT, Astra, Luna, or a human manually advancing tasks or producing stage outputs. This autonomy remains subject to owner-controlled capital, governance, security, secrets, legal commitments, regulated activity, and destructive or irreversible actions. Required human approvals remain explicit policy gates.

## Consequences

Core Factory work must first prove autonomous execution through launch-candidate preparation and recovery tests. Wealth accounting, portfolio allocation, sales operations, and economic feedback are later extensions and must use auditable evidence and the existing Factory governance boundaries. No real spending, payments, token issuance, financial activation, or Wealth Engine is authorized by this ADR.
