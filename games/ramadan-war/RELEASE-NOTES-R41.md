# Ramadan War R41 — Offline review build, 2026-10-30

**User-facing changes**
- Home and Pause now accept a pasted JSON campaign backup code, using the same validated, rollback-protected import transaction as file restore. Invalid/oversized codes are refused without replacing the current save.
- When mobile clipboard permission and fallback copy both fail, the backup code opens in a selectable, accessible on-page field. No network transmission; text is erased when the player closes the panel.
- Recovery errors remain visible inside the manual dialog, including stale-tab/failed-write/failed-runtime restoration outcomes.

**Regression and release gates**
- Offline Node tests: campaign QA 109/109 passed on the attached ZIP source, including new R41 code-roundtrip checks and existing rollback transaction tests.
- R40 exact-head GitHub browser CI run 41037663792 completed successfully. R41 browser/device acceptance remains separate and unverified until its exact-head workflow passes.
- Air Supremacy: sortie completion now releases all held touch pointers before showing results. Crown Defender: pause, blur and hidden-tab transitions release captured canvas aim pointers.
- S-01 handoff: independent read-only desktop/mobile browser accessibility probe; explicitly scoped host, GET-only, no form submission, no customer credentials or payment.

**Stage:** CODE / READY_FOR_REVIEW only. No merge, deployment, live verification or public payment. MOJ1 disabled. Factory VPS/master-agent HOLD. Public release requires S-01 authorization, independent off-VPS backup and rollback evidence, browser/device QA and live URL verification.
