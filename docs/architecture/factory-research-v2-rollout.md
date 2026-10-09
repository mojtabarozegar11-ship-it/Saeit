# Factory Research V2 — safe rollout checklist

## Verified GitHub / hosting divergence

This GitHub main is at commit `da8eb37` (2026-10-05) and its core migrations
end at `0039`. The current hosting project, as observed earlier, has
FactoryRun, a more recent research provider, and core migrations through
`0048`. Accordingly this branch is **not yet deployable as-is**.

## Proposed module boundaries

`SearchJob -> SourceJob -> EvidenceSnapshot -> EvidenceGate`. Source failures
and short retries must not consume the parent `AgentTask` attempts.

The scaffold in `core/factory_research_v2.py` contains idempotent scheduling,
atomic per-source claims, successful snapshot persistence, and per-source
failure accounting. It deliberately does **not** invoke the network: adding
an HTTP client without DNS rebinding / SSRF controls would be unsafe.

## Before deployment

1. Reconcile the current server code (excluding .env, keys, databases and
   private products) with this branch. Do not overwrite newer server files.
2. Import V2 models from core.models. Generate the migration against the
   **actual** migration leaf; never guess dependency names.
3. Add a pinned-IP HTTPS fetcher: public-address validation at connection
   time, no redirects, bounded 5s network timeout, bounded body and safe MIME.
4. Implement URL relevance scoring, source/publisher independence, content
   extraction and source-attribution verification. SHA256 proves only bytes.
5. Add a short bounded Django worker command invoked under flock, and wire its
   persisted outcomes into FactoryRun/TaskRuntime without burning retry 3.
6. Add tests for timeout, invalid URL, SSRF, duplicate scheduling, crash
   recovery, stale execution identity, evidence independence, SQLite migration
   and end-to-end private checkout/download.
7. Staging smoke-test: two truly relevant independent external snapshots;
   Validation; deterministic deliverable; QC>=85; mocked payment/download.
8. Deploy only the verified delta. Enable neither paid LLM nor crypto mainnet
   automatically. Count no product until it is real and live.

The scaffold is a preparatory implementation, **not** a finished automatic
factory or proof of an operational research pipeline.
