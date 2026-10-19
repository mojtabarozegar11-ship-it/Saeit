# Zomorod live agent gap check and actual MojPlayWin reuse — 2026-10-18

## Existing safely copied and used before this audit
- 77 exact V91 master/editorial source modules archived for private MojPlayWin engine (NOT 77 independent running agents).
- 11 Zomorod V11 monitoring roles copied, adapted to main-domain MojPlayWin, real 11/11 checks successful and isolated private cron at minute 37 hourly.
- Gen64 master + research digest + product blueprint run as private, review-only and independent from Zomorod and factory.

## New discovery in this audit
A source-only audit on the **current live Zomorod Django source directory** `/home/zomorod2/Saeit` found 10 Python agent-related modules present, some differing from shared GitHub source. These modules include:
- `core/agent_registry.py`
- `core/economic_master_agent.py`
- `core/knowledge_agent.py`
- `core/knowledge_quality.py`
- `core/company_activity_agent.py`
- `core/weather_agent.py`
- `core/newsletter_engine.py`
- `core/worker_runner.py`
- `core/master_agent_capability_pack.py`
- `core/management/commands/knowledge_agent_generate.py`

Exact SHA-pinned copies verified in this **private non-web destination**:
`/home/zomorod2/.private_mojplaywin_main_agents/zomorod_django_agent_sources_20261018/`

GitHub Action: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39100145152.

The original Django modules are **NOT directly imported or executed** because they have Zomorod DB/model/brand dependencies. Retaining ten modules is not the same as activating ten independent new agents.

## New actually reused capability — editorial science/newsroom quality
A MojPlayWin-private review adapter `scripts/mpw_review_private_drafts_with_zomorod_quality.py` parses **exact current Zomorod source AST** to obtain the 11 science/editorial quality requirements, 10 SEO requirements and the original newsletter quality threshold of 90. Both source files are rechecked against their copied SHA manifests before any review. It does not execute Zomorod Django code and cannot publish.

On real private MojPlayWin drafts:
- Evaluated two existing private research/product drafts.
- **2 need editorial revision**, **0 pass the source newsroom threshold**.
- Nothing auto-published, no source files modified.
- Initial report: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39100289622

Installed one new standalone quality-review cron at **minute 49 hourly**, preserving existing ten cron entries and storing an exact private rollback copy. Verified real review and readback:
https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39100464243

As a result, this is **one additional functioning quality-review agent**, not ten. There are now private role cards for Gen64 + two editorial drafts + eleven HTTP monitors + one quality checker = **15 separately described private roles**. These roles are not equivalent to the 18 registered Django Agent model rows on a separate/shared DB.

Private staff dashboard now includes per-agent quality counts and 14-day graph. The latest 14-file SHA-verified management release candidate on cPanel:
`/home/zomorod2/.private_mojplaywin_main_agents/management_release_quality_20261018/`
https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39100657561

## What remains deliberately NOT claimed or modified
- The original Zomorod Django DB query failed with `OperationalError`; no verified exhaustive list of its live DB agents. This limitation prevents a claim that everything has been migrated.
- The copied `weather_agent` and `newsletter_engine` Django code is not executed directly. They depend on Zomorod models and/or external APIs and require separately isolated adapters.
- No MojPlayWin public/admin Django deployment. The UI candidate is **private only**, pending shared Passenger tenant isolation and verified complete restore. No app restarts, `.htaccess`, cron removals, database migrations, domain/subsite changes, public publishing, orders, transfers or other factory operations.
- All original Zomorod sites, MojPlayWin child sites, and independent VPS factory remain unchanged.
