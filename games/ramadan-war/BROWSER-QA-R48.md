# G-01 R48 browser QA handoff (NOT a live release)

- Predecessor R47 exact-head GitHub Actions run 41094630957: SUCCESS, including desktop/mobile gameplay, GLB texture loading and standalone ZIP artifact.
- R48 local Node gameplay regressions: 139/139 PASS; R48 CRC and SHA-256 manifest verified.
- R48 local Chromium: BLOCKED by ERR_BLOCKED_BY_ADMINISTRATOR for file:// and localhost; no browser pass claimed.
- Required exact-head CI: desktop+mobile gameplay, save restore from radius-clipped legacy position, normal saves, pause/resume, joystick, backup import/export, offline refresh, MOJ1 disabled.
- S-01 gate: independently verified off-VPS backup and restore, rollback, staging, live URL and site health. Do not merge/deploy before gates.
