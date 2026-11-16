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
