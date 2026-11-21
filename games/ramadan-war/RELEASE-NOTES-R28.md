# Ramadan War Web — G-01 R28 (2026-10-30)

**Stage:** Offline playable review candidate; NOT MERGED, NOT DEPLOYED, NOT LIVE_VERIFIED. MOJ1 disabled.

## Two gameplay fixes

1. Activation/extraction arrival within the same 1.35-unit range used by interaction no longer points away from a reachable action. Extraction retains the outstanding enemy quota instead of falsely promising readiness.
2. Defense hold within the same 2.5-unit zone used by the mission timer now instructs the player to hold position rather than showing a redundant waypoint. Arrival suppresses the directional arrow for assistive technologies.

**Verification:** Local extracted R28 package: 57/57 Node tests and JS syntax pass. Browser smoke is not yet verified locally (Chromium policy blocks localhost). Exact-head CI and independent S-01 backup/rollback/space checks remain mandatory before any live release. No payment, wallet or token transfer.
