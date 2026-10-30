# R43 browser acceptance (NOT PASSED)
1. Serve the extracted ramadan-war directory over 127.0.0.1 HTTP.
2. Desktop 1365x850 and mobile 390x844: start/pause and verify play, models, touch/keyboard controls, backup import/export and no JS errors.
3. Open the private backup-code dialog with nonempty text; blur the window, hide the tab, and restore from bfcache separately. Each must clear the code and announce why.
4. Verify Escape closes the dialog without resuming the game and Tab/Shift+Tab remains inside.
5. Do not claim PASS unless the actual browser run and exact artifact hash are recorded.
6. S-01 owns deployment after independently verified backup, rollback and exact-source review.
