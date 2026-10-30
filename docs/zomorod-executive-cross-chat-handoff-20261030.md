# Zomorod Melal — cross-chat executive recovery and continuation register
Date: 2026-10-30 (Asia/Tehran). Scope: existing prepared deliverables, not recovered full transcripts.
Classification: PUBLIC-SAFE / EVIDENCE-BASED / NO DEPLOYMENT / NO CREDENTIALS.
Owner: Mojtaba Roozegar. Permanent execution case: https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1514

## Source-of-truth and stage rules
- Source **code**, CI **test evidence**, private **stage**, and **live production** are different states. Never infer one from another.
- The private Zomorod management ERP, the Django office messaging/marketing application, and factory VPS are **different runtimes** and must not be combined by blind file copy, DB migration or overwrite.
- Preserve the three live public sites' visual appearance, public business data, payments and factory VPS. Do not create new hourly tasks before the ERP project is complete.
- This register indexes work recoverable from GitHub, saved Library artifacts and Issue #1514; it does not imply access to every previous conversation.

## A — ERP CEO desk, accounting, HR, treasury, workflow
| Evidence | Actual state | Remaining acceptance |
|---|---|---|
| Verified V6 ZIP/TAR archive in ChatGPT Library; PR #1612 | 46 archive members / 45 hashed manifest entries. Exact source isolated in draft branch; PHP 8.2/8.3 CI green. Private staging path exists on 30GB cPanel; **NOT ACTIVE** | Review live-only app.php differences; verify restore and account quota before promotion |
| V7 integrated PHP/SQLite, PR #1607; offline QA report zomorod-erp-v7-offline-qa-40of40.json | 40/40 defined offline checks pass; integrated treasury, payroll, financial controls, industry, workflow and command center are **CODE ONLY** | Legal/statutory accountancy, payroll and operational acceptance not proved |
| PRs #1591, #1595, #1605, #1586, #1573, #1574, #1576, #1578 | Separated private development work: HR payroll review, finance, period closure, treasury dual-control, owner task desk, quality/evidence planner, encrypted private bridge | Reconcile all draft branches; no automatic merge into production |
| Read-only live inventory PR #1614; run #40979496436 | Live app.php lacks credential_stamp session revalidation. Only 3 of 11 inspected V7 private modules present; 8 missing. SQLite quick_check ok, 13 tables, one active admin | Fix session revocation safely in stage; confirm complete dependency graph and rollback |
| One-time owner credential rotation run #40941809886 | Reported SUCCESS; private database file permissions 0600 | No new plaintext password in chat/issue/git; legacy sessions not independently revoked |

ERP 8 live-missing V7 modules: workflow_desk.php, payroll_control.php, payroll_ui.php, period_controls.php, industry_operations.php, finance_audit.php, treasury_control.php, treasury_ui.php.
**Explicit nonclaim:** Neither V6 nor V7 is 100% implemented across all requested 24 business domains or production-certified.

## B — Company messaging, Iranian channels, marketing and CRM
PR #1577: https://github.com/mojtabarozegar11-ship-it/Saeit/pull/1577
- Framework: **Django** company_messaging + company_marketing (distinct from private PHP ERP).
- Private inbox, internal read receipts, scoped contacts, opt-in evidence, queued external messages; campaigns, leads, channel rights/consent, proof-backed metrics.
- Domestic interfaces: Bale, Eitaa opt-in, Rubika; verified posting contracts only for Bale/Rubika/Telegram; other networks recorded as manual/planning until supported.
- Latest head 0586eb53e26a1bfc311729f24ce7fb034414a4d5: offline-tests, validate, readiness checks **SUCCESS**; deploy **SKIPPED**.
- All external send/publication switches OFF; provider ownership/secrets, secure live login, effective MariaDB schema and restore-tested staging still missing.
- Do **not** enable ads/spending, bulk messages, workers or cron. Real external delivery not established.

## C — Master Agent, private chat-to-server channel, factory
- MasterAgent_Architecture_Lona_2026-10-27.md in ChatGPT Library is **design v1**, not a live activated brain. It specifies persistent mission/job/artifact/evidence/cost, worker/evaluator separation, fail-closed promotion and true delivered economic outcomes.
- Verified relay: GitHub Actions -> pinned VPS -> 30GB cPanel. PRs #1597, #1598, #1599, #1604 merged; authenticated encrypted Issue #1514 ingress is available. Do not place a plaintext command or secret in public GitHub comments.
- The private command channel has an allowlisted queue. Its production execution/receipt for arbitrary instructions from this chat has **not** been proven; do not equate accepted envelope with work executed.
- Factory: last read-only checkpoint shows **0 ordinary-user writable bytes**, high system load and no independently restored off-host backup; factory restart/release NO_GO. PR #1613 probes quota; the 30GB cPanel account quota still NOT_VERIFIED, although shared underlying filesystem has free capacity.
- Requested 80 production lines, 2000 tools and 1000/1000 quality are targets; neither product acceptance nor commercial delivery can be asserted from production-count reports.

## D — Related deliverables in other project conversations (separate scopes)
| Workstream | Recoverable source/status | Do not claim |
|---|---|---|
| Public Zomorod site, academy, company gallery and newsletter | PR #1534 draft read-only fallback; public pages and author/profile site exist separately | Full 500 diagnosis, current production fixes or DB migration |
| MojPlayWin store/payment/right-to-sell | Production checkout and rights/deliverability gates under investigation in #1514 and associated PRs | Paid purchase -> independent settlement -> invoice -> download proven |
| Books | Mushroom Persian/English volumes and technical chess/leech manuscripts in Library and book task checkpoints | Finished commercial publishing or complete qualified rights review |
| Research/profile | MR-2026-001, AE-2026-001, ZM-R01 manuscript work; owner profile/SEO checkpoints | Author signoff, peer-reviewed publication or external profile completeness |
| Games | Ramadan R30 source/checkpoints, Air Supremacy, ECHOFORM, Roham/Tania workstreams | Target quality or all games actively published |
| Digital banking/group lending and jobs program | Separate business/legal planning; employment portfolio counted as plans | Financial-service license, deployed bank, funded jobs or bank transactions |

Five existing hourly tracks remain research/profile, books, sites/subsites, games, factory/master-agent/trade. Report actual diff/artifact/verified receipt; avoid double counting and duplicate task creation.

## E — Mandatory gates before any Zomorod CEO ERP live release
1. One canonical V7 candidate reconciled against actual final V7 Library archive, V6 staging copy and host-only modules. Never wholesale replace active app.php.
2. Safe, read-only positive proof of 30GB hosting account quota/free space; do not substitute shared-host disk free.
3. Independently verified encrypted **off-host** application/database snapshot and isolated restore / timed rollback; no production migrations before this.
4. Old login-session invalidation enforced in production-compatible PHP logic and independently tested; user credentials only via secure one-use mechanism.
5. Exact live PHP/Passenger/PDO_SQLite and Django/MariaDB effective DB selection, schema compatibility, HTTPS/MFA, CSRF, staff role isolation and statutory controls proven on isolated staging.
6. Integrate PHP private ERP and Django messaging by designed authenticated service boundary/URL ownership/role policy; do not directly mix their tables or entrypoints.
7. Production deployment only via verified pinned relay with constrained change set, known rollback, external UI check and preserved public pages. External messages, payments, payroll posting and marketing remain disabled until separately authorized and proven.

## Immediate continuation cursor (not a deployment authorization)
- Resolve **session revalidation gap** without exposing current password and without altering production login until rollback is proven.
- Build exact source/host-only module reconciliation + dependency map; classify source, staged and live separately.
- Complete account quota and encrypted off-host restore proofs via read-only diagnostics and isolated controlled backup path.
- Run integrated staged ERP + Django messaging private-login/permissions tests after the above; preserve all public sites.
- Maintain this register and Issue #1514 as a durable cross-chat handoff; no fabricated completed actions.

**Verification links**
- V6 transfer: https://github.com/mojtabarozegar11-ship-it/Saeit/pull/1612
- V7 integration: https://github.com/mojtabarozegar11-ship-it/Saeit/pull/1607
- V7 read-only live audit: https://github.com/mojtabarozegar11-ship-it/Saeit/pull/1614
- Messaging/marketing: https://github.com/mojtabarozegar11-ship-it/Saeit/pull/1577
- Factory quota probe: https://github.com/mojtabarozegar11-ship-it/Saeit/pull/1613
- Permanent evidence ledger: https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1514
