# MOJ Casino Lounge — single-page source

**Owner:** MojPlayWin  
**Proposed URL:** https://mojplaywin.com/arena/  
**Status:** Draft code on `feat/moj-arena-global-20261027`, **not deployed**.  
**Languages:** English, Persian (فارسی), Arabic (العربية), German (Deutsch), French (Français), Spanish (Español). English default; Persian and Arabic RTL.  
**Scope:** Exactly one public-facing HTML document: `index.html` with inline CSS and JavaScript. No additional Arena storefront, revenue catalogue, internal subpages or duplicate MojPlayWin products.

## Actual page features

- Responsive, dark-and-gold, English-first free casino-simulation lounge.
- **16 self-contained browser-local free-play simulations** on the same page:
  1. European roulette colour.
  2. Blackjack practice against a virtual dealer.
  3. Symbol reels (decorative slots).
  4. Fictional virtual sports pick (not live sports or bookmaker odds).
  5. Simplified two-card baccarat.
  6. Five-card poker hand classification.
  7. Two-dice challenge (below/above seven).
  8. Coin toss.
  9. Six-symbol fortune wheel.
  10. Mini Keno (one pick; three draws).
  11. Mini Bingo comparison.
  12. Nine-tile Mines (two simulated mines).
  13. Plinko random left/right path.
  14. Virtual three-racer sprint.
  15. Penalty kick direction.
  16. High/Low card ranks.
- Six-language interface including original four simulations' status messages, descriptions, controls, and twelve extra card descriptions/results.
- 21+ self-declaration overlay. This is **not** verification of identity or legal eligibility.
- Clear prohibition of cash stakes, real-money wagering, paid spins, wallets, purchasable tokens, withdrawals, prizes and MOJ1 wagering.
- No customer registration, personal data capture, payment, real sports feeds, affiliate destinations or backend gambling functionality.
- Cryptographically sourced random numbers used for local simulations; no cash-equivalent scoring.

## Confirmed checks

- Node static script syntax parsed successfully.
- Dependency-free runtime QA: all twelve new simulations' choice buttons, four original interactions, 21+ gate and six-language switching exercised successfully.
- RTL for Persian/Arabic and LTR for English/German/French/Spanish asserted.
- Isolated poker deck from Blackjack state to avoid cross-game interference.
- No external script dependencies.
- Actual browser/mobile visual QA **not completed** (headless browser executable unavailable here). No production HTTP test was completed.

## Before any publication

1. Confirm that free casino-style content may legally be published in each intended country/state; apply access restrictions and age protections as required.
2. Perform actual desktop, Android and iOS functional/visual QA and accessibility checks.
3. Identify the real cPanel/Passenger static serving path and existing MojPlayWin router behavior by read-only inspection.
4. Back up precisely the intended target, avoid changing shared services, and implement reviewed path-scoped deployment/rollback.
5. Verify `/arena/` renders over HTTPS and sibling sites remain unaffected.

The existing production workflows intentionally disable deployment for safety. **Do not bypass the lock.** No licence to conduct real-money gambling is asserted; if future legal permissions are obtained, a separately audited operator system would be required, not a toggle in this page.
