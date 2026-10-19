# MojPlayWin V91 Master + Agent Port — verified transfer

Date: October 18, 2026.

## Scope
**Only main MojPlayWin** at `https://mojplaywin.com/` and `https://www.mojplaywin.com/`. Never touch MojPlayWin's independent child sites, the Zomorod Melal website, or the separately running VPS factory.

## Confirmed completed
- Ported **77 exact original V91 source files** to `mpw_v91_port/legacy/` in GitHub feature branch `feat/mpw-v91-agent-port-isolated-20261018`. Includes generation 12–64 master controllers, `site_master/bridge.py`, `portal/agent_engine.py`, `portal/generator.py`, lock and validation helpers. All copied from the verified original V91 source archive with source SHA-256 `4b825f80e06d632d5aac1717f82fac32b731ca89247a45b48f2222bdd86c858c`.
- GitHub original-source import SUCCESS: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39089848250
- Private cPanel main-site staging verified: `/home/zomorod2/.private_mojplaywin_main_agents/v91_verified_main_port_20261018`. **82 staged module/manifest files**, 77 original V91 modules, ~152,517 expanded bytes. SHA-256 comparison of all legacy modules passed.
- Actual Gen64 + legacy Persian research-agent callback passed in isolated private cPanel stage: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39090346500 .
- MojPlayWin-only `mpw_v91_port/runtime.py`: two source extraction features (`research_digest` and `product_blueprint`), no external request, no publication, no database changes, no settlement or payments, no scheduled tasks.
- `core/mojplaywin_v91_agent_views.py` and `config/urls.py`: isolated private draft API `POST /agents/v91/review/`, only if main MojPlayWin hostname **and** staff login **and** CSRF token **and** `MOJPLAYWIN_V91_AGENT_REVIEW_ENABLED=True`. The flag is **off by default**, so public traffic cannot use it.
- A test suite covers actual imported master/editorial engines, main-host restriction, strict inputs, staff permissions, and private review-only output.
- PR: https://github.com/mojtabarozegar11-ship-it/Saeit/pull/466 (draft; not merged).

## Hard deployment boundaries
No `main` branch merge, no real website deployment, no Passenger restart, no change to factory schedules/agents, no change to any child site, no Zomorod site change. Existing main homepage design/rows, store/payment, and all child app paths are preserved.

The shared Django production deployment workflow is deliberately disabled because a prior cPanel audit could not prove full tenant isolation and verified restore. DO NOT remove that guard to publish this feature until isolated production routing and recoverability are proven.

## Release checklist
1. Validate all standard CI and Django CI suites green for the latest commit. Verify source/port integrity and original site URL protections.
2. Prove all path-based child websites and Django/Passenger applications remain isolated, document a verified complete rollback plan and backup.
3. Only then merge and allow safe MojPlayWin main-only deployment. Keep `MOJPLAYWIN_V91_AGENT_REVIEW_ENABLED` false during deployment.
4. On the live main hostname, enable preview for authenticated staff only after tests of CSRF, rate limits, content size, and that no source is automatically published.
5. Do not conflate this MojPlayWin site-scoped port with autonomous factory agents.
