# MOJ ARENA GLOBAL — Independent source package

Source: site_releases/mojplaywin/arena/
Subpages: revenue/ and casino/
Intended URL: https://mojplaywin.com/arena/
Owner: MojPlayWin
Status: 2026-10-27 source exists on isolated feature branch. **Not deployed. Real-money wagering NOT available.**
Language: English-first with Persian for major headlines/navigation; full localization is pending.

## Implemented

- Premium responsive static design, accessible navigation and focus/reduced-motion styling.
- Filterable twelve-category experience index; future services are explicitly described as planned.
- Three interactive, locally scored skill games: reaction time, number memory, knowledge sprint; plus three free nonfinancial casino-style routines in the separate adult district.
- Free user-authored forecast journal with basic validation, local browser storage, JSON export and confirmed deletion.
- Country/market selector that keeps real-money betting disabled in every market; informational jurisdiction notes only.
- Interactive 50-channel revenue matrix plus separate adult casino area, with clear non-operational money-play gating and regulator references.
- No wallet, money deposit, withdrawal, API integration, fake leaderboard, customer payment or prize-redemption facility.

## Fifty non-casino revenue channels + the separate casino vertical

The approved portfolio is **50 distinct non-casino potential revenue models in 10 categories, plus MOJ Casino as a separate vertical**. The exact fifty individually named mechanisms and their launch gates are in revenue/models.js, presented at /arena/revenue/.

| Commercial engine | Count |
|---|---:|
| Advertising | 5 |
| Sponsorship | 5 |
| Game sales | 5 |
| Cosmetics | 5 |
| Subscriptions | 5 |
| Events | 5 |
| Digital goods | 5 |
| Affiliate and leads | 5 |
| B2B technology | 5 |
| Creator services | 5 |
| **Total outside casino** | **50** |
| Additional separately regulated casino vertical | **+1** |

None are asserted to be active merely because the source exists. The casino vertical must not be conflated with a working regulated operator.

### Casino source and legal separation

- /arena/casino/ contains an adult-gated informational zone and **three functioning free casino-style routines**: European roulette-colour practice, single-deck blackjack practice and symbol reels.
- There are no entry fees, money stakes, purchaseable play credits, payouts, redeemable assets, wallet integration or real-world prizes. Each browser visit requires an 18+ self-declaration; **this is not identity verification**.
- This source is NOT licensed casino software, not certified for gambling, and not suitable for financial play. It remains unpublished pending the same safe URL-path deployment preflight and jurisdictional assessment applied to all Arena content.
- Real-money casino operations, if pursued, require an entirely separate service and market/product-specific permission, audited operator backend, approved payment and identity verification. A foreign licence cannot be assumed sufficient worldwide.
- UK Gambling Commission remote casino licence: https://www.gamblingcommission.gov.uk/licensees-and-businesses/licences-and-fees/remote-casino-operating-licence
- Germany GGL official operator whitelist: https://www.gluecksspiel-behoerde.de/de/fuer-spielende/uebersicht-erlaubter-anbieter-whitelist
- Restricted payment activities: https://stripe.com/legal/restricted-businesses

## Non-negotiable regulated wagering barriers

The code is free entertainment and informational material. **Do not enable real-money wagers by toggling client-side flags.** A regulated module must be completely separated from public games and should include:

1. Verified operator/legal entity and product-specific permission in each jurisdiction.
2. Server-enforced country/state geolocation, age verification and identity checks.
3. AML/sanctions/source-of-funds policies as required by law.
4. Licensed payment and banking partner, independent operator ledger, reconciliation and player-funds safeguarding.
5. Responsible-gaming limits, self-exclusion, time/loss interventions and dispute handling.
6. Fraud controls, audited settlement data, RNG/supplier certifications where required.
7. State/country-specific advertising compliance, no targeting minors, privacy/security review.
8. Contract and independent legal signoff before launch.

MOJ1 purchases of ordinary digital content need their own payment/legal review. MOJ1 stakes, cash-equivalent prizes and redeemable rewards remain forbidden here until separately authorized.

## Isolation and deployment

The existing deployment workflows .github/workflows/mojplaywin-main-deploy.yml and mojplaywin-legacy-content-deploy.yml deliberately disable production deployment via a hard safety stop because protected child sites share Django/Passenger infrastructure. Never disable or bypass these locks.

Safe publication prerequisites:
1. Read-only verification of exact cPanel/Passenger document-root and URL routing.
2. Evidence that a static /arena/ child route can be deployed without touching shared runtime or sibling sites.
3. Hash-checked backup of exact target and tested path-only restoration.
4. New dedicated reviewed deploy workflow limited strictly to the verified /arena/ directory, with pinned SSH fingerprints, atomic copy and rollback.
5. Verified HTTP 200 for /arena/, script/style loads, page behavior and no change to other domains.

There is **no verified production route** and no live gambling offer. Do not report source code as published.

## Local source QC completed

- JavaScript parses successfully.
- HTML element IDs are unique and every 49 id referenced by JS exists.
- CSS brace counts balance.
- Memory-game next-level progression bug corrected.
- No claim of browser QA or live-domain tests until those checks genuinely happen.

## Primary regulatory references

https://www.gamblingcommission.gov.uk/service/apply-for-an-operating-licence
https://gaming.ny.gov/sports-wagering
https://ag.ny.gov/press-release/2025/attorney-general-james-stops-illegal-online-sweepstakes-casinos
https://support.google.com/adspolicy/answer/15132179?hl=en
https://stripe.com/legal/restricted-businesses

This document is engineering/product planning, not a legal opinion, licence or revenue guarantee.
