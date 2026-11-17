# MOJ PROP: first genuine prospect — production contact acquisition runbook

**Date:** 2026-11-18. **Status:** PRELAUNCH, NONPAYABLE; **NO production release**.  
**Product:** **MOJ-PROP-01 REAL proposed two-stage simulated evaluation + conditional separately contracted company-funded trading**, never educational MOJPROP-STARTER30. Price **30 native TRX (30,000,000 SUN) is not presently payable**. One global **28-calendar-day evaluation period across both simulated stages**, not two separate 28-day clocks. No employment, real capital, profit or payouts promised.

## Verified external conversion surfaces

- `GET https://mojplaywin.com/moj-prop/`: HTTP 200, existing *static* page and JavaScript-driven **generic** draft request form. **Not** proof of MOJ-PROP-01 paid availability, validated POST, or genuine buyer. Do not count as conversion.
- `GET https://mojplaywin.com/moj-prop-intake/`: HTTP 200 JSON with CSRF token; `?format=html` also returns JSON, **not** a native fallback. This legacy API is generic; no fake POST/customer should be generated to force a green result.
- `GET https://mojplaywin.com/moj-prop/contact/`: HTTP 200, one first-party `mailto:` link. The **publicly published recipient is `mojtaba.rozegar11@gmail.com`**, a connected owner mailbox, **not** `mojplaywin@gmail.com`. This link is the **one confirmed accessible route for VOLUNTARY manual prelaunch enquiries**.
- `GET /contact/`: HTTP 200, 3 published mailto links; do not assume they have the same recipient.
- `GET /moj-prop-interest/form/` and FA `?lang=fa`: HTTP 404 as of verified check; `/moj-prop-v141-info/` and `/moj-prop-status/?format=html` also 404; `/moj-prop/plan1/` HTTP 404. **Do not put these routes into live prospect CTAs.**
- `GET /moj-prop/contact/` does not itself persist a CRM lead; sending a message from a prospect's own mail client is optional and only the delivered mailbox response counts as an actual contact.

Evidence: [Actions #44175862981](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44175862981), [#44177201320](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44177201320), [#44177559844](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44177559844).

## Current CRM and incoming Gmail reality

- [Actions #44174763030](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44174763030): authenticated pinned SSH via factory VPS to cPanel, discovered live candidate Django Python, executed **aggregate SELECT only** for `core.models.MojPropRequest` on MySQL. **0 total records, 0 last seven days, 0 last 30 days, all workflow statuses 0**. No personal rows queried. This is **candidate site DB**, not proof of a complete inventory of every connected store, payment ledger or any independent WordPress/subsite.
- Connected MojPlayWin Gmail `mojplaywin@gmail.com`: since 1 Oct 2026, searches of brand/challenge terms returned the support message from LiteFinance plus its reply draft, **no customer-qualified inbound in those scoped searches**. Incoming LiteFinance reply requests a shorter query; **it does not grant written brokerage/third-party-trader permission**.
- Connected owner Gmail `mojtaba.rozegar11@gmail.com`: brand-term search excluding GitHub notifications and automated Task Update messages returned **0 incoming brand-term matches** since 1 Oct 2026. Do **not** confuse dozens of CI failure alerts and Task Update emails with new prospects. This targeted search is not an exhaustive audit of every generic email.

## Source fixes prepared, NOT deployed

Source-only Draft **#2699** stacked on #2695, #2693, #2690, #2688:
1. Six dead `href="/moj-prop-interest/form/"` links in `templates/moj-prop-v4/index.html` replaced with observed public `/moj-prop/contact/`. English and Farsi labels changed from unserved "consent form" to truthful free official contact.
2. In the prepared static source only, broken `/moj-prop-status/` private receipt lookup form is hidden; customers see a warning to **keep receipt bearer tokens OFF EMAIL** and not to assume status lookup or registration has been issued. No backend/payment code touched.
3. [GitHub Actions #44176874349](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44176874349) finished **12/12 static route-content regressions, embedded JavaScript syntax PASS, actual public contact HTTP 200+mailto PASS**. A green test is not proof that the source changes are live.

## First organic marketing asset (not sent or published)

Connected Metricool brand: `dr.mojtaba.rozegar`, Facebook and Instagram connected.
- A **Facebook-only** preview post ID `432032176` saved as `draft:true`, `autoPublish:false` and independently verified still PENDING/DRAFT.
- It accurately describes **MOJ-PROP-01 as prelaunch**, no live customer account or fee collection, and sends voluntary visitors to the **already-live contact page**: https://mojplaywin.com/moj-prop/contact/
- Draft planner: https://app.metricool.com/planner/calendar?blogId=7317306&openWithPostUuid=-4130925392959815592
- Public publication and paid advertising **not authorized by this source work**. Regulatory eligibility and platform financial-service promotion rules require review. Do not claim draft = reach, lead, or buyer; do not spend money.

## Actual next conversion work, in strict order

1. Confirm owner/legal approval for a narrowly framed **nonpayable first-contact** information announcement and avoid finance/payout/employment guarantees. The draft is available for review.
2. When a *real unsolicited or voluntary prospect* contacts the public email, verify origin, lawful jurisdiction and that they knowingly request MOJ-PROP-01. Never invent a lead, purchase or test contact. Keep consent restricted to answering the specific inquiry, no marketing re-use without separate permission.
3. Reply individually only with applicable legal terms/eligibility/risks and no payment instructions before source, finance and refund gates; owner approval needed before sending actual emails.
4. Establish fresh full DB+app+media encrypted backup outside the 30-GiB cPanel quota and verify independently isolated restore. Latest private VPS backup with consistent metadata is ~15.5 days old and **not** independently restored, per [Actions #44172003842](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/44172003842).
5. Match real Passenger source, installed model/migration and routing; stage a minimal official **browser-native, no-charge enquiry + secure private receipt** under owner-reviewed, pinned rollback release. The new source files are not currently installed on cPanel; never bypass migration/backup gates.
6. Once a bona fide customer voluntarily submits, verify CRM persistence and receipt, never count an HTTP 200 GET or email draft as accepted enrollment.
7. Secure signed buyer-facing terms, country/KYC/AML/refunds, independent market and risk data, broker's **written** permission for company-owned real account delegation, and demonstrated available capital.
8. Only then propose **separate case-specific owner approval** for enabling 30 TRX unique on-chain settlement and real challenge delivery. No false promises of automatic income.

**Verdict:** first public contact entrypoint *exists*; source-only dead-link/receipt UX fixed; no actual qualified prospect or paid buyer was established in this cycle. Production release and paid challenge remain NO-GO. No new fees, server-side writes, customer simulations, outgoing messages, production deployments, migrations or deletions.
