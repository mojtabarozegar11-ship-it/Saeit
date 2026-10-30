# Ramadan War Web R38 — offline playable review build

- Corrected browser QA enemy count: renderer 3D mesh count previously overwrote simulation enemy count, producing the R36/R37 `4 !== 1` fixture failure.
- Solid-cover missile impacts no longer damage enemies through walls; normal airbursts retain prior AoE behavior.
- Added three R38 regressions; 99/99 local Node unit tests passed.
- ZIP integrity and 62 manifest SHA-256 entries verified offline.
- Local Chromium navigation blocked by `ERR_BLOCKED_BY_ADMINISTRATOR`; real-browser gameplay is **NOT VERIFIED** until exact-head CI and device acceptance.
- No merge, public deploy, live purchase, MOJ1 wallet or factory VPS write.
- Branch `games/g01-r38-cover-ci-mobile-20261030`; draft PR #1624; S-01 owns eventual backup/rollback and live release gate.
