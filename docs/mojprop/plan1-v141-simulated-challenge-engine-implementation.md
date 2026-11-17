# MOJ-PROP-01 — v1.4.1 Simulated Challenge Engine / Technical Handover

**Reviewed as of:** 2026-11-17. **Scope:** proposed 30 native TRX Plan 1 *prop challenge*, NOT `MOJPROP-STARTER30` educational reporting. **Status:** Source-only deterministic demo engine; **NO PAID ENROLLMENT / NO REAL TRADING / NO DEPLOYMENT**.

## Deterministic challenge rules

- The v1.4.1 *unsigned buyer draft* is bound by the exact SHA-256 from `plan1_v14_social_or_50_terms.py`. Former signed contracts are never silently updated.
- Two strictly sequential **SIMULATED** stages in one 28-day evaluation window, starting from the independently trusted initiation timestamp only **after** lawful and settled enrollment (not yet implemented).
- Stage 1 realized net-profit goal **9.6% of USD 100**, stage 2 **6% of USD 100**. Each phase resets its own simulated starting equity to **USD 100**; real capital is never assumed.
- Each stage must have at least **6 UTC dates containing a fully closed, uniquely identified, reconciled position**, with a total of **50 distinct fully closed positions across both phases**. Multiple fills of the same position count once, but realized partial-fill P&L and fees are summed; conflicting final-close or event IDs cause a hold.
- Best profitable UTC day may not exceed **32% of the stage's verified realized net P&L**. UTC is a mathematical convention only until the permitted simulator's contractually binding trading-session timezone is validated.
- Every verified equity mark is checked against a daily breach floor of **day-opening equity − USD 4** and an overall floor of **USD 92**, inclusive of floating loss. Breach is sticky: even if equity subsequently recovers, math qualification is rejected.
- The first stage requires an explicit acceptance timestamp before stage 2 may begin; both transitions and every fill/mark must fit the correct chronological interval. No phase or source can self-promote from a browser boolean.
- Stage-opening equity must equal **USD 100**, stage-closing equity must reconcile to **USD 100 + aggregate verified realized net P&L**, the closing mark must follow the last position close, and position/equity source labels must agree. At stage-one acceptance, a SEPARATE canonical SHA256 of the entire stage-one close/equity event history is frozen in the proposed v1.4.1 journal. **At valid stage-two completion, a separate SHA256 freezes its complete closed-fill and equity history. A subsequent signed snapshot cannot rewrite it, even without changing total profit. Finishing stage two requires all 50 unique fully closed positions in total, both stages' passing math, and no conflicting/unreconciled evidence.** Later snapshots may update stage two, but modifying any accepted stage-one event (even if net profit is unchanged) is rejected; recording stage-one approval with a bad/unreconciled source is rejected.
- Proposed XAUUSD risk **prior to an individual DEMO order**: at most **USD 3** single and **USD 8** aggregated nominal loss-at-stop (including spread, slippage and round-trip fees), with tighter prospective **USD 4 daily / USD 8 total drawdown headroom**. Lot step, stop distance, margin sufficiency, quote age and latest phase equity must pass; additionally, unreconciled events, conflicting IDs, wrong source and opening/terminal equity mismatch block even a demo-order mathematical review. NO order is submitted by this module.
- **Social condition is a separate 672-hour clock:** at least one original compliant post on EITHER Instagram OR Facebook, continuously public for at least 28 days. Even passing both demo stages may only produce `TRADING_MATH_COMPLETE_WAITING_SOCIAL_CLOCK` until a prospective mathematical social review is supplied. A self-reported post is NOT platform-verified, and legal review of mandatory financial endorsements is still required.

## Source modules (pure review core plus separate transaction-locked, NOT-DEPLOYED Django adapter)

1. `prop_firm/plan1_v141_simulated_challenge_engine.py`: `SimulatedClosedFill`, `SimulatedEquityMark`, `EngineSnapshot`, `replay_simulated_challenge` and immutable phase/challenge decisions. Over-5,000-event snapshots, inconsistent terms, non-finite/float values and invalid timezones are rejected.
2. `prop_firm/plan1_v141_demo_order_risk_review.py`: `review_v141_demo_order` bridges an exact v1.4.1 challenge to the previously vetted **v1.3 mathematical XAUUSD preflight only**. Neither module performs real/broker/demo execution.
3. `prop_firm/plan1_v141_signed_simulator_manifest.py`: `verify_and_replay_signed_simulator_manifest` accepts one bounded JSON ledger authenticated with a configured, server-owned HMAC key. It binds the exact schema, source ID, key ID, manifest ID, monotone sequence supplied from a **separate durable registry**, current time, challenge reference and contract fingerprint before replay. A valid HMAC verifies the configured sender of exact bytes — **NOT underlying broker identity, correctness/completeness of fills or legal funding**. It also rejects freshly signed reports with assessment timestamps older than 10 minutes. Keys are never committed.
4. `prop_firm/plan1_v14_social_or_28d_review.py`: independent, claim-only mathematical social-post age/visibility checker; no Meta login, scraping or auto-post.
5. `prop_firm/plan1_v14_private_interest_review.py` and `plan1_v141_precontract_boundary.py`: precise buyer-information consent and draft contract digest matching, NO personal data storage, payment or enrollment.
6. `prop_firm/plan1_v141_replay_journal_policy.py`: pure monotone, nonpayable receipt-chain and phase-transition policy; genesis, stage-one acceptance, phase-two start/completion, terminal states and timestamp history are immutable.
7. `prop_firm/plan1_v141_persistence_models.py` and `migrations/0009_v141_sim_replay_journal.py`: two NEW isolated Django audit tables; old v1.2 buyer schema remains unmodified. `prop_firm/models.py` has only a model-registration import appended. **Migration source is committed but NOT applied to a database and has NOT been transaction-tested on MariaDB.**
8. `prop_firm/plan1_v141_atomic_receipt_service.py`: server-internal `@transaction.atomic` + `select_for_update` receipt writer with unique (challenge, sequence) and (challenge, manifest ID), authenticated HMAC, strict next-sequence and stable idempotent prior receipts. A challenge row must already be provisioned privately from a lawful customer purchase; the intake cannot create a challenge or customer. **No HTTP endpoints or credentials are included.**

## Review-only usage

At repository root, with Python 3.11:
```bash
PYTHONDONTWRITEBYTECODE=1 python3.11 -B scripts/mojprop_xauusd_v13_full_review_suite.py
```

The current Python 3.11 suite inventory is **194 v1.3 + 361 v1.4.1 + 39 historical = 594**. Additions include 73 two-phase engine tests, 28 gold risk review tests, 33 signed-manifest/freshness tests, 64 executable pure journal-transition tests and 24 source-compilation/static migration safety checks. **[594/594 tests successfully executed on exact source SHA](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44128340660)** `f96964aaafa409c0179416296e4d612692ea0a4d`: 0 failures, 0 errors, status `UNIT_TESTS_PASS_NOT_RELEASE`. The Django checks DO NOT instantiate a database or execute the migration; multi-process concurrency remains unverified.

**Do NOT run any test sample as a real brokerage order or payment request.** Success is reported as `UNIT_TESTS_PASS_NOT_RELEASE`. No browser-facing POST endpoint or payment button is created.

## Required integration steps for actual commercial operation (NOT yet achieved)

1. Obtain legal authorization for merchant, jurisdiction, buyer eligibility, marketing obligation, KYC/AML and lawful refund/withdrawal rights; sign immutable buyer-specific **v1.4.1 final** terms.
2. Build a uniquely allocated 30,000,000 SUN native-TRX invoice backed by owner-approved wallet custody. Verify settlement server-side, deduplicate chain transactions, handle confirmations/reorgs and record refund rights. **Do not** activate a challenge before settlement.
3. Run and validate the NEW isolated `0009_v141_sim_replay_journal` Django migration on a backed-up, capacity-approved separate development database; prove migration rollback, concurrent row locking and receipt uniqueness against the actual MariaDB version. This new audit journal does **NOT** replace or migrate existing `PropChallengeEnrollment`/funded accounts/social tables: their v1.2-specific constraints still need an explicitly reviewed v1.4.1 commercial enrollment integration, without altering any historical buyer terms.
4. Supply a real authorized **SIMULATOR** that owns a complete signed fill/equity event stream (including all trade/mark gaps, UTC vs broker session calendar and flat account state), plus a full immutable externally archived original raw manifest for every SHA256 receipt. The new journal stores metadata hashes only; without original archives **audit replay and disaster recovery are impossible**. Server-only keys and approved publisher identity are mandatory. An HMAC on buyer-provided JSON is NOT proof.
5. Reconcile stage acceptance and terminal equity via a trusted backend and persist decision hashes. Stage 2 must be unlocked only after stage 1 is independently passed. A mathematical green result must NOT itself activate brokerage.
6. Verify one original Instagram **OR** Facebook post after 672h with actual lawful, independent reviewer evidence. Permit no forced unlawful financial promotion.
7. Establish independent actual USD 100 company liquid capital, lawful third-party account permissions from LiteFinance, safe risk enforcement and **real off-host recoverable full backups**, including rollback and 24/7 incident operations, before any live broker stage or payout.

**Current hard blockers:** No substantive broker authorization, no proven USD 100 reserve, no lawful signed final buyer contract, no production-grade 30 TRX settlement/enrollment, no independently verified live simulator stream, untested MariaDB migration/atomic persistence, and no verified immutable original event archive, no verified legal social-post compliance, no independently restored full database/app backup. Therefore this repository branch is an implementation artifact, **not a commercially deployed service**.

## Financial safety invariant

Every decision from these modules remains:
`checkout_enabled=false`; `paid_enrollment_authorized=false`; `real_broker_orders_authorized=false`; `payout_authorized=false`.
Only separately reviewed, lawful, independently proven external services may eventually change operational permissions. Do not remove these safeguards or bypass protected workflows to force a green release.
