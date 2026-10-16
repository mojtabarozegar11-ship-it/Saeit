# Farnaz under MojPlayWin

The Farnaz route is an isolated Django page at `/farnaz/`. The existing `/admin/` remains the Django administration entry point. Farnaz-specific content and incoming inquiries are listed there under the labels "Farnaz services", "Farnaz portfolio", "Farnaz offers", and "Farnaz enquiries".

## Scope and safety

- No existing route is removed or renamed.
- All initial portfolio cards are clearly marked as conceptual examples.
- New content tables are additive and have a reversible schema migration; seeded examples are left in place on migration rollback.
- Inquiry submissions require CSRF protection, a privacy consent checkbox, and pass through Django validation. A honeypot field catches basic automated submissions.
- No payment is recorded as successful and no bank card data is collected by this page.

## Bank gateway setup

The checkout switch for each offer is off by default. Before enabling real payments, select the acquiring bank/provider, configure the merchant account and callback URL in the hosting environment, implement and test the provider's signed request and server-to-server verification, and test success, rejection, cancel, retry, and duplicate callbacks in sandbox. Do not enable `checkout_enabled` until all those checks have passed. Never put merchant secrets in GitHub source or in public page fields.

## Admin

Use the existing Django admin at `/admin/`. The owner can edit service descriptions, portfolio cards, digital offer details/prices, and inquiry status. The login continues to use the existing site's staff accounts.
