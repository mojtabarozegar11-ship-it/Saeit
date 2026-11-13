# Single-bot coding-first completion contract — 2026-11-13

## Identity and code already gathered in this integration branch

- **Exactly one public/runtime identity:** `mojtaba.bot.ai` / `mojtaba-bot-ai`.
- Existing `ava_core.MojtabaBot`, owner-scoped goals/memory and approval
  boundaries are preserved. Existing economic/factory task management is not
  replaced, disabled or deployed.
- Signed-scope **offline** cyber evidence, origin and incident modules have
  been included from PR #2259. Their gateway tools require the exact canonical
  Agent code and are disabled until separately authorized.
- The richer multi-strategy **demo-only** cBot from PR #2257 is included,
  with a net6.0 package contract from PR #2262 and a separate research-only
  backtest from PR #2260.
- The existing cBot build workflow is deliberately **manual-only** while coding
  is incomplete. The source has not been compiled or runtime-verified here.

## Source gaps required before any '100% coding complete' statement

1. The isolated source self-upgrade verifier and private repair producer
   from PR #2252 are integrated with independent source/candidate hash checks.
   The remaining VPS evolution state reader and canonical task/approval
   identity mapping still require reconciliation before completion.
2. Nine source/fleet groups need explicit canonical routing and a verified
   no-duplicate-worker design. Legacy agent rows must retain audit history.
3. Connect authenticated Django owner sessions, canonical chat runtime, and
   immutable request/approval evidence to the same capability hub.
4. Complete all product, content, research, agriculture/factory, commerce,
   customer communication, game/Moj Coin and trading adapters without starting
   standalone bots, duplicate schedulers or new public dashboards.
5. Unify trading cBot and research signal parameters; add durable trade
   idempotency and portfolio/broker risk state before any live authorization.
6. Maintain payment, email, public publishing and expense default-deny
   policies. No expenditure without explicit single-action owner authorization.
7. Provide a bounded full-code acceptance inventory, independent code review,
   source provenance, and intended runtime topology before final QA begins.

**Coding completion is not 100%**. Source imports, PR merges and green CI
cannot substitute for implemented adapters and end-to-end commercial behavior.
Do not use the number of files or GitHub commits as completion percentage.

## Explicit exclusion for this coding phase

No manual testing, real/demo broker operation, cPanel/VPS deployment,
financial action, emails, deletion, site redesign, or independent agent
provisioning is authorized by this integration commit.

## Source-only hardening imported in coding phase

Private source changes must be verified by an independent dossier inspector; a producer's own success flag is insufficient. The existing master economic self-improvement handler now reopens the report and compares candidate and source hashes before claiming a verified internal effect. There is no promotion to the live codebase, no new scheduler and no automatic deployment.

## Signed cyber gateway source wiring

`build_economic_gateway` now exposes optional, disabled-by-default signed cyber handlers through the **existing** Django `ToolGateway`. A host-owned verifier key and explicit `enable_cyber_offline` flag are both required for handler activation. Each handler is further restricted to `mojtaba-bot-ai` and an authenticated AgentTask. The canonical agent capability definitions have been included in the existing seed catalog. No keys, users, services, tasks, host processes or payments were provisioned by this commit.

## Canonical module mapping

The three signed cyber actions now map to the internal `cyber_security` lane in the existing unified identity catalog. Any unknown capability remains unmapped and requires human review rather than being silently treated as executable.

## چرخهٔ بعدی: حالت VPS و هویت واحد

- موتور وضعیت خودارتقایی از شاخهٔ سخت‌گیری شواهد گرفته شد و سابقهٔ کارهای انجام‌شده، هش وظایف و cursor مستقل از `verified_effect` ساده بررسی می‌شود.
- در جابه‌جایی از `economic-master-agent` به `mojtaba-bot-ai` پروندهٔ وضعیت قدیمی بدون تطبیق رد می‌شود؛ هویت جدید فقط با تاریخچهٔ مستقل خود پذیرفته می‌شود.
- حضور هم‌زمان شناسهٔ canonical و شناسه‌های اقتصادی/کارخانه‌ای قدیمی در انتخاب runtime متوقف می‌شود.
- افزایش عمق اجرای ترتیبی از ۱ به ۲۰ فقط با دست‌کم دو اقدام جدید، مستند و دارای تنوع پذیرفته می‌شود؛ این تغییر خودبه‌خود مجوز هزینه، استقرار یا معامله نیست.
- **این فقط Commit کد است:** هنوز آزمون، اجرا روی VPS، مهاجرت وضعیت و استقرار انجام نشده است.

## Identity and replay execution guards

The existing `core.unified_bot_identity` now exposes a single-executor assertion across `mojtaba-bot-ai`, `economic-master-agent` and `moj_1ro_1`. It is called before a task is claimed and again before an authorized tool executes, so overlapping active Django executor rows refuse work rather than operating in parallel. Stale-running legacy executor tasks no longer auto-requeue without reconciliation, preventing accidental duplicate side effects. This is an in-process/DB-row gate, **not** evidence of a singleton across unknown VPS cron/systemd or PHP workers.

## Precise owner approvals — coding phase

Existing task acceptance now checks the original request's action, target task id and approved risk against the active task snapshot. The approval service denies a missing/deleted task, a mismatched action or insufficient risk and a forged/absent owner identity. The same validation is applied again when TaskRuntime claims work and when ToolGateway invokes the capability, including higher-risk tool adapters. This is source-only and has not been executed against live data; commercial/external action gates remain closed by default.

## Retried execution is never assumed safe

For all three recognized executor IDs, errors during an active task no longer place it back into a runnable queue automatically; they leave a blocked task and preserve the previous execution identity for manual reconciliation. This includes errors after a tool reported a side effect but before `TaskRuntime.complete` persisted the result. Both heartbeat and completion now recheck the canonical/legacy singleton before confirming a running task. A stopped execution is not proof of rollback, and approval of a retry must be narrowly scoped.

## Auditable coding worklist (a subset, not whole-bot readiness)

**Implemented in the open Draft branch, not validated in operation:**

1. [source staged] VPS evolution state explicitly binds its economic runtime code and will not silently migrate an existing legacy ledger.
2. [source staged] Canonical/legacy active executor singleton rechecked at task claim, heartbeat, completion and tool invocation.
3. [source staged] Approval decisions and task invocations bind requested action, task ID, allowed risk and the active designated owner.
4. [source staged] On uncertain tool failure, all known master/factory executor tasks block pending reconciliation instead of automatic replay.

**Remaining code and integration, before whole-bot QA:**

5. [not complete] Authenticated canonical chat/goal runtime connected to durable task and audit state.
6. [not complete] Full games/Moj Coin, products and commerce, customer communication and research capability adapters mapped and coded under one dispatcher.
7. [not complete] All pending self-evolution, runtime state, scheduling and fleet disposition dependencies reconciled with canonical identity.
8. [not complete] Branch conflicts with main and overlapping PR sources reconciled without overwriting live website templates or newer changes.

This **4 of 8 source milestones** inventory is limited to the explicitly named
milestones above. It is not a percentage of all source lines, all capabilities,
QA acceptance or commercial completion. A source-staged milestone is NOT an
assertion that code runs correctly; owner requested acceptance testing later.

## Canonical chat approval flow (coding-only)

A chat command is now **pending** even when entered by a Django superuser. The durable approval binds the existing ChatSession ID, requester, operation ID, action, exact risk tier and an allowlisted target/parameters contract. The existing Approvals API requires a separate owner decision, followed by an explicit `execute-chat` call. No duplicate scheduler or dashboard was added. The existing one-shot executor rejects ambiguous outcomes and prevents automatic replay. Source is not acceptance-tested or deployed.

## Authenticated conversation composition root — source only

The existing Django `MasterAgentChat` now invokes `core.canonical_chat_bridge.respond_with_mojtaba_runtime` for non-operational conversation. The bridge instantiates `ava_core.MojtabaBot` for this authenticated request, injects the existing host-owned model provider, and reads **only** the current user's bounded ChatSession history. Persistence remains in the existing Django ChatMessage table. Operational commands remain separately approved ChatOperations; no new Django agent/worker/queue or additional public bot identity is created. External model use requires `MOJTABA_CHAT_EXTERNAL_MODEL_ENABLED=1`; a key alone is not authorization. This code is untested, unmerged and undeployed. This is request-scoped composition, NOT proof of one globally running VPS process.

## Conversation tenant isolation and usage bounds

The request-scoped canonical bridge now re-verifies the ChatSession ownership in Django before any model usage and refuses external model calls for non-superusers. Historical context is bounded to 12 prior chat messages and a response token ceiling. External-provider use remains disabled by default, and any future billing policy must be reviewed before turning it on; no actual provider call was initiated in this coding cycle.

## Cycle 7 — canonical owner for new managed tasks

New tasks planned through the existing `master-chat/plan` endpoint require an authenticated active superuser. `MasterAgent` chooses only the single active `mojtaba-bot-ai` Agent row with the explicitly registered capability, not a lowest-risk legacy Agent from the global registry; it refuses simultaneous canonical/legacy runtime rows. High-risk task approval requests bind to the authenticated requester (or the validated active designated project owner for internal uses). Non-dictionary payloads are rejected. This is code only; no tasks were queued on a live server, and no tests or model/provider calls were run for this commit.

## Cycle 7 — release boundary and draft integrity

The existing ChatOperation intent does **not** authorize `cpanel.deploy_release` for an unspecified Git SHA. This path now refuses requests at the chat layer, approval allowlist and executor; immutable release identity, signed manifest and a separate per-case owner approval are prerequisites for future work. The existing website/template remains unchanged. The MojPlayWin draft update action now targets existing draft records only; it will not demote or mutate a published page record by changing its `state`. API planning returns a safe conflict on canonical-runtime misconfiguration. No live deployment, payment, email, chat provider billing, tests or DB migration was executed in this cycle.

## Cycle 8: Fail-closed autonomous task replanning

The existing autonomous loop previously created new inferred prerequisite AgentTask rows following a handler failure, including cases where the previous task could have applied a side effect. The speculative-replan branch is now removed, all blocked canonical tasks pause the loop, and max-steps is constrained to 1..20. On failure the original task remains under TaskRuntime reconciliation and no new task is auto-created. Source only: no worker started, no tests or deployment.

## Cycle 8: Multi-domain portfolio source adapter

The internal `business_portfolio_review` operation is now wired to the existing unified `ToolGateway`, task seed registry, canonical module map, fleet audit and economic worker. It reads aggregate rows from eight existing Django domain groups (research, knowledge, catalog, commerce, content/SEO, newsletters, MojPlayWin local records and canonical factory task receipts). For games and trading it reports missing independent runtime evidence, not invented zero counts or certified profitability. No customer data, private email, wallet addresses, site publication, or revenue sums are emitted. All domains are read-only and approval gates for other operations remain unchanged. This is *source staged*, not acceptance-tested, deployed or verified against real Django tables in this cycle.

## Cycle 9 — source-only Moj Coin and trading identity inventory

`core.domain_source_attestation.inspect_domain_source` now supplies an allowlisted, bounded, symlink-denying SHA256 **local source inventory** to the two formerly unmapped `business_portfolio_review` domains. Game sources in this public repository are old Living Cities release scripts rather than the private actual game runtime or Moj Coin transaction engine. Trading sources are the existing demo-only cBot, csproj and risk boundary README; their presence does not prove compilation, broker connection or profitable trades. The new adapter does not make broker/API calls, execute untrusted shell, activate game tokens or publish assets. Portfolio reports distinguish **8 Django count domains**, **2 source inventory domains**, and **0 externally attested runtimes**. Source hashes are freshly computed observations, NOT independently pinned supply-chain signatures. No integration tests or deploy were performed.

## Cycle 9 verification-effect correction

A source-only `business_portfolio_review(domain=games|trading)` must return `verified_effect=False` even if all allowlisted local source files can be hashed; source existence alone is NOT an operational or commercial result. For a request encompassing a Django row-count domain the old `verified_effect` semantics of that internal read remain, but no game run, trade or settlement is certified. The audit payload explicitly marks `source_only_no_operational_credit` so aggregate reports cannot mistake source inventory for execution.

## Cycle 10 — uncertain-effect barrier across owner approvals and task execution

A previously attempted `blocked` task cannot be released or cancelled through an ordinary Owner Approval decision. An independent outcome-reconciliation workflow is required; the approval transaction rolls back instead of requeueing. The single master/legacy task registry now records `requires_review=true` on ambiguous terminal failures (including exhausted retry budget), and an unresolved-effect barrier is checked both before task claim and immediately before tool invocation. Historical tasks are not silently deleted or retried. The new barrier is source only; previous unknown effects and live VPS schedulers were NOT inspected, and no new reconciliation API was activated.
