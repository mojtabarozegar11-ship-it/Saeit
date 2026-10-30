# G-01 R46 browser QA checkpoint

- Local Chromium attempted with Playwright on 127.0.0.1:18765; `net::ERR_BLOCKED_BY_ADMINISTRATOR`. NOT A PASS.
- Local Node `qa/*.test.mjs`: 130/130 PASS, including radius-aware swept collision.
- R45 predecessor CI 41075894692 success; R46 exact-head CI still required.
- S-01 must verify desktop WASD wall sliding, mobile joystick diagonal corner sliding, pause/resume, offline save/restore, scene/HUD controls, and record exact SHA, URL, browser version, independent backup and rollback evidence.
