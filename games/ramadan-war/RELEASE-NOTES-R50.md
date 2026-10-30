# Ramadan War R50 — offline playable review candidate (not live)
Date: 2026-10-30. Owner: G-01. Factory/master-agent HOLD is unchanged.

## Primary game
- Bound desktop/touch aim deltas per pointer event (120 px default, 240 px hard maximum) and reject non-finite coordinates before changing camera/angle. A malformed move cancels click-to-fire eligibility.
- Clamp transient zero-size WebGL viewport dimensions to at least 1 px and reject non-finite device-pixel ratio.
- Added eight dedicated aim/viewport regression cases; updated obsolete R39 source-contract test. **149/149** local `node --test qa/*.test.mjs` pass; syntax checks pass.
- Exact prior R49 GitHub browser run [41111136308](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/41111136308) **SUCCESS**, including desktop/mobile GLB load and ZIP artifact. That success applies to **R49 only**; R50 browser QA is not yet proven.

## Rotations
- Air Supremacy: joystick rejects invalid pointer coordinates and zero-sized touch geometry rather than introducing NaN into flight controls.
- Roham Super Jungle Run: accessible Pause/Resume button and P keyboard shortcut, with RAF and jump blocked while paused and resumed with fresh frame timing.
- Rotation QA: `games/g01-qa/r50-rotation-gameplay.test.mjs`; separate game builds not yet live verified.

## S-01 independent assistance
- Read-only `games/g01-handoffs/g01_s01_r50_release_gate.py` checks ZIP CRC, all declared runtime SHA-256/byte counts, offline entrypoint, no remote script and disabled MOJ1 guards.
- Five synthetic fail-closed unit cases; never uploads, merges, deploys, pays or accesses the factory.
- S-01 owns staging/production release, rights, backups, rollback and URL verification.

## Acceptance status
- R50: CODE / READY_FOR_REVIEW offline, **NOT** MERGED, DEPLOYED or LIVE_VERIFIED.
- Local Chromium attempt blocked by `ERR_BLOCKED_BY_ADMINISTRATOR`; use exact-head CI real browser, then S-01 site-specific staging.
- Factory/master-agent remain HOLD; no write, restart, cron/systemd/worker or DB operations. MOJ1 disabled.
