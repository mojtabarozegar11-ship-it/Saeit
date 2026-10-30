# Ramadan War Web — G-01 R27 (2026-10-30)

**Stage:** Offline playable review candidate / READY_FOR_REVIEW. Not merged, deployed, live verified or payment-enabled. S-01 owns public release.

## Gameplay corrections
1. The objective HUD reports traversable grid-cell count on detours, not misleading shorter straight-line meters. Same-tile targets retain direct distance.
2. When a route is blocked, the misleading arrow is hidden and aria-hidden; the HUD explicitly states the route is blocked. Completed objectives also clear the stale arrow.

## Evidence and safety
- R27 offline ZIP: 57 files; SHA-256 `f5c155b740aa5bf36ddaacf97abf9eb5a7327beb328201846cdedc9b108160cb`; 53/53 local Node tests passed, JS syntax passed, archive extraction and per-file manifest verified.
- Prior R26 exact-head [CI #40944053871](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40944053871) succeeded including desktop/mobile Chromium. This does **not** establish R27 browser success.
- R27 browser QA local Chromium blocked by ERR_BLOCKED_BY_ADMINISTRATOR; exact-head GitHub CI must pass before release review.
- S-01 must independently verify off-host restore, disk capacity, pinned relay, rollback and live route. MOJ1 disabled. No public release or site layout changes.
