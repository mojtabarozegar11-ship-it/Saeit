# ROOTLINE: Bloom Defense — Factory F14 pilot

**Status: PRIVATE, UNRELEASED TECHNICAL GAME PROTOTYPE — NOT FOR LIVE SALE.**

An original, fixed-scope five-lane garden-defense game implemented with Canvas 2D, CSS and deterministic plain JavaScript. No images, fonts, audio files, external packages or network dependencies.

## Play / contents
Open \`index.html\` in a modern desktop or mobile browser with the adjacent \`game.css\`, \`engine.js\`, and \`game.js\` files kept together. The browser must support Canvas 2D, pointer input and requestAnimationFrame.

- Place thorn defenders, slowing mist plants and water-producing wells; manage irrigation as a finite resource
- Five independent pest attack lanes, eight placement columns; escalating enemy waves with beetle, swift and armored variants
- Rainburst defensive ability, wave completion bonus, local high score; optional synthesized sound defaults off
- Pointer/touch controls and alternative number-key and spacebar controls; pause/restart and help panel
- No login, ads, checkout, in-app purchase, monetized loot boxes, external links, trackers or user-data upload
- Local storage retains only a best-score number; browser restrictions may disable persistence without preventing play

## Engineering acceptance
Execute \`python -m unittest -v tests.test_rootline_game_pilot\` from repository root, with Node.js installed. Checks cover actual Node execution of production engine state transitions: starting, three plant types, resource accounting, occupied/out-of-bounds rejection, pause, combat/score, rainburst costs/cooldown, loss condition and enemy spawning. These tests **do not** verify that a person finds the game fun.

### Further release requirements (all unverified until demonstrated)
1. **manual playtesting**: meaningful multiple-session manual playtesting for difficulty, pacing, fairness and feedback; make balance changes from observed play evidence
2. **independent specialist** review: game design, interaction/accessibility, failure modes and suitability for intended age/market
3. **rights and provenance**: item-level ownership, original source and asset provenance, license and written approval to commercially redistribute
4. **real device** testing: representative Android, iOS, desktop and low-power configurations including reduced motion, small screens, Safari and touch
5. **merchant** verification: verified PSP/on-chain settlement identity for the exact target store, tax/refund terms, fixed owner-approved price, authenticated payments and actual entitlement/download tests
6. Security and operational gates: no script injection, safe package versioning, browser CSP and MIME behavior, package checksums, reliable restoration/rollback and uptime monitoring
7. Product value gates: independent player feedback, screenshot/demo provenance, correct expectations and publication copy approved by owner

## Owner decisions pending
- Should distribution be on Zomorod Melal, MojPlayWin, or both, and which legal publisher receives the license?
- Free demo or paid product; approved customer price and support policy
- Final brand/name and ownership of all parts by the declared individual rights holder
- Approval after expert reviews and real-world trial evidence

**No modification to public storefronts, live payment routes or existing customers is authorized by creating this branch.**
