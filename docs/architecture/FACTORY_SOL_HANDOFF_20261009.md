# Zomorod Factory — root-cause investigation and SOL implementation handoff
Date: 2026-10-09
Status: architecture and code diagnosis completed; server repair NOT performed or verified.
Repository: mojtabarozegar11-ship-it/Saeit
Integration branch: factory/integration-control-bridge-20261005
PR #32: OPEN, DO NOT MERGE.
Inspected initial commit: fd98121899ecee688bfcb025c73b1eeb4091356a
Rechecked relevant files at current commit: 3802cd29672f7f68cb718e978a11fccf47559546.
This document branch contains architecture only. Implementation belongs to SOL.

## 1. Findings and limits
No authenticated runtime logs, deployed SHA, active provider configuration, or live DB rows were obtained in this investigation. Consequently the immediate cause of the reported stage 4 -> 5 failure is not yet proven. Map numbered stages to actual action_type/state in the deployed runtime before changing anything. Do not confuse a later economic-validation failure with an earlier research-fetch failure.

Verified code defects/limitations:
- core/self_hosted_research_provider.py: one discovery endpoint (Brave), no independent discovery fallback. Previous Bing reports do not describe this inspected code; verify deployed revision.
- _NoRedirect rejects every redirect although the runtime accepts a configurable redirect budget. PDF content is unsupported. These can discard legitimate sources, but their incidence in the live failure is unknown.
- Provider emits economic_factors={} for every source. core/factory_economics.py consumes those factors, requires nine commercial factors and blocks after two insufficient research attempts. Collecting additional unannotated pages cannot repair that contract.
- core/factory_agent_runtime.py requires a factor's numeric value and claim to occur literally in the snapshot; this conflates source observations (price, demand, costs) with derived 0–100 ratings. A coincidentally matching number does not substantiate an assessment.
- research_plan and provider invocation cap each call at six results. There is no demonstrated cumulative 100-source acquisition workflow in this path.
- factory_staging_tick.py selects oldest active runs and reports advanced_runs=len(runs), which counts selected runs rather than confirmed transitions. Repeated oldest failures can starve later eligible work.
- _safe_research_url checks literal IPs and hostname syntax, not DNS resolution/connected peer addresses. Preserve security while adding redirect handling; do not simply remove URL checks.
- A single returned malformed record currently can abort batch validation. Distinguish record quarantine from fatal authorization/security failures.

Reproduction performed locally:
Executed the inspected pure scoring/validation functions with two synthetic source records matching the provider's empty-factor shape.
score=None; coverage=0.0; attempt 1=NEEDS_MORE_EVIDENCE; attempt 2=BLOCKED.
This is a contract regression reproduction, NOT live evidence acquisition, a Django integration test, or proof of stage advancement.

## 2. First SOL operation: one bounded diagnostic
Use existing authenticated GitHub/SSH deployment route if available; no Remote Desktop Commander consumption. Do not assume credentials or successful SSH.
Read deployed SHA, SAEIT_ENV, provider class name (no secrets), one blocked run/task ID, its exact stage/action, last error chain, and relevant logs.
Trace that same run through discovery -> fetch -> extraction -> validation -> DB persistence -> transition.
Emit structured reason codes: DNS_FAILURE, CONNECT_TIMEOUT, TLS_FAILURE, HTTP_403, HTTP_429, REDIRECT_REJECTED, UNSAFE_ADDRESS, UNSUPPORTED_CONTENT, EMPTY_TEXT, IRRELEVANT, DUPLICATE, INVALID_PROVENANCE, DB_FAILURE, TRANSITION_CONFLICT.
Record durations, provider, sanitized URL, HTTP status and counts. Never log credentials.
If runtime access is unavailable, report the precise missing capability and keep deployment/runtime verification marked pending. A source code review cannot prove server connectivity.

## 3. Durable evidence architecture
Extend the current Django runtime; no wholesale rewrite or mandatory paid API.

Discovery: query planner + source registry + replaceable discovery adapters + direct known-source retrieval. Prioritize independently published relevant sources; an engine's failure must not disable all retrieval. No CAPTCHA/access-control bypass.
Transport: DNS and IPv4/IPv6 checks, public-address allow policy, connected-peer validation/DNS pinning with correct TLS SNI, redirect revalidation per hop, default <=3 redirects, HTTPS preferred. Run extraction without server secrets or outbound access.
Extraction: HTML/text and bounded PDF extraction, page/paragraph locators, MIME/magic validation, byte/time/page limits. OCR is optional and budgeted.
Evidence: preserve raw/content hashes, normalized snapshot, exact passage locator, canonical URL, publisher identity, published/retrieved timestamps, extractor version, product/run/version and relevance decision. Content is untrusted data, never agent instructions.
Facts: attach exact quoted observations, units, currency, geography, date, uncertainty and evidence IDs. Unknown remains unknown.
Assessments: separate versioned rules compute ratings from facts; store rule version, inputs, assumptions, calculation and provenance. Do not require derived scores to appear in external text. Listed competitor price is not proof of customer willingness to pay; projected revenue is not collected revenue.
Persistence: commit valid source snapshots incrementally in short transactions; network work occurs outside DB locks. Quarantine invalid records with reasons. Preserve prior valid results after timeouts.
Deduplication: canonical URL plus content hash and actual publisher grouping; multiple pages/subdomains are not automatically independent publishers.
Progress: resumable cursor, next_attempt_at, per-provider circuit breaker, capped exponential retry and finite per-run budget. Authorization/security failures must remain fail-closed.
Capacity: support up to 100 distinct relevant sources cumulatively, in small batches. The gate uses relevant evidence sufficiency, not an arbitrary requirement to fetch exactly 100.
Scheduling: fair eligible-work selection, limited concurrency (start with one research worker), leases with expiry and durable checkpoints. Backpressure intake when the research queue is saturated.
Transitions: one versioned gate policy keyed by action/state; row locking or compare-and-swap, unique task/effect key, and transactional transition/event creation. Replay must not duplicate evidence/products or fail solely because the prior attempt committed.
Counters: attempted, fetched, extracted, accepted, persisted, rejected_by_reason, actually_transitioned. Count success only after durable effects.

Suggested additions (adapt names to existing models):
ResearchAttempt; SourceSnapshot; EvidenceClaim; FactorAssessment; StageTransitionEvent; CapabilityDefinition; CapabilityEvaluation.
Reuse ResearchProject/ResearchSource/Evidence/Finding/FactoryRun/AgentTask where compatible. Add migrations only for missing durable fields/constraints.

## 4. Acceptance gate before expanding the factory
1. Identify and reproduce the actual live stage failure on one existing product.
2. Fetch real relevant content from at least two independent reachable publishers; store snapshots and provenance in DB.
3. Confirm the same run crosses the actual 4 -> 5 boundary automatically, with before/after state, task ID, evidence IDs, timestamps, SHA and transition event.
4. Separately verify downstream economic assessment from supported facts. A genuinely unsupported/unviable opportunity must remain pending or rejected; never force validation.
5. Restart/replay after partial persistence: no duplicate effects; prior evidence retained.
6. Exercise provider outage, timeout, valid redirect, private-address redirect, DNS rebinding defense, PDF budget overflow, duplicate and malformed record.
7. Verify scheduled execution and fair selection; report actual transition count.
8. Targeted regression tests first; existing required CI gates remain. No unrelated broad retesting.
9. Staging-only deployment, backup/checkpoint and rollback to prior SHA/schema-compatible configuration. Production /home/zomorod2/Saeit untouched.
10. Deliver sanitized proof bundle. No claim of permanent failure-free operation; durable recovery means bounded retries, diagnosis, checkpointing and monitored regression prevention.

## 5. Architecture of the twenty target capabilities
These are targets, not current capabilities. Keep moj_1ro_1 as the sole persistent orchestrator. Specialist roles are bounded jobs/tools under its control, not independent always-running masters.
Shared backbone: durable task DAG, evidence graph, artifact/version registry, experiment runner, capability registry, policy gateway, resource budget ledger, audit/metrics and release rollback.
Start as modular components in the existing application; split services only for measured isolation/load needs.

| # | Capability / module | Required proof of readiness |
|---|---|---|
| 1 | Invention / novelty workbench | Prior-art evidence, differentiation claims, tested prototype; no unsupported novelty guarantee |
| 2 | Scientific discovery / hypothesis lab | Explicit hypothesis, reproducible experiment, uncertainty, negative results and independent validation |
| 3 | Engineering / specification and build | Versioned requirements, build artifact, functional and performance tests |
| 4 | Technology production / transfer pipeline | Research-to-spec-to-tested-product traceability |
| 5 | Factory builder / template provisioner | Isolated child factory, quotas, manifest, smoke test and deletion/rollback |
| 6 | Self-development / capability backlog | Measured need, bounded change, evaluation and controlled release |
| 7 | Multi-agent coordination / job DAG | Typed inputs/outputs, scoped tools, bounded fan-out and replay-safe orchestration |
| 8 | Virtual laboratories / sandbox runner | Pinned environment, datasets, seeds, reproducibility; simulation limitations disclosed |
| 9 | AI model development / model registry | Licensed data lineage, baseline comparison, held-out evaluation and measured compute cost |
| 10 | Global economics / market research | Dated demand/price/cost evidence, scenario assumptions and uncertainty |
| 11 | Multi-market trade / localization and eligibility | Tested locales, market-specific eligibility and operational sales readiness |
| 12 | Future technology / horizon scanning | Primary research tracking, maturity classification and tested feasibility |
| 13 | Novel algorithms / benchmark workbench | Reproducible baselines, correctness and complexity/performance comparison |
| 14 | Resource management / budget scheduler | Hard CPU/RAM/disk/time/spend limits and cost per accepted artifact |
| 15 | Complex products / modular product builder | Interface contracts, integration/security/load tests and deployable artifacts |
| 16 | Intellectual property / provenance register | Authorship/license/ownership ledger and documented prior-art review; registration distinct from internal record |
| 17 | Quality / independent evaluation gate | Versioned tests, security/scientific/usability evaluations and traceable failures |
| 18 | Self-healing / recovery controller | Fault injection, bounded repairs, verified restoration and escalation reasons |
| 19 | Controlled evolution / release manager | Candidate-versus-baseline evaluation, canary limits and demonstrated rollback |
| 20 | Global ecosystem / factory portfolio | Isolated tenants/factories, cross-factory contracts, accounting and evidenced economics |

No automatic claim of scientific discovery, patentability, profit or global scale from generated text. GPU-heavy training and physical-world validation require explicit resource availability and independent validation.

## 6. Implementation order for SOL
P0: live diagnosis + research acquisition/persistence + truthful counters and stage mapping.
P1: observed-fact/derived-assessment separation; fix economic dead end without fabricated factors; resume/fair scheduling.
P2: shared capability registry, artifact lineage, resource caps, quality and recovery (7,14,17,18,19).
P3: market/localization + reproducible engineering/algorithm/product pipelines (3,4,10,11,13,15).
P4: scientific/AI/novelty/IP capabilities with real experiments and feasible budgets (1,2,8,9,12,16).
P5: factory templates, self-development and portfolio ecosystem (5,6,20).
Each package: implementation -> targeted tests -> staging proof -> capability status update.
Capability states: planned, implemented, tested, staging_verified, operational; require evidence IDs for every promotion.
Preserve actual existing publication/financial authorizations; this technical handoff adds no payment/spend authority and does not merge PR #32.

## 7. Copyable next-turn instruction
SOL: Continue Saeit from the current integration branch, preserving concurrent changes. Read this report, compare the deployed revision, map actual stages 4 and 5, and capture one failing runtime trace. Repair acquisition AND the empty-economic-factor contract; preserve SSRF/provenance gates. Work in small bounded batches without RDC or mandatory paid APIs. First prove real source retrieval, DB persistence and automatic 4 -> 5 advancement on the SAME run. Then verify downstream fact-based validation, crash replay and provider failover. Return deployed SHA, run/task/evidence IDs, transition evidence, tests and remaining blockers. Implement the twenty capabilities only in the gated package order above; do not claim them operational before evidence exists. Production stays untouched; PR #32 stays unmerged.
