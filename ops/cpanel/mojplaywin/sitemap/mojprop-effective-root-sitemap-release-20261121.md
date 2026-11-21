# Effective MojPlayWin root sitemap — MOJ PROP English SEO release
Date: 2026-11-21

## Exact live mechanism

The **real** request path for public `https://mojplaywin.com/sitemap.xml` is controlled by the cPanel document-root `.htaccess`, whose exact GET rewrite sends the request to:

`/home/zomorod2/mojplaywin.com/design-preview-20261017/_mpw_sitemap_three_indexable_20261017.php`

This existing PHP file calls the original integrated Django sitemap using **HTTPS only** at `/sitemap.xml?__mpw_sitemap_passthru=1`, validates the returned XML, appends missing site URLs and emits the result. Editing only `core/seo_views.py` in GitHub cannot update the public root route while the PHP rewrite is active. The integrated Passenger app root was observed as `/home/zomorod2/Saeit-mojplaywin-integrated-20261119`, which is distinct from the CLI's `Saeit-staging`; no runtime changes were made.

## Actual one-line scope and verified release

The original PHP root sitemap contained four base Django URLs and four added MOJ PROP URLs, **eight distinct canonical URLs in production**. The only live PHP edit was to change the `$mojPropPaths` array from four to twelve known public English MOJ PROP paths. The PHP's host and method checks, HTTPS-only cURL fetch, XML validation, low-count fallback and other-domain branches were not changed.

The effective public result became **16 distinct canonical URLs**: the eight original, plus eight previously omitted MOJ PROP URLs (Selected Traders, Education index, five risk education guides, and catalog). All 16 responded HTTP 200 in the postflight check, and the 14 MOJ PROP URLs had exact self-canonical tags. The existing /store/ canonical was not altered as it lies outside this release.

Technical checks:
- Preflight SHA-256 pin of PHP and `.htaccess`.
- Source backup before the atomic PHP replace.
- CLI `php -l` succeeded before writing to production.
- Exact public root route HTTP 200; original eight URLs preserved; 16/16 unique.
- `X-MPW-Sitemap-Augmentation: moj-prop-only-low-count` present.
- Passthrough original Django sitemap still HTTP 200 with the original four base URLs.
- Public `/robots.txt` already declares the root sitemap and was **not changed**.
- Root `.htaccess`, database, Django code, app WSGI, Passenger, signals, payments, and factory were **not changed or restarted**.
- Source PHP copy under `ops/cpanel/mojplaywin/sitemap/` was byte-for-byte compared against the updated live host using SHA-256.
- A three-test stdlib regression test parses the site's 14-entry independent sitemap and asserts the effective PHP code adds exactly the twelve paths beyond the two original MOJ PROP base paths. It validates host, HTTPS-only and passthrough safeguards.

## Immutable receipts and rollback

Live PHP before: `3d4e4d50348419e7a3bd08bd71276bf6fbe1e5b64b7768e8383fbcfa75321dcc`  
Live PHP after: `4f4378999094eea203f9cda3c220d83cd7dc580795a045ac772c6a2a343772be`  
Unchanged `.htaccess`: `57dfa57660113a64bd5057cf8e6a1f53152a62c11b72279fb800b4347013ed43`  
Independent static 14-page sitemap: `9a28ab35f6e3940a80cbf7833b3495355cc524329e59506c44bd31f8996b769e`  
Root public output after: `e0568b043cb471df84cc221e2ffe267300530479506efc9b868bfc41cbe656ea`

Host-only separate backup directory:
`/home/zomorod2/separated-backups/20261121/mojprop-root-sitemap-php/`

It contains original PHP, `manifest.json`, and saved public root XML before/after. The rollback is a narrow restoration of the original SHA-pinned PHP using this private backup and independent HTTP validation; a generic cPanel deployment is **not** required and would be inappropriate.

## Release boundaries / business truth

This is an SEO indexing-discovery fix. A public sitemap and successful IndexNow notification do not confirm Google indexing, qualified visitors, sales, payment receipts, actual trader hiring, live brokerage positions, salaries, profit allocations or expense reimbursements. The Starter 30 customer-facing challenge remains simulation-only. Selected professional live traders are a separate conditional company appointment with individually agreed terms. No financial obligation was created.

A source merge does **not** redeploy the PHP to the host; the host was already independently, narrowly updated with rollback support.
