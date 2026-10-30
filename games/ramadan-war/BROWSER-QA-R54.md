# R54 exact-source browser acceptance — pending

Prior R53 exact-head browser CI [41140909099](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/41140909099): SUCCESS. R54 offline Node checks do not replace browser tests.

1. Desktop: focus ARIA HUD controls and press Space/arrow; native controls work without gameplay input; arena WASD/Space/Q/E/R/G/M remain functional.
2. Mobile: hold joystick/fire, background/foreground, no phantom movement/fire.
3. Desktop/mobile BFCache: navigate away/back during play; restored page pauses, releases inputs, and preserves saved campaign.
4. Rotate during active aim/joystick; fresh touch works.
5. Complete a mission, export/import campaign backup, confirm WebGL/GLB assets and no uncaught page errors.
6. MOJ1 payment and wallet calls stay disabled; S-01 independently verifies backup and rollback.

**CODE / READY_FOR_REVIEW. Not MERGED, DEPLOYED or LIVE_VERIFIED.**
