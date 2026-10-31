# G-01 R56 — 2026-10-31 (offline candidate; no deployment)

- Pagehide and Page Lifecycle freeze now release keyboard/touch/pointer capture and pause even if blur/visibilitychange never fires.
- Freeze redacts temporary backup text and requests a save; BFCache restore remains manually resumable.
- Separately rebuilt the exact-source R56 offline ZIP and corrected stale R53 preview-manifest metadata (game.js and input-guard hashes).
- Offline ZIP SHA-256: `665a5a1d07ca8743f6c9c80cd01efa6c2348263d2698bc1379c7f19d7db875f0`, 127 entries, 177/177 local Node tests, 126/126 SHA checks.
- The GitHub branch is a code review continuation of R55, not an assertion that its source snapshot is byte-identical to the offline R54-derived ZIP.
- Local Chromium navigation blocked by administrator; no R56 desktop/mobile browser acceptance. No merge, live deployment, factory write, wallet or MOJ1 checkout.
