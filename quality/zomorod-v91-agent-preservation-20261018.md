# Zomorod Melal V91 — agent source preserved

Date: 2026-10-18. Authorized source is the **unused** V91 Zomorod Melal draft at `/home/zomorod2/saeit_v91`. This is not the live site.

## Result — verified private copy on VPS
- GitHub Actions run: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39086083902 — **success**.
- Saved 203 source code/doc/test/dependency files: 73 `site_master` files, 121 `portal` Python files, 9 other docs/tests/requirements.
- Total expanded source bytes: **656905**.
- Transfer archive bytes: **189704**.
- Archive SHA-256: `4b825f80e06d632d5aac1717f82fac32b731ca89247a45b48f2222bdd86c858c`.
- Destination (VPS / githubops account, outside web roots):
  `/home/githubops/.private_zomorod_v91_agents/v91_master_agents_20261018_run39086083902/`
- Files: `agents.tar.gz`, `V91_AGENT_MANIFEST.json`, `SHA256SUMS` and the unpacked `recovered_source/`.
- Every archived member was checked against the individual source SHA-256 in the manifest before being saved as a private working copy. Source directories, site files, hosted services, database, cron and Passenger were not changed.
- No passwords/private keys/DB/media were intentionally collected; filename-based secret filtering and regular-file-only export were enforced.
- Includes `site_master/vendor/master_gen12..64`, `portal/agent_engine.py`, `agent_services.py`, `agent_claims.py`, `agent_run_lock.py`, both `run_site_master.py` and `run_site_agents.py`, related Django Python files/migrations, test and integration notes.

## Restore and subsequent use
1. Use the **already preserved** private archive and `recovered_source/`. This is source preservation, not activation on MojPlayWin, Zomorod Melal, or any live site.
2. Verify `SHA256SUMS` and the manifest again before repurposing agents; perform sandbox dependency/import checks. No production cron/process has been enabled.
3. Do not assume the old V91 website content, images, databases or credentials were backed up. This archive intentionally includes only selected agent-related source. Deleting V91 would destroy anything not included.
4. Before the owner deletes the original V91, preferably create a **second independently stored, recoverable backup** of this private archive (e.g., owner-controlled off-VPS storage). Never delete V91 automatically.

No live changes permitted as part of this preservation task.
