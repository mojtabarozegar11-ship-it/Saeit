# Proprietary trading policy engine v1.2 (prospective cohorts)

**Business status (owner declaration, 15 Nov 2026):** **Plan 1 is funded and active according to the owner**; Plans 2–10 are funding in progress and **temporarily inactive**. This is an owner assertion, not independently verified treasury/broker evidence. The code in this PR remains draft: **no independently proven checkout, broker adapter, settlement or deployment here**. The only organizational robot identity is **mojtaba.bot.ai**; this is an internal capability, not a second robot.

## Confirmed product terms
- **Plan 1: 30 TRX per applicant**, confirmed by owner as the entry price; other 9 proposed prices differ. An entrance fee is not the company-funded trading capital.
- Two *simulated* evaluation phases: realized-net profit goals **9.6% / 6%**, at least **6 valid trading days** each, maximum daily **4%** and fixed total **8%** mark-to-market equity loss; largest profitable day at most **32%** of net profit.
- **At least 50 DISTINCT, independently verified CLOSED trades across both simulated stages COMBINED** within that same 28-day period, not 50 per stage. Each stage still requires at least six independently verified trading days. Only the FINAL phase-two pass is gated by the total-50 threshold, so participants can progress from stage one before 28-day social proofs mature.
- **Trader-owned automated strategies (bots) AND manual trading are allowed** in the challenge, only when supported by the broker/simulator and subject to the same daily/total equity limits, stop-loss, per-order risk, open-risk ceiling, integrity and anti-manipulation rules. This is not authorization to start real trades, operate organizational robots, market-signal execution or third-party paid bot services.
- A completed trade means a reconciled closed BROKER POSITION with a stable external position ID and data source. Repeated fill/execution events for the same position, pending/unverified rows, entries without a confirmed close and activity outside the purchase's 28-day window **do not** increase the count. Historic rows lacking position IDs require trustworthy reconciliation; do not automatically infer one trade per event.
- **28-day challenge trading window from verified purchase**. No trades may qualify after the end of that window. Inactivity notice at 14 days and grace at 14 days are informational and do not extend the window.
- Upon passing both stages, KYC, lawful funding and broker approvals, **Plan 1** starts at **$100**; Plans 2–10 have their own larger proposed starting tiers, contingent on independent capital backing and release approval.
- All **14 USD levels:** 100, 200, 400, 800, 1500, 3000, 5000, 10000, 20000, 35000, **50000**, 70000, 85000, 100000.
- **30-day promotion window**, at most one level per qualifying window, profit goal **3.6%**, at least **12 valid trading days**, no risk breach, max day 32%, trustworthy reconciled evidence and verified funding for the next tier.
- Per-trade stop-risk max **0.8%** and cumulative open stop-risk **1.6%** of tier capital; block an order if broker minimum lot/stop distance cannot fit.
- Monthly net profit sharing **70% trader / 30% company**, on cumulative realized net P&L exceeding previously *allocated* profit. Losses must be recouped first; no double payment.

## Ten MOJ PROP variants — owner-active Plan 1 + nine inactive funding plans

The owner's Plan 1 remains **30 TRX** and begins its **conditional** real-funded
ladder at **$100**. Nine temporarily **inactive** proposed plans offer differentiated starting
capital and entry fees. Every plan shares the same immutable v1.2 rules:
two simulated phases, 28 total calendar days, minimum six valid trading days
per phase, 50 unique reconciled closed positions across both phases combined,
one Instagram + one Facebook post retained 28 days, trading bots permitted,
9.6%/6% net stage goals, 4% daily and 8% total drawdown, 32% consistency,
0.8% risk/order, 1.6% open risk, 70/30 split and a 14-step capital ladder.

| Plan SKU | Starting capital if funded (USD) | Proposed entry fee (TRX) |
|---|---:|---:|
| MOJ-PROP-01 | 100 | **30 (original)** |
| MOJ-PROP-02 | 200 | 45 |
| MOJ-PROP-03 | 400 | 75 |
| MOJ-PROP-04 | 800 | 120 |
| MOJ-PROP-05 | 1,500 | 200 |
| MOJ-PROP-06 | 3,000 | 330 |
| MOJ-PROP-07 | 5,000 | 500 |
| MOJ-PROP-08 | 10,000 | 800 |
| MOJ-PROP-09 | 20,000 | 1,250 |
| MOJ-PROP-10 | 35,000 | 2,000 |

These are **ten separate product identities**, not ten new websites or ten
verified active brokerage accounts. **Owner declares Plan 1 funded and active**, but independent evidence of its broker funding, actual TRX checkout and end-to-end settlement has not been provided to this code branch. Plans 2-10 remain on an explicit temporary owner funding hold and MUST NOT become sellable even if paper readiness attestations are true. No SKU is automatically approved for checkout here. **Prices for
Plans 2–10 are internal commercial proposals**, not binding offers, and need
explicit rate-sheet approval before any customer contract or TRX invoice.

All plans may progress only forward in the original **14 funded capital tiers**
(up to $100,000) after independent funding, KYC/AML, broker, legal and
operational verification. A higher-tier buyer may never be silently allocated
a lower starting tier. The existing 30-day one-tier-at-a-time funded
promotion model remains intact.

Implementation: `plans.py` is the sole ten-plan catalog;
`PropChallengeEnrollment.plan_code` is immutable per confirmed purchase
(migration `0006_ten_plan_enrollment.py`); both challenge phase accounts
must use its exact starting tier and P&L baseline. `challenge_commerce.py`
performs **tier-specific** treasury/cash/contract/broker readiness. The
proposed cohort economics in `economics.py` use the matching plan's fee
and funding reserve instead of treating every customer as a $100 liability.
`moj_prop_page.py` publishes nonpayable read-only cards in 20 languages;
the authenticated dashboard identifies the selected plan. Neither component
creates invoices, withdrawals, live trades or customer registrations.

**No financial side effects:** no live charging, seller payout,
funding approval, broker access, social posting or production deployment.
Reconciled paid invoice, product acceptance, independently verified treasury,
contract and country compliance must precede any external launch.

## Corrected four-week challenge and social posting requirement — new v1.2 buyers

- The **entire two-phase simulated trading challenge lasts 28 consecutive
  24-hour days** beginning with a **verified paid invoice timestamp**, not
  signup time or a self-reported purchase date. The verified trade ledger
  must contain only trades inside this time window. Each stage retains a
  minimum of **six valid trading days** and the unchanged profit and risk
  rules. The 30-day *funded-tier promotion period* is separate.
- **ONE original Instagram post AND ONE original Facebook post total** for
  the complete purchase; **NOT one post per trading day and NOT two posts
  per phase**. Publish each within 24 hours of confirmed purchase and keep
  it publicly accessible for at least **28 x 24 hours after its own post time**.
  A final independent review may therefore happen up to a day after the
  trading window closes, but never extends the trading deadline.
- Two distinct URLs are linked to a single independently settled purchase
  (`PropChallengeEnrollment`), and both challenge phases share this
  enrollment. Missing or removed posts defer passing; they do not fabricate
  a risk violation or trigger forfeiture of legitimate realized profit.
- Neutral, accurate content is permitted, without invented profit records,
  recommendations, fake praise, or pressure to recruit others. Both posts
  must conspicuously state that publication is a commercial condition of
  participation. Local advertising rules and Meta platform policies must
  be reviewed before selling challenges in a particular jurisdiction.
- `PropSocialEvidence` stores the two privately reviewed URLs, author,
  disclosure, continued public visibility and independent approval no
  earlier than 28 days after posting. The trading portal is read-only;
  none of these functions publishes, schedules or edits social posts.
- The permanent prohibition concerning Instagram
  `Dr.mojtaba.rozegar` is unchanged. Never publish to that account.
- Old contracts use their original terms; do not impose this rule
  retroactively. The proposed v1.2 terms were corrected *before paid
  launch*. The public 20-language copy is subject to legal localization
  review, and paid enrollment remains switched off.

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
