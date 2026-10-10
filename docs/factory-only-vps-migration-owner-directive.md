# OWNER DIRECTIVE — FACTORY ONLY VPS MIGRATION (supersedes prior plans)

**Effective 2026-10-10. This instruction supersedes all earlier dual-instance / full-agent-copy migration plans.**

## Absolute scope
- Transfer and deploy **only the virtual factory** to VPS 178.239.147.150, subject to verifying actual live source and available capacity.
- **Master Agent stays exclusively on the website hosting.**
- **All subordinate agents stay exclusively on the website hosting.**
- **NEVER copy, sync, package, deploy, or run the Master Agent or subordinate-agent code, runtime, registries, data, snapshots, or credentials on VPS**, including as part of a full-directory rsync, tarball, container image, backup or migration archive.
- No agent migration or agent cloning. Do not disable or remove original hosting agents.
- Preserve both live websites and their hosting runtime.

## Safe migration engineering
1. Inventory the live factory's exact code and data dependencies. Identify and explicitly exclude all agent-related paths, even if nested inside factory folders.
2. Create an allowlist-based factory-only export; reject ambiguous modules or mixed directories. Generate a manifest of included files and an explicit denylist check before transfer.
3. Keep backups containing agents on the hosting side only. Never ship them to VPS. Factory-only backup may be transferred if verified to contain no agent content or secrets.
4. Configure factory VPS process, isolated PostgreSQL, workers, scheduler and network access. Keep Master Agent and subordinate agents executing only on website hosting.
5. Integrate via authenticated, scoped, TLS-protected API between hosting agents and VPS factory, with idempotency and audit logs; do not share agent source or secrets.
6. Validate real factory product execution and stage 4→5 evidence persistence, hosting agent health, both websites, rollback, capacity and no-agent-on-VPS audit.
7. Obtain owner approval before any destructive action or production cutover.

## Gate
**Fail the release** if any Master Agent or subordinate agent content is included in the factory migration artifact, container, VPS filesystem or deployment process. Do not report deployment complete without direct server proof.

Status: directive recorded; not evidence of deployment.
