# ADR: Astra Factory 2.0 — opportunity-driven, continuously productive, quality-gated VPS architecture

**Date:** 2026-10-14  
**Status:** Proposed architecture ONLY (not approved for production cutover)  
**Repository:** Saeit; isolated feature branch; no executable release in this ADR  
**Owner goal:** Replace low-value repetitive ZIP assembly with a continuously operating, market-informed producer of genuinely useful, independently verifiable digital goods; manufacture BEFORE orders, with no artificial production or revenue claims.

## 0. Executive decision (فارسی)

معماری اصلی آسترا حفظ و تقویت می‌شود؛ یک مسترایجنت مستقل یا دیتابیس موازی برای سایت‌ها ایجاد نمی‌شود. سه ایراد گزارش‌شده باید در طراحی حل شود: (۱) کیفیت و ارزش فروش بسیار پایین؛ (۲) تکرار دو بسته ثابت به‌جای تولید مستمرِ خروجی جدید؛ (۳) انتخاب محصولات صرفاً بر اساس شناسه رکورد و بدون سنجش واقعی تقاضا. مسیر جدید «شاهد بازار → ارزیابی اقتصادی → مشخصات محصول → ساخت تخصصی → آزمون واقعی → بهبود → انتشار مجاز → بازخورد فروش» است. کارِ پژوهش، ساخت و QA بدون سفارش مشتری ادامه می‌یابد؛ فروش، اتصال درگاه، هزینه خارجی و انتشار، گیت جدا دارند. هیچ بخش زنده تا احراز معیارهای پذیرش تغییر نمی‌کند.

## 1. Verified baseline / reasons for architecture change

This ADR is grounded in:
- docs/ASTRA_FACTORY_VPS_UPGRADE_20261014.md and original Astra archive audit (SHA-256 2333e35dfd29efd807cd98d31388d8a454fe9c9f030d077d7b1f1f2235f546a5).
- scripts/factory_autonomous_portfolio.py selects existing inactive factory-managed products by ID; it does not rank new opportunities by real evidence or customer need.
- scripts/factory_vps_product_cycle.py obtains dossiers but then chooses sorted(factory_product_maker.RECIPES) independent of their contents; 2 hard-coded recipes in scripts/factory_product_maker.py.
- deploy/install_autonomous_factory_products.sh sets an hourly VPS cron; a recurring unchanged build/check is NOT proof of a newly produced product.
- GitHub Action 38569508844: isolated research DB sample has 104 FactoryRun (95 blocked), 145 AgentTask (95 blocked), 9 inactive candidate products, 14 Evidence and 14 Findings; this is a point-in-time snapshot, not a current counter.
- GitHub Action 38585104797: another read-only VPS DB/runtime inspection found 209 Product rows and 0 orders/payment intents, 0 new Product rows in preceding 24 hours; the distinct DB contexts must not be added together.
- GitHub Action 38585641893: 25 candidates processed, 2 private QA packages and 0 publishable products, no claim of paid sales.
- GitHub Action 38580488942: Astra isolated test passed schema migration 0049/queue tests, but 1 test hypothesis remained waiting_for_evidence and 0 discovery snapshots were created. This is not proof of a verified market opportunity or operational Stage 5.
- GitHub issue #42 remains open for proving genuine provider-sourced evidence and Stage 4→5; issue #41 remains the production cutover gate.

**Interpretation:** existing QA establishes package integrity and unit test pass, NOT product-market fit, depth, originality, practical completeness, scientific trustworthiness, licensed distributability or commercial readiness. A schedule can be alive with no productive progress.

## 2. Architectural principles / explicit non-goals

1. **Retain one canonical owner/Master Agent control plane.** Existing core/approval.py, tool gateway, agent registry, risk rules, task runtime and financial_core remain the authority; VPS is an isolated execution/data plane. Do not run a competing unrestricted autonomous controller.
2. **Astra is the foundation, not a rewrite target.** Extend the original Hypotheses → FactoryQueueItem(discovery) → DiscoverySnapshot → Intake → FactoryQueueItem(run) → Existing AgentTask/ToolGateway/Pipeline. Migration 0049 is NOT applied to live factory by this ADR; inspect and merge differences from current VPS code before any cutover.
3. **Opportunity-led, supply-led.** Production NEVER waits for orders. Each build must nevertheless correspond to a qualified product brief with customer problem, evidence and target acceptance tests. Unvalidated hypotheses can be researched; they cannot be auto-declared sale-ready.
4. **Value over quantity.** Count only distinct, versioned, usable, QA-evidenced outputs as newly built products; ignore unchanged rebuilds/ZIP repacks/dossiers for manufacturing KPIs.
5. **Bounded autonomy.** Local scheduling, research from permitted public sources, QA and private drafts can run on an approved low-cost budget. New paid API spend, publications, financial transactions, account changes, legal obligations and safety/policy elevations follow existing explicit owner approval/allowlists.
6. **Fail closed; protect live sites.** Site Django/cPanel databases, URLs, running services, user data, workflows and current delivery remain unchanged until independent QA, backup, rollback and single-writer cutover verification. No bulk resume of the 95 blocked tasks.
7. **Truthful evidence.** No invented market statistics, references, former prices, buyer interest, customer feedback, completed sales, rights claims or successful settlement.

## 3. Target architecture (one system, three independent lanes)

~~~text
                           [Owner / existing Master Agent]
                      [Policy, approvals, budgets, kill switch]
                                         |
                          existing AgentTask/ToolGateway
                                         |
                         [VPS Factory Orchestrator + durable queue]
                                         |
                  +----------------------+-----------------------+
                  |                      |                       |
       A. OPPORTUNITY LANE      B. BUILD / QA LANE      C. COMMERCE LANE
       Signals & demand          ProductBrief version      Private distribution
       Source provenance         Specialized recipe        Existing cPanel inbox
       Legal/market checks       Build / tests / revision  Approved store adapter
       Economic rank             QA evidence and rubric    Checkout/delivery gates
       Qualified opportunities   Release candidate        Proven settlement only
                  |                      |                       |
                  +---------------[Event/State ledger]-----------+
                                         |
                     [Health, costs, retries, customer outcomes]
                                         |
                          [Measured feedback / retriage]
~~~

Control plane: existing Django owner/control API; not exposed as an open terminal for agents.  
Execution plane: single isolated VPS worker/scheduler, source/domain adapters, per-task workspaces and artifact store; no shared write access to websites.  
Evidence plane: private append-only research snapshots and immutable hashes with URLs, retrieval time, source identity and evidence freshness.  
Commerce plane: existing audited private SSH handoff then host-specific storefront gate, financial_core reconciliation and verified revenue lifecycle, never an implicit side effect of build success.

## 4. Canonical durable state machine

Research path:
- HYPOTHESIS → SOURCING → WAITING_FOR_EVIDENCE | QUALIFIED | REJECTED.
- Persist reason, evidence requirements, next-check timestamp and research budget for WAITING_FOR_EVIDENCE.
- QUALIFIED requires provenance, eligibility, minimal corroboration and explicit uncertainty flags; 200 Astra seed questions remain unverified until independently proven.

Manufacture path:
- QUALIFIED → PRODUCT_BRIEF_READY → BUILD_QUEUED → BUILDING → QA_PENDING → REWORK | RELEASE_CANDIDATE | REJECTED.
- QA failure creates a bounded actionable rework task, not a passing product.
- Every manufactured artifact is linked to exactly one ProductBrief, product/version, run, recipe/toolchain digest and evidence snapshot set.
- A digest-matched rebuild returns UNCHANGED, not NEW_PRODUCT, and consumes no paid tool calls.

Distribution path:
- RELEASE_CANDIDATE → OWNER_REVIEW (if required) → RELEASE_AUTHORIZED → PRIVATE_DELIVERED → STORE_VERIFIED → PUBLISHED → OUTCOME_MEASURED.
- Checkout, settlement, refunds and attribution are separate existing downstream workflows. No PUBLISHED status from receipt-copy alone; no VERIFIED_REVENUE without evidence of reconciled settlement.

Side states: POLICY_BLOCKED, RETRY_SCHEDULED, RESOURCE_WAIT, TEMPORARILY_UNAVAILABLE, FAILED_PERMANENTLY. Retries have finite exponential backoff and per-task leases, no general-purpose permission bypass.

## 5. Market selection engine — design, not fabricated demand

### A. Candidate sourcing
- Sources: newly observed buyer needs, consented/anonymized feedback where permitted, real competitor feature/pricing pages, official industry data, documented workflow gaps, independent research, existing business expertise and underserved tool niches.
- First specialized vertical: agricultural economics, farm cost optimization, water-use budgeting; expand only when the generator and validators can prove competence. Also support software/automation, education and B2B tool categories after separate QA capability registration.
- Each candidate: problem statement, buyer persona, scenario, expected outcome, competing alternatives, source URLs/hashes/dates, legal/market eligibility, distribution route, constraints, estimated engineering effort and evidence confidence.
- Source fetcher: HTTPS allowlist/policies, SSRF and redirect protections, bounded bytes/time, dedup, stable provenance and retention; search snippets alone never count as proof of buying intent.
- Corroboration policy: normally at least two independent evidence sources for a positive demand claim; if unavailable label NOT_VERIFIED and hold in research. Do not pretend 2 links guarantee a market.

### B. Knock-out / eligibility gates (before numeric ranking)
- User problem is specific and testable, product is lawful and rights/licensing are viable.
- A permitted sales channel and feasible fulfillment/support path exist.
- Can be built honestly and checked by supported technical/domain validators.
- Source/market claims are not solely self-generated or hallucinated.
- No prohibited data acquisition, irresponsible regulated claims or unapproved external monetary commitments.
- Missing crucial evidence => research queue, NOT automatic product selection.

### C. Evidence-sensitive priority model, provisional weights /100
- Observed problem intensity and relevance: 20.
- Independent demand signals and willingness-to-pay evidence: 20.
- Concrete superiority over available alternatives: 15.
- Feasibility with current tools, time and VPS resources: 15.
- Verifiable economic margin and support burden: 15.
- Legal, distribution and payment feasibility: 10.
- Strategic knowledge reuse / learning benefit: 5.
Record score + uncertainty interval + evidence references + scoring version + explicit reviewer notes. No score may be described as predictive sales probability. An evidence confidence floor and knockout gates override arithmetic scores.
Implement diversify/explore: allocate **candidate research** across exploitation/exploration categories without declaring unverified candidates eligible for product manufacturing. Do not choose simply by Product.id.
Re-rank on significant new evidence or stale research TTL rather than on every heartbeat.

## 6. Production engine — replace hard-coded recipe selection

Each qualified candidate yields an immutable **ProductBrief**:
- buyer/problem and paid/free proposition; outcome metrics and functional user journeys;
- modality/industry and specialist capability requirements;
- feature acceptance cases, domain constraints, sample datasets provenance, reference solution and failure conditions;
- explicit market differentiation, boundaries, licensing/rights and required support/docs;
- effort/cost/resource ceiling, deliverable formats, test fixtures, review gates.

The planner maps brief.capabilities to versioned registered builders:
- functional software/calculator/API + runnable integration tests;
- research-backed datasets and worked economic decision templates;
- substantive original technical learning packs/manuals with citation/accuracy and instructional checks;
- service/automation assets with demonstrable workflows and operator documentation.
Unsupported types remain NEEDS_BUILDER instead of silently reusing one of two calculators.
Builders are pluggable with a strict interface: plan(brief), build(brief,workspace), test(artifact,brief), evidence(artifact), estimate_cost(). All execution is sandboxed and resource-limited. A builder is not a valid manufacturer until it proves at least one non-trivial reference product.

Use staged prototypes/feedback: Brief → MVP → domain verification → comparative tests → full deliverable → independent QA. Prefer a smaller genuinely useful asset over hundreds of pages or files filled without verified content.

## 7. Multi-gate product quality framework

**Hard failures** (any => REWORK/BLOCK even if total score high):
- missing feature/invalid outputs, severe security risks, copyright/license rights unverified, fabricated sources/test results, substantial factual errors, inaccessible core flows, broken package/install, misleading promotional claims.
- Domain-sensitive claims (farm prices, agronomic outcomes, finance) require labeled assumptions, reproducible calculations, credible references and known limits.
- Provenance and reproducible checks for all non-obvious claims.

**Rubric; all dimensions 0..100, weighted result:**
- 25% functional correctness, end-to-end acceptance and reproducibility;
- 20% depth, evidence quality and domain accuracy;
- 20% usefulness relative to validated customer problem/alternatives;
- 15% completeness: workflows, examples, docs, maintenance, localization where promised;
- 10% usability/accessibility and user onboarding;
- 10% reliability, security, licensing and maintenance/support readiness.
Suggested RELEASE_CANDIDATE threshold: >=90/100 AND no hard failures AND each critical dimension >=80 AND an independent review/validation appropriate to the modality. This score is a design gate, not proof of market demand or guaranteed sales.
Record individual tests, test datasets, failed cases, reviewer provenance, source hashes, model/tool versions, QA timestamps and issue list. Do not auto-award 100 for unittest pass. No sale listing before existing publication gate.

**Quality feedback:** first-pass yield, defect escape rate, revision attempts, field errors, support burden, refund reasons and independently verified usage; measured profitability only after actual settlement. Kill low-quality product lines rather than maximizing ZIP count.

## 8. Continuous, event-driven production and cost policy

The existing hourly cron is merely a heartbeat; it must not be called continuous manufacturing on its own.
- Durable queues hold verified work with priorities, owner/budget scopes, due dates and idempotency keys. Maintain a backlog target of 2–4 QUALIFIED, independently verifiable briefs when actual evidence permits; a shortage triggers research, not fictitious products.
- Scheduler wakes on bounded cadence (initial design: five-minute local reconcile/watchdog, and events for validated evidence/QA completion). It dispatches only READY work; logs NO_ELIGIBLE_WORK without claiming production. Reconcile does not consume LLM tokens.
- 1 CPU-heavy build at a time on the observed ~3 vCPU/~4 GiB VPS; 1–2 small research/QA tasks may run if actual memory limits permit. Queue ComfyUI or other heavy tasks separately, never co-run them under memory pressure.
- Bounded timeouts, memory/disk quotas, crash recovery, leases with fencing tokens, exact-once-effects via idempotency (at-least-once queue deliveries), atomic artifact publication to private staging and watchdog checks.
- Separate cheap local research/health from expensive tool invocation. Paid model use is DISABLED by default; an owner-approved cap, purpose and per-job ledger are mandatory before enabling, with cache/dedup and zero-call heartbeat. No claim that a cheap VPS can locally generate all modalities at high quality.
- SLA **target**, not observation: worker heartbeat freshness <=10 minutes; 24-hour soak without orphan/duplicate jobs; any qualified runnable brief progresses or reports a named explicit blocking reason within one hour. Fresh product count is only from distinct accepted SHA/version.
- If pipeline empty/blocked, alert and surface actionable cause, not rebuild two unchanged ZIPs.

## 9. Data model and interfaces (additive only; source-of-truth mapping required)

Do not introduce a second set of editable website Product/Order records. Map to existing Astra FactoryQueueItem, DiscoverySnapshot, FactoryRun, AgentTask, ResearchProject/Evidence and Product where their semantics fit. Proposed additional PRIVATE records, subject to schema diff review:
- OpportunityAssessment(opportunity_id, evidence_digests, scoring_version, demand_confidence, eligibility, blocker_codes).
- ProductBrief(brief_id, version, opportunity_id, owner_scope, output_type, acceptance_specs, build_budget, source_digests).
- BuildAttempt(attempt_id, brief_version, task_id, recipe_version, workspace_ref, result_digest, resource_usage, failure_code, lease_fence).
- QualityReport(product_version, rubric_version, individual scores, mandatory_checks, evidence_links, reviewer_id, defects, final_decision).
- ReleaseDecision(product_version, exact scope/store, owner_grant_ref, rights/license, publication_gate, rollback_ref, immutable audit).
- OutcomeEvent(product_version, source_ref, measured_at, verified_paid_or_nonpaid_metric, provenance, reconciliation_ref).

Stable event contract: event_id, schema_version, occurred_at_utc, aggregate_id, causation_id, idempotency_key, actor/capability, evidence_digest, minimal non-secret payload. Transactional outbox/lease fencing for reliable handoff. Raw secrets do not enter reports or GitHub artifacts. Use explicit cross-host acknowledgement receipts; never confuse private delivery with live publication.

## 10. Reliability, observability and stop controls

Separate dashboard states:
- PROCESS_ALIVE; SCHEDULER_READY; QUALIFIED_BACKLOG; RESEARCH_WAIT; BUILD_PROGRESS; QA_READY; RELEASE_BLOCKED; STORE_DELIVERED; PUBLIC_LISTED; REAL_PAID_ORDERS; SETTLED_REVENUE.
- Metrics: verified independent source count, candidates rejected/qualified, briefs ready, unique product versions completed, QA first-pass %, median lead time, revision rate, per-product cost, resource pressure, stalled leases, number waiting due to evidence, verified conversion and net profit when real data exists.
- Auto-recovery only of expired/known worker leases, NOT policy/owner/unknown historical blocked tasks.
- Circuit breakers on provider errors, repeating identical hypotheses, cost overruns, CPU/RAM pressure or QA defect spikes.
- Pause/kill commands scoped to a product/job/worker with audit; keep websites and private store independently healthy.
- Test artifact/provenance hashes and rollback restoration before declaring an install complete.

## 11. Deployment boundary and acceptance plan (not executed by this ADR)

**Phase A — Architecture contract (this PR):** review and accept KPI definitions, capabilities, score gates, privacy/security restrictions; no code release.

**Phase B — Read-only mapped audit:** inventory deployed VPS source vs original Astra archive vs main branch; schema diff and read-only queue/cron/worker/DB report; identify every blocked reason; preserve factory/site split. Must resolve issue #42 provider limitations honestly.

**Phase C — Isolated implementation:** introduce pluggable builders, evidence-driven selector, ProductBrief/QA schema and event log in a disposable copied runtime. Keep all website production databases untouched. Add deterministic tests for selection bias, true new product count, insufficient evidence, no source fabrication, flaky worker/leases, quality block, store owner gate, and no-paid-calls.

**Phase D — Independent product proof:** build at least three DISTINCT non-trivial reference products across at least two builder categories, using genuinely qualified briefs and independent domain QA; record all artifacts, feature tests, mistakes and corrected versions; at least one full user-facing walkthrough. The number is an acceptance target, not a reported achievement. No publication/paid sales.

**Phase E — 24-hour soak / Stage 4→5:** exercise actual bounded source retrieval, evidence snapshots, research→intake→build→QA through isolated state, cron/watchdog recovery and fault injection. Zero duplicate manufacturing, zero payment/publication leakage, stable memory/disk, complete audit history. No fake clock-loop throughput.

**Phase F — Guarded private VPS cutover (separate explicit permission):** backup consistent private SQLite and exact code, verify migration 0048→0049 and compatibility, exclusive single-writer lock and supervisor, canary + bounded real research tick, verified rollback. Do not replace entire live Django files or stop existing working factory until go/no-go is measurable.

**Phase G — Product release (separate explicit permission):** private inbox → accurate market/rights/QA review → owner-scoped publication → independently verified web delivery + checkout + reconciliation gates. No blanket authorization, invented 90% old prices, or real-money switch from this document.

## 12. Architecture acceptance tests / objective completion criteria

- New-idea independence: with 3 qualified briefs and only 2 installed starter recipes, the engine does NOT pretend to manufacture the third; it records NEEDS_BUILDER, and a newly installed suitable builder produces a genuinely distinct tested artifact.
- Market selection: chosen work differs when credible external demand/feasibility evidence changes; zero records promoted from mere Product.id ordering or unverified Astra hypotheses.
- New output accounting: running unchanged inputs ten times yields 0 NEW_PRODUCT after first accepted version, even if tests/cron run ten times.
- Quality block: broken calculations, invented research references, missing license, unusable install or unresolved major defects force REWORK/BLOCK despite score >=90.
- Continuity: watchdog/crash injection cannot duplicate effects or lose work; one ready task advances after restart, without an operator and without exceeding cost or resource caps.
- Isolation: factory build cannot mutate real cPanel database, website files, live payment settings, deployments or treasury accounts.
- Release: private received file is not marked PUBLISHED; payment not VERIFIED_REVENUE until independently reconciled.
- Honest run status: if no demand evidence, worker reports WAITING_FOR_EVIDENCE and 0 new products, never fake autonomous output.
- Regression: existing 40 Astra isolated queue tests and all relevant modern security tests must pass in the same disposable integration runtime; investigate any pre-existing failures rather than waive them.

## 13. Implementation mapping and decisions still needed

Existing code to preserve/adapt:
- core/approval.py, core/agent_registry.py, core/queue_dispatcher.py, core/production_gate.py, core/research_runtime.py, core/observability.py and financial_core remain canonical (versions/deployment must be inspected).
- Astra archive's durable FactoryQueueItem/DiscoverySnapshot and existing AgentTask are the foundation.
- scripts/factory_autonomous_portfolio.py becomes a bridge for legacy candidate dossier reads; remove Product.id as a selection heuristic only after passing new engine tests.
- scripts/factory_vps_product_cycle.py stops selecting sorted(RECIPES) unconditionally; it dispatches an allowed builder chosen from qualified ProductBrief and registered capabilities. Keep old two recipes as private reference regression fixtures, NOT promoted products.
- scripts/factory_product_maker.py becomes one of many versioned builders or is wrapped by a secure builder adapter.
- scripts/factory_store_sender.py remains PRIVATE-delivery-only; source and storefront release remain separate.
- deploy/install_autonomous_factory_products.sh and existing Actions remain unchanged until independent green acceptance and rollback plan.

Design choices to validate before implementation: concrete evidence data sources/platform permissions; modality-specific trusted validators; true qualified backlog; target storefront jurisdiction/licensing, safe spending/compute budgets, and actual VPS headroom. No speculative sales or guaranteed 90+ score.

**Status at authoring:** ARCHITECTURE PROPOSAL ONLY; none of phases B–G or the new selection/build/QA engine are claimed as implemented. No live VPS or cPanel changes are part of this change.
