# MOJ Casino Lounge — single-page source

**Owner:** MojPlayWin  
**Live URL:** https://mojplaywin.com/arena/  
**Release state:** First free-play release deployed and independently verified; subsequent versions must pass owned-update checks and separate live HTTPS smoke.  
**Languages:** English, Persian (فارسی), Arabic (العربية), German (Deutsch), French (Français), Spanish (Español). English default; Persian and Arabic RTL.  
**Scope:** Exactly one public-facing HTML document: `index.html` with inline CSS and JavaScript. No additional Arena storefront, revenue catalogue, internal subpages or duplicate MojPlayWin products.

## Actual page features

- Responsive, dark-and-gold, English-first free casino-simulation lounge.
- **37 browser-local free-play games plus 12 complete interactive fortune/horoscope activities** in one page, with six-language search and mobile category shortcuts:
  - 4 originals: European roulette, Blackjack practice, symbol reels and fictional sports picks.
  - 12 additional casino-style activities: simplified baccarat, five-card poker hand classifier, above/below seven, coin toss, animated fortune wheel, Keno, Bingo, Mines, Plinko, fictional racer sprint, penalty direction and high/low cards.
  - 15 new dice/chance exercises: exact die face, odd/even sum, doubles, three-dice range, four-or-more, triple match, craps point practice, Pig to thirty, two-dice duel, 1-2-3 sequence, sum ten, four of a kind, count sixes, closest to seven, six-seeking run.
  - Chess and backgammon: local two-player boards with move validation, checkmate, castling, en passant, promotion, undo; and dice turns, bar entry, hits and bearing-off.
  - 4 card games: Card War, Memory Pairs, three-card showdown and five-trick card duel.
- Twelve interactive, six-language symbolic oracles: daily zodiac for 12 signs, Chinese year animal (with Lunar New Year caveat), one-card Tarot, three-card Tarot, coffee-cup symbols, three-rune cast, six-line coin-based I Ching-inspired symbol, birth-date numerology, dream-symbol picker, original poetry oracle, yes/maybe/no reflection, and lucky-color/number draw.
- Each oracle produces a real browser-local result on interaction, with distinct underlying mechanics. Uses cryptographically sourced random draws where appropriate; daily zodiac is date-and-sign deterministic. Dates are never stored or transmitted. Results are explicitly entertainment/reflective, not factual predictions or professional advice.
- Six-language interface including original four simulations' status messages, descriptions, controls, twelve extra card descriptions/results, and all oracle titles/prompts/readings.
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
- The 12-oracle addition additionally requires Playwright tests of the 49 searchable experiences, each of the 12 oracle interactions, deterministic daily zodiac, invalid-date rejection, six-language switching and isolated deployment SHA-256 smoke.
- Initial production deployment and HTTPS checks passed in [GitHub Actions run 40613042892](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40613042892); later versions require their own run evidence.

## Before any publication

1. Confirm that free casino-style content may legally be published in each intended country/state; apply access restrictions and age protections as required.
2. Perform actual desktop, Android and iOS functional/visual QA and accessibility checks.
3. Confirm exact cPanel/Passenger root and prior isolated static release. Target must be either absent or an unmodified hash-matched directory owned by the Arena release workflow.
4. Upgrade `/arena/` only after validating the original marker and SHA-256. Preserve previous version in private release history; automatically restore it if live smoke fails. Never overwrite unowned content.
5. Verify `/arena/` renders over HTTPS and sibling sites remain unaffected.

The existing production workflows intentionally disable deployment for safety. **Do not bypass the lock.** No licence to conduct real-money gambling is asserted; if future legal permissions are obtained, a separately audited operator system would be required, not a toggle in this page.
