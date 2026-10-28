# MOJ Casino Lounge — single-page source

**Owner:** MojPlayWin  
**Live URL:** https://mojplaywin.com/arena/  
**Release state:** First free-play release deployed and independently verified; subsequent versions must pass owned-update checks and separate live HTTPS smoke.  
**Languages:** English, Persian (فارسی), Arabic (العربية), German (Deutsch), French (Français), Spanish (Español). English default; Persian and Arabic RTL.  
**Scope:** Exactly one public-facing HTML document: `index.html` with inline CSS and JavaScript. No additional Arena storefront, revenue catalogue, internal subpages or duplicate MojPlayWin products.


## Connected European football, world sports and horse competition coverage

- **Priority: Spain:** live public OpenLigaDB season fixtures/results for `la1` LaLiga. Also includes UEFA Champions League (`ucl`), Europa League (`uel2026`), Conference League (`uecl2026`), English Premier League (`pl`), German Bundesliga 1/2 (`bl1`/`bl2`), DFB-Pokal (`dfb`), and German ice hockey DEL (`del`). Community-edited coverage is league-dependent; empty or unavailable feeds remain visibly unavailable and never fabricate scores.
- The selected league loads only **after 21+ self-declaration**. Dynamic fixture rows remain outside the immutable 62-activity free-play entertainment catalog. Screens show upcoming/started/finished results with local-device times, last refresh, explicit provider attribution and source ODbL licence. Results may be delayed, disputed or corrected.
- For supported **football** matches only, the browser stores up to 50 no-cost local picks on 1X2, over/under 2.5 goals, both teams to score and exact score. Each selection closes at kickoff and reconciles from the published full-time result, with no server upload, odds, prizes, transactions or MCD balance effect. **Ice hockey is results-only**, since soccer-specific prediction market rules do not fit hockey.
- **Additional sports and countries:** browser read-only TheSportsDB free public `eventsnextleague.php` spotlight for NBA basketball, Formula 1 motor racing, ATP/WTA tennis, Big Bash cricket, plus Serie A (Italy), Ligue 1 (France), Eredivisie (Netherlands), Belgium Pro League, England Championship, Scotland Premiership and Greece Super League. The public free endpoint returns **at most one next listed event per league**, not complete fixtures, official live scores or racing odds. A null/no data response displays an explicit empty state. A two-hour browser cache and one selectable provider GET at a time limit traffic; manual refresh is available. Provider data are credited and never claimed as licensed betting odds.
- **Combat sports:** the same read-only provider's one-next-event spotlights now include real upcoming listings for UFC (`4443`), boxing (`4445`), ONE (`4495`), PFL (`5430`), European OKTAGON MMA (`5702`), and WWE (`4444`), AEW (`4563`), and NJPW (`4449`). Results, full fight cards, odds and betting markets are deliberately not inferred from this one-event listing; no money, wallets or MCD touches these modules. **WWE, AEW and NJPW are scripted pro-wrestling entertainment, not unscripted competitive wrestling.** An additional **22-entry official organizer/federation directory** with discipline and country/region filters covers Spanish boxing/wrestling/judo/taekwondo, World Boxing, UFC, ONE, PFL, OKTAGON, WWE, AEW, NJPW, freestyle/Greco-Roman UWW wrestling, IJF judo, World Taekwondo, WKF karate, WAKO and GLORY kickboxing, IFMA Muay Thai, IBJJF and ADCC grappling. Organizers' official links are navigational resources; neither real-time combat results nor winner predictions are claimed. Existing fantasy predictions remain unaffected.
- **Daily combat event agenda (new):** read-only free TheSportsDB `eventsday.php?d=YYYY-MM-DD&s=Fighting` results, manually selectable UTC date (last 7 to next 45 days) and one upcoming Saturday preselected. The provider's free tier is limited to **three events per day**, so this feature is a **partial public schedule preview**, not a fight-card or comprehensive live-data product. The browser caps each response to three verified entries, caches one selected date for an hour, aborts slow requests, rejects wrong sport/date, and clears stale data on provider failure. All fetched event names are untrusted text, inserted using `textContent`; no outcomes, individual bouts, payments or MCD stakes are inferred. This adds exactly one audited GET on the already allowlisted TheSportsDB host, with no new backend or provider costs.
- **Horse racing and equestrian are different sports.** A directory of **18 official calendar links** covers Spain (Madrid Zarzuela racing and Seville SICAB), France (Prix de l’Arc), United Kingdom (Ascot, Grand National, Cheltenham), USA (Derby, Breeders’ Cup), UAE (Dubai World Cup), Saudi Arabia (Saudi Cup), Japan (Japan Cup/JRA), Hong Kong (HKIR), Australia (Melbourne Cup/VRC), Germany (CHIO Aachen), and FEI jumping/dressage/eventing and Global Champions Tour. Country and discipline filters reveal the relevant organizer links; dates, entrants and results must be checked at the official organizer website. **No live horse racing API, horse-level betting predictions, fabricated racecards or race prices** are present.
- Static CSP permits exactly three audited public GET call sites across only two hosts: `api.openligadb.de` and `www.thesportsdb.com`. The guarded deploy verifier rejects unapproved calls, any wallet integration, altered CSP, tampering with live owned files or any edits to protected sibling routes. No analytics, payment endpoints, extra scripts or backend architecture.
- On missing/stale OpenLigaDB data, new football picks fail closed; existing casino simulations and official event links still work. Two independent read-only feeds do not grant data redistribution rights beyond their published API terms; revisit licensing before commercial resale of provider datasets.

## Future regulated finance boundary (documentation and UI locks only)

Status: **OFF / NO FINANCIAL ENDPOINTS OR PAYMENT CONNECTIONS**. This work does not activate real stakes or create an unlicensed sportsbook.

Activation must be a separately approved, audited backend project with verified jurisdiction-specific gambling licence and approved data/odds rights; jurisdiction and sanctions geofencing; age and identity verification; AML/CTF and suspicious activity monitoring; responsible-gambling limits, self-exclusion and customer dispute processes; treasury and regulatory reserves; double-entry server-owned accounting and idempotent payment/webhook handling; independent risk/RNG/security assessments; rigorous logging, reconciliation, monitoring, rollback and operator separation of duties. Never trust client-local MCD balance, picks, predicted outcomes or browser time for a financial transaction. A public launch requires a new release gate and an explicit owner decision on legal commitments and spending.

The published static site contains no live-money toggles, wallets, purchase paths, deposits, withdrawals, custody or transfer interfaces.

## Actual page features

- Responsive, dark-and-gold, English-first free casino-simulation lounge.
- **37 browser-local quick games, 12 interactive fortune/horoscope activities, 7 Casino Dollar practice tables, and 6 multi-market fictional prediction fixtures** in one page, with six-language search and mobile category shortcuts:
  - 4 originals: European roulette, Blackjack practice, symbol reels and fictional sports picks.
  - 12 additional casino-style activities: simplified baccarat, five-card poker hand classifier, above/below seven, coin toss, animated fortune wheel, Keno, Bingo, Mines, Plinko, fictional racer sprint, penalty direction and high/low cards.
  - 15 new dice/chance exercises: exact die face, odd/even sum, doubles, three-dice range, four-or-more, triple match, craps point practice, Pig to thirty, two-dice duel, 1-2-3 sequence, sum ten, four of a kind, count sixes, closest to seven, six-seeking run.
  - Chess and backgammon: local two-player boards with move validation, checkmate, castling, en passant, promotion, undo; and dice turns, bar entry, hits and bearing-off.
  - 4 card games: Card War, Memory Pairs, three-card showdown and five-trick card duel.
- Twelve interactive, six-language symbolic oracles: daily zodiac for 12 signs, Chinese year animal (with Lunar New Year caveat), one-card Tarot, three-card Tarot, coffee-cup symbols, three-rune cast, six-line coin-based I Ching-inspired symbol, birth-date numerology, dream-symbol picker, original poetry oracle, yes/maybe/no reflection, and lucky-color/number draw.
- Each oracle produces a real browser-local result on interaction, with distinct underlying mechanics. Uses cryptographically sourced random draws where appropriate; daily zodiac is date-and-sign deterministic. Dates are never stored or transmitted. Results are explicitly entertainment/reflective, not factual predictions or professional advice.
- Six-language interface including original four simulations' status messages, descriptions, controls, twelve extra card descriptions/results, and all oracle titles/prompts/readings.
- **Seven expanded risk-free Casino Dollar (MCD) tables:** European roulette (colour/parity/range/dozen/straight-up), dealer Blackjack (natural 3:2, hit/stand/double; no split or insurance), Punto Banco Baccarat (third-card rules and banker commission), symbol slots (explicit total-return paytable), five-card Jacks-or-Better video poker (hold/draw), pass-line Craps (point progression), and fictional virtual 1X2 sports prediction (displayed decimal odds). Existing quick-play experiences remain intact; expanded tables are distinct rule-rich practice modes.
- **Prediction Center:** Six fictional fixtures (three football, one basketball, one tennis, one esports) with coherent market outcomes: 1X2, double chance, total goals, both-teams-to-score, correct score; basketball winner/total/handicap; tennis and esports winner/series score/set totals. Browser-only finite probability models generate both the displayed demo decimal odds (6% illustrative margin) and cryptographically sampled outcomes. A multi-event slip accepts up to three different fixtures; one MCD stake, settlement and history update applies to the slip. Combined odds are capped at 100×, with a maximum 10,000 MCD return per simulated slip. These are not genuine event forecasts or bookmaker quotes.
- **Demo ledger:** 1,000.00 initial MCD, stake buttons, rounds/wins, last-ten local result history and free refill. All balances are cents-based **local browser state**, untrusted and non-transferable, not stored in any server or blockchain. Reloading mid-hand restores the last completed-round balance.
- **MOJ1 ⇄ MCD conversion is visibly LOCKED**; there is no purchase, payment, wallet, transfer, exchange rate, payout or redemption functionality in the expanded page. Real-money features require a separate licensed and independently audited backend.
- **Search and navigation:** 62 selectable entertainment experiences in six categories (37 quick games + 12 oracles + 7 practice tables + 6 prediction fixtures). The new table captions are localized for all six languages. Advanced round outcome descriptions retain standard game terms.
- **Keyboard access:** age dialog now initially focuses its age self-declaration, makes background inert while open and traps Tab within its two actions. This improves accessibility but does **not** verify legal age.
- 21+ self-declaration overlay. This is **not** verification of identity or legal eligibility.
- Clear prohibition of cash stakes, real-money wagering, paid spins, wallets, purchasable tokens, withdrawals, prizes and MOJ1 wagering.
- No customer registration, personal data capture, payment, affiliate destinations or backend gambling functionality; sports feeds are public read-only event data and nonfinancial.
- Cryptographically sourced random numbers used for local simulations; no cash-equivalent scoring.

## Confirmed checks

- Node static script syntax parsed successfully.
- Dependency-free runtime QA: all fifteen new dice games, four card games, chess legal moves/checkmate/undo, a backgammon move, four original interactions and six-language switching exercised successfully.
- RTL for Persian/Arabic and LTR for English/German/French/Spanish asserted.
- Isolated poker deck from Blackjack state to avoid cross-game interference.
- No external script dependencies or financial connections.
- Actual desktop and mobile-viewport Chromium browser QA passed in [GitHub Actions run 40577107944](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40577107944); this is not a substitute for all physical-device testing.
- The latest expanded addition requires Playwright tests of the 56 searchable experiences, each of the 12 oracle interactions, deterministic daily zodiac, invalid-date rejection, six-language switching and isolated deployment SHA-256 smoke.
- Initial production deployment and HTTPS checks passed in [GitHub Actions run 40613042892](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40613042892); later versions require their own run evidence.

## Casino Dollar practice release checks

The guarded GitHub workflow additionally checks seven MCD practice tables, 56 searchable experiences, local balance/settlement/refill across all table types, age-dialog keyboard focus, six-language switching, browser errors, exact live payload SHA-256 and protected sibling routes. **These tests do not certify financial randomness, casino rules for all edge cases or real-money suitability.**

## Before any publication

1. Confirm that free casino-style content may legally be published in each intended country/state; apply access restrictions and age protections as required.
2. Perform actual desktop, Android and iOS functional/visual QA and accessibility checks.
3. Confirm exact cPanel/Passenger root and prior isolated static release. Target must be either absent or an unmodified hash-matched directory owned by the Arena release workflow.
4. Upgrade `/arena/` only after validating the original marker and SHA-256. Preserve previous version in private release history; automatically restore it if live smoke fails. Never overwrite unowned content.
5. Verify `/arena/` renders over HTTPS and sibling sites remain unaffected.

The existing production workflows intentionally disable deployment for safety. **Do not bypass the lock.** No licence to conduct real-money gambling is asserted; if future legal permissions are obtained, a separately audited operator system would be required, not a toggle in this page.
