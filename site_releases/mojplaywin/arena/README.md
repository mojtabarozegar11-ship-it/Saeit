# MOJ ARENA GLOBAL — Independent source package

Source: site_releases/mojplaywin/arena/
Intended URL: https://mojplaywin.com/arena/
Owner: MojPlayWin
Status: 2026-10-27 source exists on isolated feature branch. **Not deployed. Real-money wagering NOT available.**
Language: English-first with Persian for major headlines/navigation; full localization is pending.

## Implemented

- Premium responsive static design, accessible navigation and focus/reduced-motion styling.
- Filterable twelve-category experience index; future services are explicitly described as planned.
- Three interactive, locally scored skill games: reaction time, number memory, knowledge sprint.
- Free user-authored forecast journal with basic validation, local browser storage, JSON export and confirmed deletion.
- Country/market selector that keeps real-money betting disabled in every market; informational jurisdiction notes only.
- Business and 30-channel strategy described below; responsible-play disclosures and regulator references.
- No wallet, money deposit, withdrawal, API integration, fake leaderboard, customer payment or prize-redemption facility.

## Thirty proposed income channels

Revenue is **not active** merely because this UI exists. Each monetization stream requires a real offer and appropriate product rights, legal review, funding/payment acceptance, fulfillment and taxes.

| # | Category | Stream | Activation gate |
|---|---|---|---|
| 1 | Ads | Contextual ads | ad provider and privacy consent |
| 2 | Ads | Voluntary rewarded ads | provider and nonfinancial rewards |
| 3 | Ads | Sponsored video | sponsor contract and delivery |
| 4 | Ads | Interactive product ads | brand agreement/disclosure |
| 5 | Ads | Event sponsorship | confirmed event/sponsor |
| 6 | Games | Standalone premium games | IP, QA, fulfillment |
| 7 | Games | Cosmetic items | item entitlement/checkout |
| 8 | Games | Expansion packs | rights and delivery |
| 9 | Games | Customization | moderation/entitlement |
| 10 | Games | Product bundles | item rights |
| 11 | Subscriptions | Individual premium | renewal terms/billing |
| 12 | Subscriptions | Non-gambling family plan | age segmentation |
| 13 | Subscriptions | Creator plan | creator agreement |
| 14 | Subscriptions | B2B club | service contract |
| 15 | Competitions | Lawful event admission | local law review |
| 16 | Competitions | Organizer service fee | organizer contract |
| 17 | Competitions | Sponsored contest | contest law and sponsor |
| 18 | Commerce | Original digital goods | ownership and checkout |
| 19 | Commerce | Creator marketplace | moderation/royalty |
| 20 | Commerce | Non-gambling affiliate links | merchant contract/disclosure |
| 21 | Commerce | QR and product-code campaigns | brand campaign |
| 22 | B2B | White-label skill software | license contract |
| 23 | B2B | Branded mini-games | development contract |
| 24 | B2B | Interactive campaign studio | defined offer |
| 25 | B2B | Tournament operations | SLA and fair rules |
| 26 | Content | Educational game content | content license |
| 27 | Content | Entertainment event tickets | live scheduled event |
| 28 | Content | Skill tutorials | owned course |
| 29 | Content | Licensed media/co-production | IP agreement |
| 30 | Regulated | Licensed-operator wagering partnership | licence and financial approvals |

Paid competitions, paid predictions, sweepstakes, prizes of real-world value and crypto rewards may trigger gambling/contest regulation even when described as skill-based.

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
