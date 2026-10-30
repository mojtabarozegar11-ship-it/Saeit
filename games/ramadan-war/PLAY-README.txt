RAMADAN WAR WEB R38 — OFFLINE PLAYABLE REVIEW BUILD (NOT LIVE)
Extract ZIP; cd ramadan-war; python3 -m http.server 8765; open http://127.0.0.1:8765/.
Desktop: WASD + mouse aim/fire; G interact; R reload; M radar; Esc pause.
Mobile: joystick + touch aim/fire; tactical radar toggle.
R38: accurate browser QA enemy count; cover-impact rocket blasts cannot penetrate walls.
Unit regression: node --test qa/*.test.mjs (99/99 local PASS).
Browser acceptance: GitHub Actions on draft PR #1624, followed by independent desktop/mobile test. Local Chromium navigation ERR_BLOCKED_BY_ADMINISTRATOR; no browser PASS claim.
MOJ1 and wallet payments disabled. Factory VPS/master-agent HOLD; no deploy, restart, payment or public publication.
Source branch: games/g01-r38-cover-ci-mobile-20261030
