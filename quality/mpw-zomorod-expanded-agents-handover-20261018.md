# Zomorod agent comparison and missing-feature recovery for MojPlayWin
**Verified:** October 18, 2026 | **Scope:** MojPlayWin MAIN site only

## Previously recovered
- 77 exact original V91 source modules: generations 12–64 master and two editorial proposal functions.
- 11 Zomorod V11 site health agents, adapted to fixed `mojplaywin.com` routes. Private hourly cycle at minute 37. Original Zomorod 11-role PHP source retained as non-executed reference.
- Existing MojPlayWin private Gen64+editorial review worker at minute 17, two private draft outputs.

## New source-level comparison
- Read-only, direct scan of the Zomorod live site `/home/zomorod2/Saeit` source confirmed 10 important Python modules and SHA-256 values, including `agent_registry`, `knowledge_agent`, `knowledge_quality`, `newsletter_engine`, `company_activity_agent`, `weather_agent`, `economic_master_agent`, `worker_runner`, `master_agent_capability_pack`, and `knowledge_agent_generate`.
- Ten original modules were copied byte-for-byte with hashes to a private `/home/zomorod2/.private_mojplaywin_main_agents/zomorod_django_agent_sources_20261018` reference directory. **They are not imported or executed directly**, because Django models and DB belong to the original site. https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39100145152
- The live Zomorod Django DB role inventory returned `OperationalError`. Additional historical roles, if any, cannot yet be verified or treated as safely portable. No Zomorod database was copied or modified.
- Verified SHA-based AST inspection of the original knowledge/scientific quality and newsroom constants. This is now used in a separate private MojPlayWin reviewer scheduled hourly at minute 49. The first two genuine drafts were rated **needs editorial revision**, 0 published. https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39100464243
- Extracted (with SHA verification, without importing the original modules) the original company-activity reporting formats and economic master-agent policy constants. **Two further MojPlayWin-only private capabilities**:
  - `company_activity_intelligence`: composes factual operational performance summaries from actual MojPlayWin private agent checks/drafts, **not** fictitious company project events;
  - `economic_master_policy`: reviews business/quality decisions but blocks ALL money movements, payment, trading and order-placement. No real revenue claimed.
  - Both executed successfully and now have one separate hourly private job at minute 58. All 11 existing crontab entries preserved, now 12 total. https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39103482594

## Staff management
- **17 individually reported private roles**: 3 old Gen64/editorial + 11 monitoring + 1 research/newsroom quality + 2 reporting/economic policies.
- Staff metrics sourced from private operator files, not generated counts. Historical performance for new economics/reporting roles is unknown beyond one observation and is NOT extrapolated.
- 15 SHA-256-verified staff-dashboard source files staged privately in `/home/zomorod2/.private_mojplaywin_main_agents/management_release_17_agents_20261018`; verified with standalone Django template rendering using actual cPanel agent state: 17 unique roles, 33 real successful recent monitor checks. https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39104015944
- All controls and chart code remain behind staff access/main domain. No new public agent page.

## Deployment and exclusions
- **NOT merged into production Django**. The private agents and cron processes DO run, but the 17-role management panel is private-staged/validated, not accessible from the live Django Admin until shared Passenger isolation, full backup and tested rollback.
- Zomorod Melal, its database, original V91, factory VPS and ALL independent MojPlayWin child sites unchanged.
- Zomorod weather and knowledge generation routines have original-site and external-data dependencies; do not blindly deploy, publish content, or claim they run as independent MojPlayWin agents.
- This audit has not proven that every historical Zomorod agent ever created has been located or activated; source-only preservation and reusable safe subset are what is verified.

PR: https://github.com/mojtabarozegar11-ship-it/Saeit/pull/466
