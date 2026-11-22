# MOJ PROP — 21 localized canonicals missing from submitted root sitemap

Date: 2026-11-22. **Source-only change; no server deployment, payment, CRM write or paid promotion.**

## Why this matters for first revenue

Verified Google Search Console account `https://mojplaywin.com/` yielded 13 site-wide organic clicks and 443 impressions during 2026-11-01 through 2026-11-20, and **zero page performance rows containing `/moj-prop/`**. Lack of rows is not proof of a Google index ban, but there is no measured search exposure for the product in that window.

The connected GSC sitemap table reported `https://mojplaywin.com/sitemap.xml` submitted, with zero reported errors and a last Google download of 2026-11-18. This live root XML contains 20 total <loc> entries, only **14** MOJ PROP URLs. Its separately declared `https://mojplaywin.com/moj-prop/sitemap.xml` exposes 35 MOJ PROP URLs, including **21 indexable language paths absent from the submitted root**.

A separate 2026-11-22 read-only audit fetched **all 21 paths**: each returned HTTP 200, declared `index,follow`, and had a self-referential canonical. All but the Nigerian Pidgin page emitted 20 hreflang alternatives. This patch does not synthesize new translations or claim Google has indexed them.

## Exact source change

Edit only the cPanel effective root PHP *mirror*:

`ops/cpanel/mojplaywin/sitemap/_mpw_sitemap_three_indexable_20261017.php`

- Preserve the existing 12 extra English MOJ PROP URLs and the two baseline URLs in Django passthrough.
- Append exactly the 21 verified language URLs to the existing `$mojPropPaths` for both low-count and normal branches.
- Preserve two independently observed **live-only** additions that were not in the GitHub mirror: public `/mojtaba.bot.ai/` landing and public product pages `/store/product/{72,225,879}/`.
- Never add buyer intake, checkout, recovery, invoice, admin, private, metrics or payment URLs to a sitemap.
- Retain same-host HTTPS source validation, fallback, XML well-formedness, path deduplication, URL safety and narrow PHP source root.

## Deployment stop conditions

No mutation of the active `/home/zomorod2/mojplaywin.com/design-preview-20261017/_mpw_sitemap_three_indexable_20261017.php` is authorized by this source PR. The live PHP had Git Blob `bc9dfd9d80b6658d847d8ac3cf0d9c21036818a3` on this audit (unlike source main `d09c122900bda2081730b420ef83c1213559c3b8`). Its two additions must survive any future cutover.

Before any separately authorized limited release:
1. Recompute live PHP SHA and Git Blob immediately prior; reject unexpected drift.
2. Save the original PHP and a matching independent, owner-only restore receipt with digest on the host (not a public GitHub backup).
3. Inspect only the documented root sitemap rewrite; leave `.htaccess` and Django untouched.
4. Validate `php -n -l` and run the source tests plus real HTTP GET parity on the authorized host.
5. Verify root XML remains HTTP 200, `urlset`, all preexisting URLs retained, and all 35 MOJ PROP URLs are present once; payment/checkout paths absent.
6. Restore the backup on mismatch; check HTTP output after cache expiry. Do not change WSGI, DB, cron, financial gates or social accounts.

Search-engine discovery can take time and is not a sale or visitor guarantee. The next measurable outcomes are Search Console impressions and clicks to MOJ PROP, qualified CRM leads, written offers, and collected valid orders after release gates.

## Traffic quality caveat

In a privacy-preserving classification of HTTPS logs (2026-11-16 through 2026-11-21), 479 of 672 MOJ PROP landing GETs were explicitly curl/Python/crawler User-Agents; 435 of 554 intake GETs were likewise automated. Real user agents can be disguised and direct visits can omit referrer. **No completed intake POST** was visible in the scoped log, and the active CRM had **0 requests / 0 manual offers** on audit. Do not describe these GET counts as verified human visitors or sales.

Do not publish on the prohibited `dr.mojtaba.rozegar` account. No spending or paid indexing submissions without the owner's explicit per-item approval.
