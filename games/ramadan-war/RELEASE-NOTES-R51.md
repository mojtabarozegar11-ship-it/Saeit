# G-01 R51 — 2026-10-31 — offline playable, not deployed

Primary: joystick now rejects non-finite pointer coordinates and collapsed touch-pad geometry; bounded movement radius and fail-closed reset of held axes. 8 new Node tests; local Ramadan suite 157/157 PASS.

Rotation A: Crown Defender canvas pointer input rejects non-finite/zero-size geometry before capture; invalid active drag releases aim. Rotation B: Taniya Cake Maker saves bounded local-only frosting/topping/candle draft in sessionStorage and clears on reset. These source changes remain review-only.

HELP G→S: R51 offline ZIP gate verifies SHA-256 runtime manifest, disabled MOJ1, ZIP CRC, bounded uncompressed size/entry count, no symlinks, offline entrypoint and expected manifest format; 8/8 local fixture tests PASS.

R50 exact-head GitHub Actions 41118857469 SUCCESS with real desktop/mobile gameplay. This is NOT R51 browser verification. R51 local Playwright Chromium blocked before navigation by ERR_BLOCKED_BY_ADMINISTRATOR. Await exact-head CI and S-01 backup/rollback/source-provenance gates. Factory/master-agent HOLD; no remote writes, merge, deploy or payment.

Source branch: games/g01-r51-joystick-geometry-crown-taniya-20261031. PR #1672. Offline ZIP SHA-256 d0dea1b3ab5bcb8fd4695fea6f0eb4a51bd7c69d1804f8b48b717d02e96d123e (111 entries); recover from owner-held artifact or rebuild from this branch, do not assume the ZIP is publicly hosted.
