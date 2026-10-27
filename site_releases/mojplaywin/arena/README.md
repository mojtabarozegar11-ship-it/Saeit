# MOJ Casino Lounge — single-page source

**Owner:** MojPlayWin  
**Proposed URL:** https://mojplaywin.com/arena/  
**Status:** Draft code on `feat/moj-arena-global-20261027`, **not deployed**.  
**Languages:** English default; Persian selectable.  
**Scope:** Exactly one public-facing HTML document: `index.html` with inline CSS and JavaScript. No additional Arena storefront, revenue catalogue, internal subpages or duplicate MojPlayWin products.

## Actual page features

- Responsive, dark-and-gold, English-first casino lounge.
- Four browser-local, free entertainment interactions on that same page:
  1. European roulette colour simulation (37 outcomes).
  2. Simplified blackjack practice against a virtual dealer.
  3. Three-symbol reels with no real-world award.
  4. Fictional virtual sports pick with random outcome (not actual sporting events or bookmaker odds).
- 21+ self-declaration overlay. This is **not** verification of identity or legal eligibility.
- Content-only English/Persian language toggle, with RTL for Persian.
- Clear prohibition of cash stakes, real-money wagering, paid spins, wallets, purchaseable tokens, withdrawals, prizes and MOJ1 wagering.
- No customer registration, personal data capture, payment, real sports feeds, affiliate destinations or back-end gambling functionality.

## Confirmed checks

- Node static script syntax parsed without error.
- No duplicate DOM IDs; selector references checked against static IDs.
- No external script dependencies.
- Browser/mobile behavioral QA **not completed** (headless browser binary unavailable here). No production HTTP test was completed.

## Before any publication

1. Confirm that this free casino-style content can legally be published in each intended country/state; apply access restrictions and age protections as required.
2. Perform actual desktop, Android and iOS functional/visual QA and accessibility checks.
3. Identify the real cPanel/Passenger static serving path and existing MojPlayWin router behavior by read-only inspection.
4. Back up precisely the intended target, avoid changing shared services, and implement reviewed path-scoped deployment/rollback.
5. Verify `/arena/` renders correctly over HTTPS and all sibling sites remain unaffected.

The existing production workflows intentionally disable deployment for safety. **Do not bypass the lock.** No licence to conduct real-money gambling is asserted; if future legal permissions are obtained, a separately audited operator system would be required, not a toggle in this page.
