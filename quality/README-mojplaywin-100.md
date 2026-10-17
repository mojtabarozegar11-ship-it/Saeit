# MojPlayWin — strict 100/100 release contract

**Status: NO-GO until every one of the 19 independent dimensions is verified.**

Scope: **only main `https://mojplaywin.com/` and its owned main pages.** Do not modify or interfere with independent child sites, most critically `/mojtaba.roozegar/`, its 93 articles, pictures and SEO; or `zomorodmelal.ir` and its sites.

## Meaning of 100/100

An average, rounded score, success rate or attractive screenshot is NOT 100/100. For every applicable quantitative criterion, acceptance is the exact target; for operational and manual criteria the result is **pass only with independently reviewable evidence**. Missing, partial, unsupported and untested results are failures for the purposes of release authorization.

**Release is forbidden if any gate is unverified.** A passing automated suite does not imply passing live payment, product, security, backup or other site-integrity checks.

### Acceptance inventory

The machine-readable register is `quality/mojplaywin-acceptance-100.json`, checked by `scripts/mojplaywin_release_100_gate.py`.

1. **Approved design:** main page presents the approved spatial black/gold identity, globe, real MojPlayWin emblem and exactly three functional orbital rows, not the previous ordinary-card-only layout. Owner must visually accept mobile and desktop reference comparisons.
2. **Real interactions and responsive layout:** keyboard, touch/swipe, mouse dragging, left/right controls, start/pause, reduced-motion, no visual cut-off or horizontal overflow, no dead links.
3. **Every page/content:** preserve the complete before/after route inventory, 10 homepage guides, full specialty articles, descriptions, metadata, translations, forms and menus; no placeholder pages.
4. **Images/logo:** originals and rights retained, appropriate distinct media, no broken files/alternative text failures; verify the owner-supplied official logo is the correct original asset.
5. **Mobile performance 100:** Lighthouse **1.00** Performance for **every main-site page**, not merely a sample, with reproducible device/network runs.
6. **Desktop performance 100:** likewise all pages.
7. **Accessibility 100:** Lighthouse 1.00, practical keyboard/screen-reader support and WCAG 2.2 AA checks.
8. **Best Practices 100:** Lighthouse 1.00, no unresolved technical console issues.
9. **SEO 100:** Lighthouse 1.00, verified self-canonical URLs, sitemap, structured data, indexing and links.
10. **Products:** inventory and database integrity pre/post; IDs, owner links, images, digital files, titles, currency, price, discounts, status, licenses, entitlements and fulfillment absolutely unchanged.
11. **Real ETH/TRX and other existing currency payment gateways:** wallet destinations, records, verification, callbacks, order handling, settlement and idempotency unchanged. Verify without charging real customers.
12. **Django admin:** authenticate and confirm safe staff access, permissions and listings for real products/orders/agents; no shared admin schema changes.
13. **Agents:** ownership-isolated execution verified by worker heartbeat, queued/failed/succeeded task evidence; an active flag alone is inadequate.
14. **Security/privacy:** authenticated checks, secrets protected, HTTPS, sessions, headers, CSRF/XSS and zero unresolved critical issues.
15. **Protected sites:** before/after URL, media, data, permissions and SEO smoke tests of all protected sites, particularly Mojtaba Rozegar personal site.
16. **Verified restore and rollback:** real restorable pre-change backups and a rehearsed recovery process; safe Passenger/deployment isolation.
17. **Functional services:** real support/contact/requests and other enabled flows work end to end; no decorative dead controls or payment claims without evidence.
18. **Footer 2022:** exact `© 2022 MojPlayWin. All rights reserved.` on both main-site template families, without changing other sites.
19. **Final authorization:** explicit owner sign-off on verified implementation, then controlled live release and independent post-release smoke testing.

## Current measured evidence (17 October 2026, draft branch)

The first offline Lighthouse run of seven page types, two viewport modes, reported 100 for accessibility, best practices and SEO across the sample. Desktop Performance was 100 in all seven; mobile Performance was **home 96, store 89, research 94, agents 96, AI 100, blockchain 96 and support 91**. This was **NOT an acceptable 100/100 result**. Importantly, the initial offline snapshot workflow forced all below-the-fold lazy images to eager-load; that behavior has been corrected so the next Lighthouse run audits the original lazy-loading HTML. Fresh scores must be measured before reporting improvement.

The existing draft originally **did not** implement the approved three-ring orbital concept. New ring markup, scalable original globe art, CSS and controls have now been staged but are **not yet fully verified** by the latest browser and Lighthouse runs.

CI and Django tests cover only source/runtime test-environment behavior. Currency payment success, full real product inventory, protected-site integrity, admin login and agent heartbeat remain **UNVERIFIED ON PRODUCTION**.

## Publication procedure

1. Finish all route, media, mobile and interactive tests in the isolated preview. Retain screenshots, source commit hash and audit log.
2. Verify the complete route inventory against the current live site; reconcile any missing legacy Django/cPanel routes without touching independent sites.
3. Verify recoverable backups of the shared live database/media/application, and obtain a safe publication path proven not to restart or overwrite other apps.
4. Record authorized **read-only** inventory/hash comparisons on products/orders/licensed files and payment configuration, plus noncharging ETH/TRX smoke checks.
5. Confirm Django admin and staff-only agents genuinely work, using evidence of recent executions.
6. Obtain the owner's visual sign-off on the actual rendered site and exact logo.
7. Mark individual gates passed only after inspecting genuine supporting evidence; never fabricate or round.
8. Run the release validator with `--require-ready`. Refuse merge/deploy if it fails. (The shared GitHub main branch currently has no mandatory branch-protection checks; the workflow alone cannot prevent another actor from bypassing the gate.)
9. On authorized release, run complete post-deploy regression; rollback at once if any protected file, product, order, payment flow or site differs.

**Do not claim 100/100 or live deployment before those steps succeed.** This is a quality policy for the draft main-site redesign, not evidence that the site is already perfect.
