# Tala subsite

The public interface is restricted to `/tala/`. A local `.htaccess` sets `PassengerEnabled off` and `DirectoryIndex index.html` inside this directory only, so the static app can bypass the root Passenger application without changing the parent configuration. Its deploy workflow stages `public/tala/**` and swaps only `/home/zomorod2/public_html/tala`, keeping a recoverable copy before deployment. It never modifies root `.htaccess`, Passenger, Django configuration, application files, databases, or neighboring site paths.

The current release is an installable progressive web app. Search, product detail pages, a device-local inquiry draft with text export, a six-article learning library, five educational market-analysis explanations, and the jewelry estimate work in the browser. These features do not submit an order or represent live market data. Inquiry drafts remain in the visitor's own browser storage and are not visible to staff. An isolated `/tala/api/health.php` probe reports only whether PHP, PDO SQLite, and private-home writing are available; it stores no records or secrets.

## Not connected yet

The interface explicitly marks these services as unavailable until their real dependencies are configured and tested:

- A licensed, attributable gold and coin quote source and an accurate Tehran business-day schedule.
- Server-side orders, inventory, authentication, payment processing, accounting records, audit history, and staff permissions.
- Original, reviewed daily educational and market content with source timestamps.
- Authorized social accounts and a human-approval process for outbound posts.

The browser-only interactions are not the operational back office. They do not provide shared inventory, customer accounts, official accounting, server backups, audit history, or payment processing. The estimate and market analysis are educational tools; they are not quotes or investment advice. Company contact information must be supplied before a mail link can address the business directly.

The calculator is an educational estimate only and does not account for tax, actual market price, labor rules, gemstones, or a formal invoice. It does not persist records or transfer funds.
