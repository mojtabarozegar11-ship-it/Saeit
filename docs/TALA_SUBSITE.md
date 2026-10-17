# Tala subsite

The public interface is restricted to `/tala/`. A local `.htaccess` sets `PassengerEnabled off` and `DirectoryIndex index.html` inside this directory only, so the Tala app bypasses the root Passenger application without changing the parent configuration. Its deploy workflow stages `public/tala/**` and swaps only `/home/zomorod2/public_html/tala`, keeping a recoverable copy before deployment. The only database used by this panel is Tala's own SQLite file in its private folder; it never modifies the root database or neighboring site paths.

The current release is an installable progressive web app. Search, product detail pages, a device-local inquiry draft with text export, a six-article learning library, five educational market-analysis explanations, and the jewelry estimate work in the browser. These features do not submit an order or represent live market data. Inquiry drafts remain in the visitor's own browser storage and are not visible to staff. An isolated `/tala/api/health.php` probe reports only whether PHP, PDO SQLite, and the private Tala data directory are available; it stores no records or secrets. The isolated data directory is `/tala/api/.private`, denied by its own `.htaccess` and set to mode `0700`. The deploy job pauses API writes briefly, backs up the current subsite, and carries the hidden SQLite database into the staged version so releases do not erase business records.

## Not connected yet

The interface explicitly marks these services as unavailable until their real dependencies are configured and tested:

- A licensed, attributable gold and coin quote source and an accurate Tehran business-day schedule.
- Online orders, verified live inventory, payment processing, tax-compliant accounting, and integration with the company's official books.
- Original, reviewed daily educational and market content with source timestamps.
- Authorized social accounts and a human-approval process for outbound posts.

The storefront and estimate remain browser tools. The internal panel stores shared records on the Tala server, but it is an operational journal rather than certified accounting; it does not reconcile inventory or process payments. The estimate and market analysis are educational tools; they are not quotes or investment advice. Company contact information must be supplied before a mail link can address the business directly.

The calculator is an educational estimate only and does not account for tax, actual market price, labor rules, gemstones, or a formal invoice. It does not persist records or transfer funds.


## Internal management panel

The isolated `/tala/admin/` panel supports one-time admin bootstrap, password-hashed staff logins, purchase/sale/production/expense journal entries, immutable reversal entries, audit hash chaining, summary totals, and CSV export. It uses PHP PDO SQLite in a private directory and preserves the database across subsite releases. Initial administrator setup uses a single-use random token; the unhashed token is never stored in the public repository. The owner must use that token to create the first username and password. The journal is not a legally certified accounting or tax system.
