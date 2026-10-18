# V91 agent preservation: two independently-hosted verified copies

As of 2026-10-18, the user's abandoned V91 site template is **NOT DELETED**. The requested V91 *agent-related code only* is protected by two archives on separate physical hosts.

## Copy 1 — VPS
- `/home/githubops/.private_zomorod_v91_agents/v91_master_agents_20261018_run39086083902/agents.tar.gz`
- 189,704 compressed bytes, 203 SHA-256-verified entries and unpacked private working source
- Preservation run: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39086083902

## Copy 2 — cPanel, outside V91 and webroot
- `/home/zomorod2/.v91_agents_safety_copy/v91-master-and-site-agents-20261018.tar.gz`
- 189,704 bytes; independent copy from VPS, not from the original V91 directory
- All 203 entries re-read from compressed archive and checked against the embedded per-file SHA-256 manifest
- Confirmed `created_and_verified`, second-host recovery inspection success
- Run: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39088722802

## Common archive integrity
SHA-256: `4b825f80e06d632d5aac1717f82fac32b731ca89247a45b48f2222bdd86c858c`.

## Run readiness
- Real Generation64 callback succeeded on VPS in read-only isolated run https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39087337513.
- Real Generation64 callback succeeded again on cPanel in read-only isolated run https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39087919799.
- cPanel confirmed original Django master + agents management files and safety flags https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39087821805 and https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39088027667.
- Source content engine initial dry run **REJECTED** because synthetic input didn't satisfy the original input contract. The actual code requires Persian language, `research_digest` kind, approved HTTPS source string and long enough title/summary/body. Corrected synthetic test source committed but its remote workflow execution is **not confirmed**; must NOT say all agents run.
- No live site, DB, Passenger, cron, installed services, payment or independent sites were modified.

## Deletion safety policy
**Do not delete the V91 folder automatically.** Both backups preserve only agent source and related dependencies. They do not preserve ALL V91 templates, other content, archives, SQL databases, media or legacy project files; such content would be irreversibly lost if the owner deletes all V91. A separate full V91 backup with restore proof or explicit acceptance of loss is necessary before approval to delete the whole original. Verify neither copy has been removed first.

These copies are preserved private sources, not a persistent or production-ready agent deployment.
