# Ramadan War Web R39 — offline review candidate

Main fixes:
1. Three bounded, persistent aim-sensitivity levels (low/normal/high) scale both horizontal and vertical pointer aiming. The default preserves R38 behavior.
2. Restore a previously exported campaign backup from the Pause menu, reusing the existing size/format validation, confirmation, conflict detection, and rollback path.

Rotation: Crown Defender now tracks individual pointer IDs on mobile controls, rejects secondary presses and releases controls on pause; Super Jungle Run (Roham) suspends on window blur and does not treat Space on a focused modal button as a jump.

S-01 independent assist: offline SKU-specific direct checkout guard, excluding register-next false positives and rejecting wrong-SKU, cross-origin, duplicate, and query-bearing direct CTAs. No site source was edited by G.

Local acceptance: `node --test games/ramadan-war/qa/*.test.mjs` (102/102 in isolated extracted R39 package) and `python3 -m unittest games/g01-handoffs/test_g01_s01_direct_checkout_guard_r39.py` (7/7 locally). Browser/mobile acceptance remains pending on exact PR head.

Run `python3 -m http.server 8765` from `games/ramadan-war`; visit http://127.0.0.1:8765/ and verify Pause > Aim sensitivity and Pause > Restore from file, persistence across reload, malformed backup rejection, and 2-finger aiming/fire on a real phone. Crown/Roham require separate mobile and keyboard regression.

**Status: CODE / READY_FOR_REVIEW only.** No public deployment, production purchase, payment, wallet or MOJ1 activation. S-01 alone owns release after independent backup/restore/rollback and legal gates. Factory VPS/master-agent HOLD is unchanged.
