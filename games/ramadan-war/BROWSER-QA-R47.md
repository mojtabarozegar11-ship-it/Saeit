# G-01 R47 browser QA handoff — not a live release

- Predecessor R46 exact-head GitHub Actions run `41085753459`: all `model-and-browser-qa` steps successful, including desktop/mobile gameplay, GLB texture load and ZIP artifact upload.
- R47 local Node gameplay regression: 134/134 PASS; ZIP manifest and CRC separately checked.
- R47 browser acceptance: PENDING. Local Chromium attempt did not yield an authorized playable browser session; no local browser PASS claimed.
- Required: GitHub exact-head R47 desktop+mobile gameplay, pause/resume, wall-face block, diagonal corner clearance, joystick, backup export/import, offline refresh, MOJ1 disabled. Then S-01 independent backup/restore/rollback and live verification.
