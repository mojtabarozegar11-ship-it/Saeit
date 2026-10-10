# Unified Command Center — implementation contract

Scope: existing staff portal, Iranian site, international site, virtual factory, moj_1ro_1 master agent, agents, bots, VPS, cPanel and GitHub. Additive integration only. Do not assume a service is healthy based on a successful CI build.

## Delivery sequence
1. Inventory deployed URLs, Django routes, models, agents, existing staff dashboard and production data sources. Preserve existing components.
2. Build read-only adapters per system with explicit source, timestamp, freshness, and failure status. Never replace unavailable metrics with zero or fabricated percentages.
3. Persist service heartbeats, production stage transitions, agent tasks, deployment revisions, incidents and evidence references with strict tenant/site scopes.
4. Add role-protected API endpoints for overview, timeline, topology, task drilldown, progress, incidents and evidence. Expose only sanitized errors.
5. Build responsive Persian RTL charts: production throughput, task success, agent health, site page status, incident history, costs and dependencies. Drill down from each visual to raw evidence.
6. Integrate master-agent chat through an authenticated command gateway. Commands have idempotency key, actor, scope, proposal, risk classification, explicit owner approval for execution, progress events and immutable audit history.
7. Implement incident correlation: last confirmed success, first failed step, affected dependencies, suggested remedy, and verification of recovery.
8. Release via separate reviewed PR, staged rollout, backups, and production verification. Never auto-deploy from this branch.

## Required states
healthy, degraded, failed, stale, unknown, unauthorized. Unknown is never green. Progress means evidence-backed completed acceptance criteria / total criteria, with unverified items shown separately.

## Security
No arbitrary shell from chat, no secrets in UI/logs, no uncontrolled code self-modification, no privileged operation without approval; CSRF, authentication, authorization, rate limiting and audit are mandatory.

## Acceptance criteria
- Real service outage appears with timestamp and evidence.
- A factory item blocked between stages 4 and 5 displays its real failure point, not a synthetic percentage.
- Both websites show page-by-page published/live state independently.
- Agent commands cannot execute before required owner approval.
- Every chart value links to its source and collection time.
- Existing staff portal remains functional.
