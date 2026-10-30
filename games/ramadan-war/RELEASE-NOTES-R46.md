# Ramadan War Web R46 — offline playable review build

2026-10-30 | G-01 | Not merged, not deployed, not live verified.

## Gameplay correction

- Player movement now has a 0.21-tile collision footprint on all four corners, rather than a single leading-edge tile probe. This prevents diagonal wall-corner clipping for both WASD and touch joystick.
- Large frame displacements are swept in at most 0.16-tile substeps, avoiding tunneling through walls; X/Y sliding remains possible along free corridors.
- Non-finite displacements are rejected. No save data, payment logic or site templates were changed.

## Verification and release gates

- Local `node --test qa/*.test.mjs`: 130/130 PASS; 7 new collision regressions.
- Local Chromium blocked by `net::ERR_BLOCKED_BY_ADMINISTRATOR`; this is NOT a browser pass.
- Predecessor R45 CI https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/41075894692 completed success.
- R46 branch `games/g01-r46-collision-roham-taniya-20261030`; rotations fix Roham runner JavaScript parse and Taniya cake SVG topping art. S-01 helper is offline/read-only.
- MOJ1 disabled; factory/master-agent HOLD; no deploy, restart, wallet/payment or public release.
- S-01 exclusively owns release after independent backup, restore, rollback and browser verification.
