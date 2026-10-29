# Ramadan War Web — G-01 R27 (2026-10-30)

**Stage:** Offline playable review candidate / READY_FOR_REVIEW. Not merged, deployed, live verified or payment-enabled. S-01 owns public release.

## Gameplay corrections
1. The objective HUD reports traversable grid-cell count on detours, not misleading shorter straight-line meters. Same-tile targets retain direct distance.
2. When a route is blocked, the misleading arrow is hidden and aria-hidden; the HUD explicitly states the route is blocked. Completed objectives also clear the stale arrow.

## Evidence and safety
- R27 offline ZIP: 56 files; SHA-256 `0513a773d94b664deb23aa2a7ed4c0be1c0e240fb80df44f7beee448b538db6e`; 53/53 local Node tests passed, JS syntax passed, archive extraction and per-file manifest verified.
- Prior R26 exact-head [CI #40944053871](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40944053871) succeeded including desktop/mobile Chromium. This does **not** establish R27 browser success.
- R27 browser QA local Chromium blocked by ERR_BLOCKED_BY_ADMINISTRATOR; exact-head GitHub CI must pass before release review.
- S-01 must independently verify off-host restore, disk capacity, pinned relay, rollback and live route. MOJ1 disabled. No public release or site layout changes.
