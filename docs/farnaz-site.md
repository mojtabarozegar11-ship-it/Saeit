# Farnaz global English subsite

Farnaz is a Django-powered English-language drafting and design studio at `https://mojplaywin.com/farnaz/`.

## Scope and safety
- The integration adds one URL prefix and one Django app. Existing routes, homepage templates, and independent sub-sites are left in place.
- The deploy workflow sends only the new `farnaz/` app and a scoped installer to the host. The installer patches the live settings and URL files with unique additive entries, records file-hash-verified backups, applies only the Farnaz migration and restarts Passenger.
- If the new page or existing homepage/admin health checks fail, the workflow restores only the two config files. It keeps the app tables so any enquiry data remains recoverable.
- Portfolio cards are clearly labelled as concept samples; no client work, professional approvals, testimonials or performance claims are invented.
- The inquiry form uses Django CSRF middleware, field validation, consent text and a honeypot. Enquiries are visible in Django admin.

## Django admin
Open `/admin/` using the site's existing staff account. The Farnaz section manages services, portfolio concepts, offers, prices, checkout status and incoming enquiries.

## Bank gateway
Checkout is disabled until the owner chooses the payment provider and completes merchant onboarding. The site does not collect card data or record a payment as successful. Before enabling checkout, configure a supported gateway, protect its merchant secrets in hosting environment variables, validate signed server-to-server callbacks, and test success, rejection, cancellation, retry and duplicate callbacks in the provider sandbox.
