# Ramadan War Web R35 — objective arrival and extraction gate
Stage: READY_FOR_REVIEW (offline file is playable; public deployment is NOT verified).
- Same-grid-cell route guidance no longer reports arrival until the player is within objective distance; solid-goal interaction uses 1.35 world units, other goals 0.78.
- Extraction direction HUD now explicitly blocks interaction until the enemy quota is cleared.
- R35 adds five targeted regressions. Existing R34 83 tests remain in the suite.
- Rotation: Crown Defender single touch pointer ownership; ECHOFORM R35 Escape pause/resume.
- S-01 independent offline asset preflight handoff; no network, payments, factory, host or deployment writes.
Acceptance: node --test qa/*.test.mjs; node --check game.js; node --check tactical-map.mjs; S-01 must independently verify browser/mobile, backup/rollback, license and release before public deploy. MOJ1 remains disabled.
