# Proprietary trading policy engine v1.2 (prospective cohorts)

**Status:** Code for the proposed prop business. NOT a launched website, licensed provider, funded-account contract, broker adapter or payments service. The only organizational robot identity is **mojtaba.bot.ai**; this is an internal capability, not a second robot.

## Confirmed product terms
- **30 TRX per applicant** is the challenge participation fee, not the company's starting capital.
- Two *simulated* evaluation phases: realized-net profit goals **9.6% / 6%**, at least **6 valid trading days** each, maximum daily **4%** and fixed total **8%** mark-to-market equity loss; largest profitable day at most **32%** of net profit.
- **No completion deadline**. Inactivity notice after 78 days and 39-day grace; inactivity messaging is not implemented here.
- Upon passing both stages, KYC, lawful company funding and broker approvals, the first *real* account is **$100**, contingent on available capital.
- All **14 USD levels:** 100, 200, 400, 800, 1500, 3000, 5000, 10000, 20000, 35000, **50000**, 70000, 85000, 100000.
- **30-day promotion window**, at most one level per qualifying window, profit goal **3.6%**, at least **12 valid trading days**, no risk breach, max day 32%, trustworthy reconciled evidence and verified funding for the next tier.
- Per-trade stop-risk max **0.8%** and cumulative open stop-risk **1.6%** of tier capital; block an order if broker minimum lot/stop distance cannot fit.
- Monthly net profit sharing **70% trader / 30% company**, on cumulative realized net P&L exceeding previously *allocated* profit. Losses must be recouped first; no double payment.

## New social posting pass condition — prospective v1.2 purchasers

- For **each verified UTC trading day in each simulated challenge phase**, the
  trader must personally publish **one original Instagram post AND one original
  Facebook post** and submit two URLs for independent review.
- A minimum of six trading days per phase means **6 Instagram + 6 Facebook
  posts per phase**, **24 combined posts across both phases** at minimum.
  Additional valid trading days require corresponding additional posts;
  idle calendar days do not add a posting obligation. The challenge remains
  without a fixed completion deadline.
- This is a disclosed commercial participation condition, **not a request
  for a fake review or a positive endorsement**. A neutral, truthful account
  of the process is acceptable. Each post must clearly state that it is a
  requirement of participating in MOJ PROP, and use an advertising/partnership
  disclosure or labeling where applicable. Do not claim guaranteed returns,
  falsely advertise actual funding, or pressure friends into purchasing.
- Each post must come from the trader's own authorized account and remain
  publicly inspectable at review, with its date matching the verified trading
  day. Independent staff validates author, date, public visibility,
  disclosure, content, and platform before marking the day reviewed.
- **No automatic posting, scheduling, account passwords, Meta credentials,
  forced tagging, or publication through mojtaba.bot.ai**. No action on
  Instagram `Dr.mojtaba.rozegar` under any circumstances.
- Missing or rejected posts **delay phase completion** but do not override
  broker risk results, fabricate a risk breach, or directly confiscate
  legitimate realized trading profits. The rule applies only to new v1.2
  cohorts whose contract disclosed it before fee acceptance. Legacy v1.1
  accounts retain their former terms.
- Public-facing text is available in all 20 existing UI languages; local
  legal/ad-policy and translation review are still required before enrollment.
  Some jurisdictions/platforms may not allow such a compulsory promotion
  requirement: in those markets the business must not sell the challenge
  under these terms before counsel approves a lawful alternative.
- `prop_firm/social_policy.py`, `social_review_service.py`, model
  `PropSocialEvidence` and migration `0003_social_evidence.py` implement
  a **private review-only evidence flow**. No live Meta integration, checkout,
  automatic enrollment or funded-account approval is provided.

## Non-negotiable implementation requirements
1. No actual payments or trade orders can be triggered by this module: both real execution and TRX checkout are disabled by policy.
2. All financial metrics must originate from verified, authoritative, timestamped brokerage or simulated-venue records; browser parameters are not trusted.
3. Daily equity floor: UTC day-opening equity minus 4% of original tier capital. Total equity floor: original tier capital minus 8%. Floating P&L counts. Trigger at or below either floor. Handle trading-day boundaries deterministically.
4. The 32% best-day rule is applied against **net realized profit**, not merely the sum of positive days; days with losses can increase the ratio. Phase two requires independent evidence of phase one pass.
5. Challenge acceptance, trade execution, settlement and promotion need durable idempotent records, transactional concurrency control, immutable audit logs, unique account/phase/period/transaction keys and dispute procedures. The pure functions do not provide these.
6. Funded real accounts require lawful eligibility, KYC/AML/sanctions screening, signed customer agreement, broker authorization, verified **unencumbered cash >= requested tier capital + payout reserve**, and independent operational signoff.
7. An authentic $100 account might not satisfy broker minimum order size on a given symbol. Do not relax order-risk bounds or invent fractional fills to solve this.
8. Bank/wallet settlement requires confirmation and safe ledger posting; payout calculations cannot transfer money. TRX receipt accounting must validate TRON mainnet transaction ID, recipients, exact onchain quantity, confirmation/finality, refund rules and taxes.
9. All customer-facing rules must be published before fee acceptance. No unilateral retroactive punitive changes; disclose capital scarcity and conditional escalation. Legal characterization depends on where the business actually operates and serves customers.
10. No independent trader bot or public branding is added. All bots/strategies are future subcapabilities of **mojtaba.bot.ai**, with old identifiers migrated only after validated handoff.

## Local automated checks (standard library only)
```bash
PYTHONPATH=. python -m unittest discover -s tests -p 'test_prop_firm_policy.py' -v
```

## Required gates before launch
Verified operating country and regulatory counsel; funded cash reserve and treasury policy; approved broker and its minimum order/stop specs; encrypted account store; KYC and eligibility; immutable and reconciled ledger; wallet and escrow accounting; customer terms and dispute handling; penetration/integration tests; hosting and domain authorization; independent deployment approval.

**No deployments, paid services, live trading, customer emails, asset deletion, or payments are permitted by this draft.**


## Moj Prop — 20-language luxury website integration (14 Nov 2026)

**Brand ownership:** MOJ PROP is a MojPlayWin division, not a stand-alone AI agent or legal entity. The **only** organizational bot is \`mojtaba.bot.ai\`.

**Canonical informational website:** \`https://mojplaywin.com/moj-prop/\` (English); 19 translated paths at \`/moj-prop/<language-code>/\`. The path is **not deployed** merely because it exists in the GitHub branch.

**Full landing-page localization:** English \`en\` default; Farsi \`fa\`, Arabic \`ar\`, German \`de\`, French \`fr\`, Spanish \`es\`, Portuguese \`pt\`, Italian \`it\`, Turkish \`tr\`, Russian \`ru\`, Simplified Chinese \`zh\`, Japanese \`ja\`, Korean \`ko\`, Hindi \`hi\`, Indonesian \`id\`, Vietnamese \`vi\`, Thai \`th\`, Dutch \`nl\`, Polish \`pl\`, Urdu \`ur\`. **840 verified non-empty translatable page strings**, 42 per language, with complete navigation, page copy, disclosures, stages, tiers, rules and FAQs. Arabic, Farsi and Urdu use actual HTML RTL, not just CSS visual flipping.

**UI implementation:** \`prop_firm/moj_prop_locales.json\` is the translation catalog, validated by \`prop_firm/moj_prop_page.py\`. Policy figures and fourteen funding tiers are supplied by \`prop_firm/rules.py\`, not duplicated as independent marketing numbers. The Django host-limited \`core/moj_prop_views.py\` renders \`core/templates/mojplaywin/moj_prop.html\`, styled by \`core/static/site/moj_prop.css\` (obsidian, champagne-gold, decorative capital orb, responsive tier visualization, keyboard-accessible localization menu, motion-reduction support).

**Navigation:** Host \`mojplaywin.com\` and \`www.mojplaywin.com\` only; no page exposed as a Zomorod Melal financial offer. The parent MojPlayWin primary navigation/footer link to the preview division.

**Availability and SEO:** All pages explicitly state pre-launch/no payments, return \`X-Robots-Tag: noindex, nofollow\`, and have canonical and language-alternate metadata. This content is a **product preview**, not a real public funding offer. Avoid promising that a trader will get cash after challenge completion unless the committed real treasury and broker support the entire advertised scale plan.

**Translation scope:** All sections of this informational landing page are localized. Broker agreements, complete customer contracts, compliance documents, support workflows and a paid checkout have **not** been translated, completed or launched. Those require qualified native/regulatory review for each served jurisdiction. Do not call them 'fully localized' until they actually exist.

### Verification
- \`python -m unittest tests.test_moj_prop_site tests.test_prop_firm_policy tests.test_prop_firm_site\` (when import packages are available).
- \`python manage.py test tests.test_moj_prop_site\` (Django integration, host blocking, HTML lang/dir).
- Review linked PR CI, staticfiles collection, mobile rendering, native-speaker proofreading, performance, contrast/keyboard accessibility and load in every target locale before any production release.

**Hard safeguards:** No wallets, payment acceptance, brokerage operations, login collection, trading APIs or financial guarantees are exposed in this page. No deployment or cost is authorized by these files.
