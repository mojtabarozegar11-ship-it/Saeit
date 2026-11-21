# MOJ PROP — qualified professional trader enquiry and static discovery

Published **21 November 2026**; exact source of the already-live changes is preserved in this branch.

## Public English URLs

- https://mojplaywin.com/moj-prop/selected-traders/ — professional trader selection and conditional compensation information; direct prepared email enquiry.
- https://mojplaywin.com/moj-prop/sitemap.xml — independent, public XML sitemap with 14 exact canonicals for English MOJ PROP pages, including education guides and the selected-traders page.
- https://mojplaywin.com/moj-prop/ — live site homepage with a visible link to the independent XML sitemap.
- https://mojplaywin.com/moj-prop/contact/ — live official contact page linking to the selected-trader policy and a prepared enquiry.

## Two distinct programmes — mandatory clarity

**Starter 30:** A paid **simulated** evaluation, with virtual balances and any conditional verified-performance rewards governed by the published challenge terms. Buying/passing does not mean hiring, real-capital allocation, salary, employment or entitlement to expenses.

**Company-selected professionals:** MOJ PROP separately identifies, verifies, approves and individually engages traders, who may trade permitted company-controlled **real brokerage** accounts using the company's own allocated funds. On an approved, signed appointment, compensation includes a contractual share of verifiable net real trading profit, a monthly salary and company-paid/reimbursed approved working expenses. Figures, obligations and conditions must be agreed individually. No customer deposits, guaranteed profit or automatic jobs are offered.

## Qualified enquiry route

The existing public contact address shown on `/moj-prop/contact/` is used for a prepared `mailto:` expression-of-interest link; **no emails are sent automatically**, no backend or new form handles sensitive submissions and no capital is requested. The user may provide markets, experience, risk management approach, non-sensitive performance evidence and general availability. No credentials, keys, IDs or statements should be sent unsolicited.

This addresses a specific conversion blocker: the previous professional-trader page led only to the generic contact page with no distinct enquiry subject. Conversion from clicking an email link to a delivered, qualified application remains unverified and cannot be counted as a hire.

## Live execution evidence

Static cPanel document root: `/home/zomorod2/mojplaywin.com/moj-prop/`. Backup directory:
`/home/zomorod2/separated-backups/20261121/mojprop-qualified-trader-leads/` including SHA-256 `manifest.json`, original versions of the live homepage, contact and selected-trader pages, plus a copy of the new sitemap.

Verifications completed against actual public HTTPS responses:
- Six key pages returned HTTP 200, each had its exact self-canonical and live bytes matched on-disk bytes.
- The new public XML sitemap returned HTTP 200 `application/xml`; **14/14** entries were unique and referred to live HTTP 200 pages with matching self-canonicals.
- The trader enquiry is a real `mailto:` link to the **existing public official contact address**, with an encoded subject and appropriate non-sensitive outline; no POST or email send was attempted.

Source contents in `templates/moj-prop/selected-traders/index.html` and `templates/moj-prop/sitemap.xml` match the live artifacts. **The historical `templates/moj-prop/index.html` and `templates/moj-prop/contact/index.html` differ from the host's current public versions**. These should not be overwritten by a broad source deployment. The latest live narrowly edited versions remain on the host with sha-backed rollback copies. Keep future releases isolated to a verified, bounded static scope.

## Unresolved, do not overstate

- Live root `https://mojplaywin.com/sitemap.xml` and `https://mojplaywin.com/robots.txt` are still Django-served and may not reflect the already-merged source changes; do not run a general Django deployment.
- An independent sitemap and IndexNow notification improve discovery opportunity but do not prove indexing, human visitors, candidate applications or sales.
- The shared first-party analytics script measures opt-in page activity but does **not** currently track external `mailto:` completion; neither sent messages nor hires should be inferred.
- No hiring contract, salary budget, real brokerage access, trades, payments, obligations, wallet changes, database migration, factory start or service cron activation was performed.
