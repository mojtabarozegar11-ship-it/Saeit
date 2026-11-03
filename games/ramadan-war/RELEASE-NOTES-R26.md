# G-01 R26 | Ramadan War objective navigation and action radius | 2026-10-29

**Status:** CODE / READY_FOR_REVIEW. Not merged, deployed or live verified. MOJ1 remains disabled.

- Objective HUD now routes to the first walkable waypoint on a bounded 16x16 grid rather than through walls; unreachable target reports blocked route.
- Objective interaction button uses the same 1.35-unit radius as the actual handler, eliminating the visible-but-rejected action gap.
- Added seven focused regression tests in `qa/r26-navigation.test.mjs`; local R25+R26 archive checks: **50/50 Node tests PASS** and JavaScript syntax PASS.
- Updated deployment ASSETS, preview dependency audit and guarded SSH stage file contract to include `objective-navigation.mjs`. Initial exact-head CI [#40943825190](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40943825190) failed because the guarded stage list initially omitted the new module; this has been corrected in commit [699f652](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/699f6521980d59ad117b0cbdd0a4876e61daabae).
- Offline review ZIP: `ramadan-war-g01-r26-navigation-playable-20261029.zip`, **54 entries**, SHA-256 `fb21b125791b2fce142ec8a514b30a78a102077f2d60d3b4d26ed4e3b327a70f`; independent extraction and manifest validation PASS.
- Local Chromium was blocked by administrator policy (`ERR_BLOCKED_BY_ADMINISTRATOR`). Do not claim browser QA until the new exact-head GitHub Actions run is successful.

**S-01 release gate:** production VPS disk/IO recovery, independent off-host backup restore, reproducible pinned SSH relay, rollback and browser smoke on the exact release artifact. No public deploy/merge by G-01.

**Next:** inspect exact-head CI and deliver verified ZIP/manifest to S-01 for gated review. Next rotation: Air Supremacy and ECHOFORM; then Crown Defender and Roham/Taniya.
