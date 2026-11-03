# G-01 R24 — Ramadan War campaign switching safety (2026-10-29)

Stage: CODE / READY_FOR_REVIEW. NOT MERGED, NOT DEPLOYED, NOT LIVE_VERIFIED. MOJ1 disabled.

Player-facing changes:
- The home screen now warns when a playable in-memory campaign is at risk because browser storage failed or another tab changed the save. Warning includes explicit backup instruction and role=alert.
- Survival, New Game and Retry cannot silently replace the only in-memory copy. A saved campaign may enter Survival without a destructive prompt; Survival never modifies the campaign save slot.

Evidence: six new focused Node regressions in `tests/game/ramadan-r24-mode-switch.test.mjs`. The independent R24 ZIP from the prior R23 review bundle passed 39/39 local Node tests and SHA-256 manifest verification. Its standalone browser navigation was blocked by container policy; exact-head GitHub browser/mobile CI remains mandatory. Do not equate local ZIP with a deployed build.

Next: confirm exact PR head CI (including Chromium/mobile), obtain F-01 resource/SSH recovery and S-01 independent off-host backup/restore plus rollback. Only S-01 may deploy after explicit release gates and live SHA/URL verification.
