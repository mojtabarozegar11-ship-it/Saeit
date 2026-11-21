# Ramadan War Web — G-01 R29 (2026-10-30)

**Status:** Offline playable review candidate; CODE / READY_FOR_REVIEW. NOT MERGED, NOT DEPLOYED, NOT LIVE_VERIFIED. MOJ1 disabled.

## Two gameplay corrections
1. During the intel-recovery mission, arriving within the actual 0.78-unit automatic pickup radius hides a stale direction arrow and displays a truthful automatic-collection hint. The player is not asked to press an interaction control that does not apply.
2. A missing target is no longer automatically labeled "objective completed": the boss-not-spawned, missing-recovery-intel, and remaining-enemy-quota cases each have distinct guidance. The true completed state remains unchanged.

## Evidence and release gate
Local extracted R28-to-R29 ZIP passed 62/62 Node regression checks, JavaScript syntax checks, archive CRC and per-member SHA-256 readback. R28 GitHub browser CI [40962082827](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40962082827) was independently checked and completed SUCCESS. R29 browser CI must be independently checked at exact head; local Chromium navigation was blocked by administrator policy, not counted as a pass.

Extract offline preview and serve from `ramadan-war/` using `python3 -m http.server 8765`; use desktop WASD/mouse and mobile joystick/aim/fire. Verify mission 3 pickup, mission 6 pre-boss HUD, campaign backup import/export and pause/resume.

S-01 alone owns deployment. No public release without verified off-host restore, production disk health, rollback, staging and live smoke. No payments or wallet connection.
