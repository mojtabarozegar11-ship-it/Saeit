# Tala subsite

The public interface is restricted to `/tala/`. Its deploy workflow stages `public/tala/**` and swaps only `/home/zomorod2/public_html/tala`, keeping a recoverable copy before deployment. It never modifies root `.htaccess`, Passenger, Django configuration, application files, databases, or neighboring site paths.

The current release is an installable static progressive web app with an editorial showroom, a client-side jewelry estimate, a daily learning article, five market-analysis frames, and a map of business modules.

## Not connected yet

The interface explicitly marks these services as unavailable until their real dependencies are configured and tested:

- A licensed, attributable gold and coin quote source and an accurate Tehran business-day schedule.
- Server-side orders, inventory, authentication, payment processing, accounting records, audit history, and staff permissions.
- Original, reviewed daily educational and market content with source timestamps.
- Authorized social accounts and a human-approval process for outbound posts.

The calculator is an educational estimate only and does not account for tax, actual market price, labor rules, gemstones, or a formal invoice. It does not persist records or transfer funds.
