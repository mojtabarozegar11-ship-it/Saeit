# Ramadan War Web R47 — offline playable review build

2026-10-30 | G-01 | CODE / READY_FOR_REVIEW; not merged, deployed or live verified.

## Gameplay correction

- Replaced the R46 square-corner player-footprint approximation with exact circle-versus-solid-tile intersection for the 0.21-tile player radius. The old square approximation blocked some safe diagonal passages beside wall corners even when the player circle had clearance.
- Kept the existing swept 0.16-tile movement substeps and independent X/Y wall sliding; solid wall-face contact remains blocked.
- Invalid or excessive radii fail closed without unbounded grid scanning. No save, payment, wallet, factory or public site changes.

## Verification

- Local `node --test qa/*.test.mjs`: **134/134 PASS**; four new circular-footprint tests (clearance, face collision, swept corner passage, invalid radii).
- Exact-head predecessor R46 browser CI **SUCCESS**: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/41085753459 (desktop/mobile gameplay with GLB loading and preview ZIP upload).
- R47 exact-head browser acceptance remains required; local Chromium could not complete the page navigation under administrator restrictions.
- Branch: `games/g01-r47-circle-input-s01-a11y-20261030`.
- Rotation A Crown Defender: paused/menu keyboard input guard; Rotation B Air Supremacy: paused gameplay key guard. Cross-assist S-01: static accessible label-association gate with 10/10 synthetic offline tests.

## Release boundary

MOJ1 and wallet payment remain disabled. S-01 owns any production release after independent off-VPS backup, tested restore, rollback, exact-head CI, desktop/mobile smoke and live URL verification. Factory/master-agent HOLD remains in force.
