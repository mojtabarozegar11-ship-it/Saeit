# Scientific Multi-Business Agent — Architecture v1.0

Status: architecture specification, not proof of live deployment.
Scope: 1 orchestration runtime, up to 50 isolated business tenants, multiple authorized channels per tenant.

## 1. Architectural invariants
- Evidence-first, reproducible, provenance-aware decisions. No fabricated metrics, claims, trends or results.
- Every record, queue job, artifact and credential is scoped to tenant_id.
- Explicit authorization for destinations; high-impact spend and contractual/financial actions require separate controls.
- Drafting is not publishing. An offline script is not an autonomous learning system.
- No cross-tenant content, secrets, analytics or audience leakage.
- Bounded retries, quotas, audit trail, idempotency and graceful degradation.

## 2. Services (modular monolith initially)
1. Registry & Identity: tenants, brands, destinations, roles, policies, authorized account references.
2. Scientific Knowledge: versioned sources, confidence, freshness, methodology, retractions and supersession.
3. Discovery: official API and permitted public feeds; regional/category-specific sampling; provenance and timestamps.
4. Evidence QA: URL validity, source credibility, duplicate detection, statistical context, relevance and uncertainty.
5. Competitive Intelligence: compare normalized cohorts by market, language, audience, channel, age and denominator; never call sampled rankings 'global winners'.
6. Brand Strategy: audience segments, brand positioning, editorial objectives, differentiation and measurable KPIs.
7. Planning: tenant-aware priorities, calendars, resource and budget constraints, experiment hypotheses.
8. Creative Production: original text, visuals and video via explicitly configured models/tools; source-backed factual claims.
9. Scientific Quality Gate: fact-check, brand fit, copyright, accessibility, policy, hallucination and bias checks.
10. Approval & Distribution: per-destination authorization, review state, scheduler, outbox and platform-specific adapters.
11. Measurement & Learning: platform-reported metrics, baselines, attribution limits, experiments, rollback and versioned policy updates.
12. Reliability & Security: observability, cost caps, secrets, incident response, backoff, audit, retention and recovery.

## 3. End-to-end state machine
DISCOVERED -> SOURCE_VERIFIED -> INDUSTRY_MATCHED -> STRATEGY_APPROVED -> DRAFTED -> QA_PASSED -> DISTRIBUTION_AUTHORIZED -> SCHEDULED -> PUBLISHED_CONFIRMED -> METRICS_OBSERVED -> LEARNING_REVIEWED.
On failure: NEEDS_EVIDENCE, NEEDS_REVIEW, QUARANTINED, RETRY_PENDING or FAILED.
Never skip source verification or quality gates. Scheduled does not imply published.

## 4. Minimum entities
Tenant(id, name, industry, markets, languages, limits)
Brand(tenant_id, positioning, voice, audience, policy_version)
Destination(tenant_id, platform, account_ref, authorization_state, capabilities)
Source(id, url, publisher, observed_at, published_at, method, license, reliability)
Evidence(tenant_id, source_id, metric_name, metric_value, denominator, measured_at, limitations)
KnowledgeVersion(domain, version, source_ids, valid_from, review_due, supersedes)
ResearchFinding(tenant_id, evidence_ids, confidence, relevance, scope)
Campaign(tenant_id, goal, audience, hypothesis, budget_cap, kpi, status)
Artifact(tenant_id, version, content_hash, citations, qa_state)
Approval(tenant_id, artifact_id, destination_id, actor, scope, expiry)
DispatchJob(tenant_id, artifact_id, destination_id, idempotency_key, state, attempt_count)
Metric(tenant_id, destination_id, artifact_id, value, window, source)
AuditEvent(tenant_id, actor, action, result, timestamp, trace_id)

## 5. Knowledge refresh targets
Trends and performance: daily where supported by licensed/official sources.
Platform rules: weekly plus change alerts.
Evergreen science and management: monthly review, immediate updates on major corrections.
A scheduled check is not proof of an update. Maintain freshness labels and last successful fetch time.

## 6. Quality gates and acceptance
G0 tenant and destination isolation: reject missing/invalid tenant, credential leakage and unauthorized destination.
G1 source and evidence: traceable source, observation time, correct metrics, stated geographic/platform coverage.
G2 strategy: industry relevance, target audience, objective, hypothesis, baseline and KPI.
G3 content: original, accurate, cited claims, platform-compliant, accessible, brand-appropriate.
G4 authorization: correct destination, approved version, expiry and media requirements.
G5 dispatch: durable queue, dedupe, bounded retry, confirmed provider receipt.
G6 learning: compare observed metrics with baseline, record uncertainty, version and rollback.

## 7. Execution phases
P0: inspect current GitHub workflows, branch, permissions and tests; preserve main/production.
P1: enforce evidence gate (empty research must not yield 'research-backed' claims); tests.
P2: registry-driven 50-tenant isolation and durable SQLite/Postgres data model; tests.
P3: official-source adapters with quotas, timestamps and independent source provenance.
P4: brand strategy, knowledge-versioning and QA enforcement.
P5: authorized publishing adapters with dry-run first and explicit permissions.
P6: live staging E2E: source -> approved draft -> provider confirmation -> observed metrics.
P7: production rollout tenant by tenant with rollback and cost controls.

## 8. Deployment and economics
Prefer a Python modular monolith and existing GitHub Actions for low-volume research/draft scheduling; use DB-backed workers for reliable high-volume publication. Secrets in GitHub/host secret store, never repository files. Per-tenant and global quotas. APIs only where needed and permitted. No claim of zero-cost live discovery across every platform.

## 9. Explicit current limitations
Existing scripts are partial offline prototypes. YouTube discovery requires YOUTUBE_API_KEY and is regional/category-limited. No verified successful live discovery, full 50-tenant integration, autonomous scientific updating, publishing, or end-to-end production acceptance yet.
