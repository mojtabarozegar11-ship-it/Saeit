# Ramadan War R53 — offline release candidate (2026-10-31)

Primary: invalid camera pointer deltas now cancel gesture and release capture; viewport resize drops stale aim/fire/joystick capture without changing campaign saves.

Rotation: Air Supremacy invalid joystick geometry releases capture; Taniya Cake Maker SVG download URL survives slow mobile handoff, reports only request (not confirmed download), and exposes frosting state to assistive technology.

Evidence: R52 exact-head real browser/model CI [41134700379](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/41134700379) SUCCESS. R53 local Node tests 163/163 PASS. R53 local Chromium navigation BLOCKED_BY_ADMINISTRATOR, so R53 browser acceptance is still required on exact-head CI. No live deployment, no rollback proof. MOJ1 disabled; factory/master-agent HOLD.

The offline ZIP is a Ramadan-only 119-file candidate with SHA-256 integrity manifest, retained in the owner-private library if verified. S-01 alone owns public release after backup, rollback and browser checks.
