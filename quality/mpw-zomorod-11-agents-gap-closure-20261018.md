# Zomorod site agents cross-check → MojPlayWin main-only reuse (2026-10-18)

## Verified original Zomorod inventory
- Independent **Zomorod V11 site-audit subsystem**: 11 runtime agent roles: `master`, `content`, `seo`, `commerce`, `agriculture`, `research`, `economic`, `weather`, `quality`, `media`, `security`.
- Zomorod live workflow executed all 11 successfully with HTTP 200 on the original site's URLs: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39097213832
- Preserved exact Zomorod V11 original PHP source in this MPW feature branch as **non-executed heritage reference**: `mpw_v91_port/heritage/zomorod_v11_site_agents_reference.php`; reusing the PHP directly would check Zomorod domain, so a bounded MPW-only adapter was written.
- Existing Django modules `core/knowledge_agent.py`, `core/weather_agent.py`, `core/company_activity_agent.py`, agent capability registry and commands were already in the common GitHub repository. **Not duplicated** because their Zomorod-specific Django/database dependencies must not be assumed safe for MojPlayWin.
- Read-only Zomorod *Django database* role inventory returned `OperationalError`, so number and live status of additional Django agents on Zomorod are **not verified**, and no claim is made of exhaustively copying every Zomorod subsystem: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39099349770

## What was actually copied, adapted and started for MojPlayWin
- Main-only adapter: `mpw_v91_port/site_health_v11.py`: 11 fixed paths on `https://mojplaywin.com` and no child-site, Zomorod or factory URLs, publishing, admin login, payments or Django models.
- Private verified cPanel copy: `/home/zomorod2/.private_mojplaywin_main_agents/site_health_v11_port_20261018`, with original V11 PHP reference and MPW-specific Python runner. Six static security/copy tests passed. https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39098783951
- Real inaugural HTTP health check: **11/11 successful**, 0 warning, 0 errors. https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39098837942
- Added one standalone private cPanel cron, minute **37 hourly**; installed only after 11/11 check, with an exact private pre-change crontab backup. All existing 9 cron entries retained verbatim; there are now 10. https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39098953042
- 11 further private graph data series: `command_center/mpw_v11_site_agent_charts.py`. Dashboard API now appends these 11 to Gen64+research+product roles. The staff UI shows site-monitor counts and actual warning/error counts, distinguished from generated drafts; all only in the main-host authenticated staff dashboard. URL remains protected.
- A **13-file** SHA-256 verified **private (NOT live)** management-panel release candidate saved at `/home/zomorod2/.private_mojplaywin_main_agents/management_release_v11_agents_20261018`. https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39099250317
- Live private record readback: 11/11 named chart series had data; **22 successful HTTP checks**, 0 warnings, 0 errors recorded in 14-day graph window. https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39099445196

## Explicit boundaries
- Original `zomorodmelal.ir` unchanged, original V91 preserved.
- No changes to factory VPS, MojPlayWin subsites, site homepage, customer data, payment systems, shared Django/Passenger or MySQL.
- **No automatic publishing**, content agents remain review-only; site monitors only audit HTTP route health. Recovered monitors are running in private cPanel, independent from the existing private Gen64/editorial worker.
- Admin charts still **not released into live shared Django**: main-site deployment workflow retains hard stop pending proven tenant isolation and full verified backup/rollback.
- 77 original V91 modules already copied earlier are distinct from 11 additional V11 monitoring roles; do not claim they equal 77 running agents.
