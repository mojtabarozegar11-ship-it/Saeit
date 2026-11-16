# Native-site migration parity evidence for Mojtaba.bot.ai (source stage)

Date: 2026-11-16. Central VPS/factory strictly out of scope.

## Legacy Zomorod PHP responsibilities confirmed in source

- `site_agent_cycle_cli.php`: 11 on-origin HTTP health checks + up to two site-only structural evidence audits per 10-minute Cron tick.
- `site_agent_workforce.php`: private SQLite tables `site_work_outputs`, `site_work_state`, and `site_work_generation_evidence`; owner review interface reads historical rows.
- `site_agents.php`: page/UI management for old agent records. Removing these three files **before replacing the admin dashboard and preserving historical evidence** will break the user-facing management view.

## Canonical bot implementation versus legacy

| Capability | New implementation | Cutover assessment |
|---|---|---|
| 11 HTTP roles | `core/mojtaba_site_fleet.py` | Source implemented; live bot execution unverified |
| Structural title/H1/meta/link audits | `core/mojtaba_site_quality.py` | Source implemented; scores/issue codes now durable and redacted in `AuditLog` |
| Cron every 10 min, singleton | No live scheduler on `mojtaba.bot.ai` confirmed | BLOCK |
| Historical private SQLite audit preservation | `core/mojtaba_site_telemetry.py` imports **summary only** | BLOCK; not the historical row set |
| Owner-facing PHP admin dashboard parity | No replacement UX verified | BLOCK |
| Editor, commerce and research private worker parity | No proven replacement receipts | BLOCK |
| Backup + off-host restore | Not attested | BLOCK |
| TRON/storefront/billing | Explicitly excluded from HTTP monitoring | Preserve; cannot claim commerce readiness |

MojPlayWin: the 77 module entries are library slots, not 77 independently running workers. The private telemetry importer does not execute or migrate those business modules. The original private collector's 15-minute Cron, report location and replacement destination must be reconciled before touching the collector or its directory.

**Retirement remains NO-GO.** Use an exact host manifest, per-worker acceptance receipts, off-host restore and independent rollback before *any* deletion. A clean CI suite alone is not deployment or commercial evidence. No database or customer information may be deleted under the site-agent cleanup.


## Follow-up: full history lineage and emergency PHP viewer (source only)

- scripts/mojtaba_zomorod_history_parity_readonly.py reads **exactly five
  known site-agent history tables** from an already checkpointed immutable
  SQLite database using mode=ro&immutable=1 and PRAGMA query_only=ON.
  It streams and hashes **all original columns/rows** in stable key order,
  emits only table row counts and SHA-256 values, and never exports titles,
  findings, run details, customer data or underlying database bytes. The
  unrelated private company-accounting database is outside the scanner.
- If a WAL, SHM or journal sidecar is present, any required table is absent,
  a source column changes, an inode/size/mtime changes during reading, or a
  symlink is found, the result is **incomplete / NO-GO**, not an empty archive.
- compare() accepts two independently obtained completed manifests.
  Equality of digests is a logical-history parity aid, **not cryptographic
  source authentication** or proof an off-host restore was performed. The
  backed-up SQLite file must still be restored and independently tested.
- The manual main-only, SSH-host-pinned cPanel inventory now can also obtain
  these lineage digests. It **never** runs against production on pull_request.
  Status at source stage: no authentic cPanel lineage manifest obtained.
- content/zomorod-business/app.php now retains original active zmAgentRender
  when present. If the old runtime is missing, a bounded staff-authorized
  **read-only emergency archive view** displays up to 14 historic health
  checks and 14 structural QA results from an explicitly read-only SQLite
  handle; no private text/findings displayed. Old POST actions fail
  unavailable rather than simulating an active worker.
- This emergency view has only partial UX parity: it does **not** replace
  old charts, role toggles, worker execution, generation evidence details,
  report export, 10-minute schedules, or archival access to every row.
  It therefore cannot justify removing the original PHP/SQLite/Cron.
- Original history and content/zomorod-business/app.php must be retained
  until independently verified full owner-facing functional parity, off-host
  restore, legacy process retirement and actual replacement scheduler receipts.

**Current approved deletion scope: none.** Source tests do not establish
production readiness or create an authorization for deletion or cron changes.
