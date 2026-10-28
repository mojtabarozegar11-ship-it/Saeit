# MOJ Casino Lounge — single-page source

**Owner:** MojPlayWin  
**Proposed URL:** https://mojplaywin.com/arena/  
**Release state:** Source on `feat/moj-arena-global-20261027`; public availability is confirmed only by the isolated release workflow and a live HTTPS test.  
**Languages:** English, Persian (فارسی), Arabic (العربية), German (Deutsch), French (Français), Spanish (Español). English default; Persian and Arabic RTL.  
**Scope:** Exactly one public-facing HTML document: `index.html` with inline CSS and JavaScript. No additional Arena storefront, revenue catalogue, internal subpages or duplicate MojPlayWin products.

## Actual page features

- Responsive, dark-and-gold, English-first free casino-simulation lounge.
- **37 browser-local free-play games** in one page:
  - 4 originals: European roulette, Blackjack practice, symbol reels and fictional sports picks.
  - 12 additional casino-style activities: simplified baccarat, five-card poker hand classifier, above/below seven, coin toss, animated fortune wheel, Keno, Bingo, Mines, Plinko, fictional racer sprint, penalty direction and high/low cards.
  - 15 new dice/chance exercises: exact die face, odd/even sum, doubles, three-dice range, four-or-more, triple match, craps point practice, Pig to thirty, two-dice duel, 1-2-3 sequence, sum ten, four of a kind, count sixes, closest to seven, six-seeking run.
  - Chess and backgammon: local two-player boards with move validation, checkmate, castling, en passant, promotion, undo; and dice turns, bar entry, hits and bearing-off.
  - 4 card games: Card War, Memory Pairs, three-card showdown and five-trick card duel.
- Six-language interface including original four simulations' status messages, descriptions, controls, and twelve extra card descriptions/results.
- 21+ self-declaration overlay. This is **not** verification of identity or legal eligibility.
- Clear prohibition of cash stakes, real-money wagering, paid spins, wallets, purchasable tokens, withdrawals, prizes and MOJ1 wagering.
- No customer registration, personal data capture, payment, real sports feeds, affiliate destinations or backend gambling functionality.
- Cryptographically sourced random numbers used for local simulations; no cash-equivalent scoring.

## Confirmed checks

- Node static script syntax parsed successfully.
- Dependency-free runtime QA: all fifteen new dice games, four card games, chess legal moves/checkmate/undo, a backgammon move, four original interactions and six-language switching exercised successfully.
- RTL for Persian/Arabic and LTR for English/German/French/Spanish asserted.
- Isolated poker deck from Blackjack state to avoid cross-game interference.
- No external script dependencies or financial connections.
- Actual desktop and mobile-viewport Chromium browser QA passed in [GitHub Actions run 40577107944](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40577107944); this is not a substitute for all physical-device testing.
- Production deployment and HTTPS checks require their own evidence, separate from source QA.

## Before any publication

1. Confirm that free casino-style content may legally be published in each intended country/state; apply access restrictions and age protections as required.
2. Perform actual desktop, Android and iOS functional/visual QA and accessibility checks.
3. Confirm the exact cPanel/Passenger document root, an intact prior isolated static release and an absent `/arena/` destination in the deployment preflight.
4. Publish only to a vacant `/arena/` directory through `scripts/deploy_mpw_arena_static.py`; never overwrite any existing path. If smoke fails, the owned new release is retained offline for recovery.
5. Verify `/arena/` renders over HTTPS and sibling sites remain unaffected.

The existing production workflows intentionally disable deployment for safety. **Do not bypass the lock.** No licence to conduct real-money gambling is asserted; if future legal permissions are obtained, a separately audited operator system would be required, not a toggle in this page.
