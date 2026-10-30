# R42 browser acceptance — S-01 (not yet passed)

1. Extract ZIP; run a local HTTP server from ramadan-war, then test desktop 1280x800 and mobile 390x844. Do not use file://.
2. Start a campaign, pause, export backup, paste valid code, confirm successful restore clears hidden textarea and the campaign remains playable.
3. Invalid code must leave the original campaign unchanged. Close via Escape and via button; verify code erased and keyboard focus returned to opener.
4. Tab and Shift+Tab must remain within the private dialog; on pagehide/back-forward cache verify code is cleared.
5. Verify joystick, touch aim/fire, map, offline model loading and no uncaught errors; capture CI artifact and exact source SHA.
6. No S-01 deployment until off-VPS backup, verified rollback, CI and live URL are evidenced. MOJ1 remains disabled.

Local Chromium attempt: ERR_BLOCKED_BY_ADMINISTRATOR. This is a test blocker, not a pass.
