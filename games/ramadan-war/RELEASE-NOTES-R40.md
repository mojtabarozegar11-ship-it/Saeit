# Ramadan War R40 — Offline review build, 2026-10-30

- Added explicit copyable campaign backup from Home and Pause. Browser Clipboard API is attempted only on a user click; local textarea fallback reports failure rather than claiming success. No account, network or wallet integration.
- Escape now resumes a paused campaign, including when a pause-menu button has keyboard focus; modified/IME keys and file inputs are excluded.
- Added Node regression for clipboard success, denied permission, fallback cleanup and Escape binding.
- Rotation: Cake Maker undo candle (preserves design), ECHOFORM playback announces actual sequence step and tile.
- S-01 handoff: independent fail-closed, read-only 35-file asset and SHA preflight; 5 local unit tests pass.
- Local Node QA 106/106 pass in extracted R40 offline build; R40 ZIP 69 files / 68 manifest hashes verified; browser Chromium in current sandbox blocked by administrator, **not a browser PASS**.
- Offline ZIP SHA-256: `87c7d199da6199e703bddcc1aba1753db8efb73e1e89b609995a222f4d801a82`.
- Factory VPS/master-agent HOLD, MOJ1 disabled. **NOT MERGED, NOT DEPLOYED**; independent browser/device and S-01 off-VPS backup/rollback gate required.
