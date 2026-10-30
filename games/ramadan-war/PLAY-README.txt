RAMADAN WAR WEB R48 — OFFLINE PLAYABLE REVIEW BUILD (NOT LIVE)
Extract ZIP; cd ramadan-war; python3 -m http.server 8765; open http://127.0.0.1:8765/.
Desktop: WASD + mouse aim/fire; G interact; R reload; M radar; Escape pauses/resumes.
Mobile: joystick + touch aim/fire; tactical radar toggle.
R48: restored saved positions now validate full player radius, recover blocked edge positions to verified spawn, and fail closed if even spawn is unsafe.
Home/Pause: Download backup, Copy backup code, or Paste backup code. Private code is cleared when leaving dialog or hiding tab.
Unit regression: node --test qa/*.test.mjs (139 PASS locally).
Local Chromium blocked ERR_BLOCKED_BY_ADMINISTRATOR; real browser acceptance requires authorized exact-head GitHub CI and S-01 staging.
MOJ1/wallet payments disabled. Factory VPS/master-agent HOLD; no deploy, restart, payment or public publication.
Source branch: games/g01-r48-safe-resume-roham-echo-20261030
