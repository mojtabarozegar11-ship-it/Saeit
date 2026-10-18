# MojPlayWin main: V91 Agents — operational release handover (2026-10-18)

## Scope, without exceptions
This is ONLY for MojPlayWin's MAIN site. Original independent sub-sites, Zomorod Melal, the independent VPS factory, existing MojPlayWin homepage/store/payment and other shared account applications cannot be changed.

## Completed, verified
1. **Original V91 source preserved:** 77 exact source-verified master agent, Gen12–64 and editorial engine modules in GitHub feature branch `feat/mpw-v91-agent-port-isolated-20261018` and private cPanel staging. No original files deleted. Evidence: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39089848250 .
2. **Main-only worker running** on cPanel: one cron at minute 17 hourly, and private Gen64 master heartbeat, no factory linkage or publication. One of several independent readbacks: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39096655665 .
3. **Real agent output, not only a heartbeat:** read-only audit initially confirmed both queues and completed outputs were zero (https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39096819534). Two MojPlayWin main-only editorial briefs were then safely queued and processed by the REAL Gen64/rule-based engine; **two verified private, review-only drafts** resulted, one research digest and one product blueprint, with no public changes or auto-publication (https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39097004989). Their subject matter is browser educational game evaluation and a web game design educational product outline. These are NOT sold or published.
4. **Staff-only dashboards and charts** source tested on isolated branch. 11 precise SHA256-verified chart/administration source files copied to private **non-webroot** cPanel path `/home/zomorod2/.private_mojplaywin_main_agents/management_release_candidate_20261018/`, evidence https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39096557300 .
5. **Staff chart reads actual cPanel outputs:** the actual staged Django metrics module evaluated against real private output, observing master Gen64 active, one verified research draft and one verified product blueprint draft in last 14 days, no invented prior history, no auto-publishing, no live app import or DB modifications: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39097132329 .
6. **Code quality**: Previous CI + Django CI had 723 passes and 5 skips each at commit `2eda718996206998c0a944b2b0c905c313887ec0`; subsequent changes on this branch are subject to latest CI, do not misreport older CI as validating newer code.

## Needed before public management panel is live
Actual live shared-Django release gate observed original dashboard, staff API, and charts **not installed in active** `/home/zomorod2/Saeit-staging`; installed only in isolated private candidate. Audit: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39096402804 .
- Original `.github/workflows/mojplaywin-main-deploy.yml` is deliberately hard-stopped `if: false` because shared Django/Passenger serves independent protected child sites. Do NOT lift this hard stop without verified restoration and deployment isolation.
- Full live app/database/media recoverable backup and child-site-isolated Passenger restart/route-switch were not proven. An archive of original V91 *agents* is not a backup of the live site.
- Consequently PR #466 stays draft/unmerged and no public or staff HTTP route was published. Keep the public agent UI absent. Only staff UI on the main host is desired, and actual code includes staff guard, host guard and private metrics.

## Exact next safe engineering task
Prove a tenant-isolated Django/Passenger deployment and individually verifiable rollback without writing to shared production routes in the meantime. Once that gate passes, release the GitHub branch **only to main MojPlayWin staff routes**, test authenticated admin URLs and real charts, and protect all independent sub-sites and their existing media/content. No server-wide restart.
