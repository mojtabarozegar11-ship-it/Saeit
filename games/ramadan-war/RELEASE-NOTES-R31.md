# Ramadan War Web R31 — 2026-10-30

**Offline playable / READY_FOR_REVIEW; not merged, deployed, LIVE_VERIFIED or commercially released. MOJ1 disabled.**

## Gameplay repairs
1. Recovery intel inside a blocked tile now has a collision-safe approach within the real 0.78-unit auto-collection radius; adjacent walkable tile centres were previously 1 unit away and falsely failed.
2. Nearest reachable intel selection now includes legal pickup approaches and breaks equal grid-step routes by actual distance. Sealed routes remain blocked, not fabricated.

## Acceptance
Extract the standalone package; run `node --test qa/*.test.mjs` inside `ramadan-war`. Serve via `python3 -m http.server 8765` and open `http://127.0.0.1:8765/` on mobile/desktop. In local QA use `RamadanWarDebug.qaMission(2)` and verify pickup navigation, autosave and export/import. Node tests are not browser proof. No live payment, wallet or MOJ1.

**Release gate:** S-01 must prove safe quota, off-host backup/restore, rollback, browser QA, version and final live URL/hash before public release. This branch is review-only.
