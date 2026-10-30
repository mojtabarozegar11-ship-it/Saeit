# R50 browser QA checklist — not yet accepted
1. Run real Chromium desktop 1280×800 and mobile 390×844 on exact R50 branch SHA, not R49.
2. Confirm GLB models and textures load without console errors, WASD and joystick movement, mouse/touch aiming and fire.
3. Inject invalid/very large pointer deltas: world angle remains finite, no accidental click-to-fire after invalid pointer movement.
4. Rotate device / resize viewport; verify WebGL context and 1px minimum dimensions, no white/blank frame.
5. Save, reload, import/export and cross-tab conflict fail closed; pause/resume and mission objectives remain functional.
6. Independently test Air Supremacy invalid joystick geometry and Roham runner Pause/P/resume.
7. Run S-01 read-only ZIP gate, verify exact manifest hashes, source provenance and MOJ1 disabled.
8. Require off-VPS site-specific backup, tested restore/rollback, rights approval, then S-01 live URL verification.
No public release or payment claim follows from local unit tests alone.
