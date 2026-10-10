# Owner directive: full factory on VPS; site agents retained; required shared agents in both

Effective 2026-10-10. **Supersedes** prior blanket prohibition of all agent copies and all earlier blanket-copy plans.

1. Deploy the **entire operational virtual factory** on VPS 178.239.147.150, including required factory code, persisted state, database migrations, workers, scheduling, dependencies and monitoring.
2. Keep **100% of the original website Master Agent and all website agents on hosting**. Do not remove, disable, or relocate them.
3. Copy **only the shared agents actually required by both the website and the factory** to VPS. Preserve their original copies on hosting. Establish a verified, explicit allowlist by identity and role before copying. Do not copy the main website Master Agent or site-only agents merely because they reside in the same source tree.
4. Distinguish factory-internal orchestration (e.g. a component named Factory Master Agent) from the separate website Master Agent. Classify by code, responsibilities, and actual dependencies, **not just names**. Factory-internal agents required to operate the factory belong on VPS; shared agents may exist in both.
5. Isolate credentials, queues, schedulers, state and worker IDs across environments; protect against duplicate outbound side effects; integrate over authenticated scoped API.
6. Before any export: inventory deployed factory and agent dependency graph; capture consistent backups; build allowlisted, checksum-verified transfer bundles and reject unclassified agent paths. Avoid transferring redundant backups or host virtualenv when reproducible.
7. Verify VPS resources, PostgreSQL, live factory job and stage 4->5 evidence persistence, website agent health, both websites, restore and rollback.
8. No destructive changes, DNS cutover or production go-live without owner approval. Do not claim deployment completed until verified on live VPS.

**Current status:** policy only; not a completed migration.
