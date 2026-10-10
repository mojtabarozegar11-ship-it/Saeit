# Stage 4 → 5: staging acceptance gate (owner-authorized staging only)

## Current evidence
- GitHub Actions run 38006640387: all configured unit/integration tests passed.
- This does **not** demonstrate real staging DB connectivity, source persistence or a 4→5 transition.
- Staging reportedly has modules absent from this PR branch. **Do not deploy this branch over staging without first reconciling those files.**
- Never touch production, delete records, or promote/release without separate owner approval.

## Execution sequence for SOL
1. Confirm the SSH relay and pinned host fingerprint through existing GitHub Actions → VPS → cPanel route; never disable StrictHostKeyChecking.
2. On staging, snapshot non-secret configuration and back up the staging DB using approved mechanisms. Never print passwords or paste .env into CI logs.
3. Resolve staging DATABASE_URL using the existing staging DB identity and authorized credentials. Percent-encode reserved characters in URL credentials. Confirm the selected DB is not production. Avoid guessing passwords or copying production credentials.
4. Run scripts/staging_db_preflight.py against the staging environment configuration. This checks URL structure only, **not** connectivity.
5. Export the staging environment securely into the process (not into logs); run scripts/staging_postgres_live_gate.py using the staging venv. Require DATABASE_BACKEND=PASS, STAGING_DB_ISOLATION=PASS and LIVE_POSTGRES_READONLY_QUERY=PASS. On failure stop.
6. Reconcile the deployed stage-4 provider, fetcher, transient recovery and stage-4 modules against GitHub before any code replacement. Maintain SSRF/DNS/IP pinning, request budgets, deadlines, evidence provenance and independent publishers.
7. Select **one** existing staging product currently at stage 4, record its immutable ID, state, attempt ID and baseline evidence row count. Do not fabricate or seed evidence.
8. Trigger one owner-authorized bounded staging research attempt. Log source URL host, fetch status, relevance rejection reason and content hash, not secrets or full private content.
9. In a fresh DB connection verify ≥2 real, relevant, independent-source evidence records are persisted with correct product/run FK, source identities and fetch timestamps. No fixture:// sources.
10. Verify the **same product** transitions 4→5 without manual state editing; confirm durable state in a second fresh DB connection, with transition event, run ID, and timestamps.
11. Re-run once to verify idempotency: no duplicate evidence or duplicate transition. On failure preserve sanitized logs and report exact failed gate, without claiming success.

## Acceptance criteria
PASS only when all of the following are true on **real staging**:
- PostgreSQL identity is isolated from production and read-only live query succeeds.
- Actual network sources yield valid, independent and persisted evidence.
- The same existing product moves 4→5 automatically.
- Persistence survives a new connection, and retries are idempotent.
- Audit includes code revision, run ID, product ID, timestamps and gate results, without secrets.

Any missing item is BLOCKED, even when GitHub CI is green.
