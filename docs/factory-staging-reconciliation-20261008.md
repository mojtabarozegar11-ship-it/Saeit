# Factory staging reconciliation — 2026-10-08

This branch is a **review-only reconciliation workspace**, not a deployable release.
The live staging working tree is ahead of this GitHub branch. Do not merge or deploy
without comparing the staging files and migration history.

## Verified on staging (earlier controlled execution)

- Stage-1 discovery handed off two independent opportunities.
- Two FactoryRuns completed `product_research`, `product_opportunity_score`, and `product_validation` with verified effects.
- Both runs stopped at bounded re-research for lack of a new independent source.
- Staging code patches were syntax checked and backed up:
  - `core/opportunity_discovery.py`: deduplicate evidence URLs.
  - `core/self_hosted_research_provider.py`: bounded fetching, HTML extraction, relevance filtering, Stage-1 URL handoff, and fresh-source search on validation retry.
  - `core/autonomous_brain.py`: new opportunities do not inherit unrelated blocked runs.
  - `var/factory/operations/factory_tick_boot.py`: Stage-2 uses the real provider instead of the static feed override.
- Paid LLM disabled. Publication and payment remain owner-gated.

## Required before any merge or deployment

1. Obtain **read-only** staging snapshots of the four files and compare with this branch. Never overwrite staging with older GitHub versions.
2. Compare migrations and Django settings. Server migrations were observed through 0048 while older GitHub main was at 0039.
3. Run isolated tests for discovery dedup, HTML cleanup, direct evidence handoff, retry independent-source discovery, and new-run isolation.
4. Ensure discovery uses topic-relevant independent publishers; the Stage-1 cron bootstrap still uses a fixed fallback feed and is not genuinely dynamic.
5. Ensure Stage-2 validation re-research produces independent **new** evidence, or fails closed. Never fabricate scores or bypass gates.
6. Inspect the two blocked FactoryRuns and retry budgets **before** any owner-authorized recovery; do not automatically reset blocked tasks.
7. Check 18 lifecycle stages against persisted task effects; a seeded Agent record count is not proof of stage completion.
8. Verify staging worker/cron logs, site health, security gates, approval boundary, and checkout end-to-end before any production promotion.

## Explicit non-goals

No live deployment, database mutation, production payment activation, fake evidence,
blocked-run reset, or claims of autonomous 24/7 sales are authorized by this file.
