# Zomorod Melal: B2B trust conversion and customer request closure (2026-11-18)

Scope: source-only changes; no live deployment, external payments, synthetic customers or financial commitments.

Delivered paths:
- /en/partners/: English supplier profile, OEM/ODM RFQ form, official channel.
- /company/: visible international access, CRM lead form with receipt.
- /company/inquiry/: canonical POST-only endpoint with CSRF, validation and honeypot.
- /company/inquiry/receipt/<signed_token>/: HMAC signed private status link, no personal data, no-store and noindex.
- /privacy/: customer data handling notice. Site-specific provider and retention facts are pending independent verification.
- /: company trust and supplier contact calls to action.

Saved leads are readable in the existing authorized company CRM. Optional SMTP staff notice defaults off; enable only when company SMTP verified by owner and env COMPANY_INQUIRY_NOTIFICATION_ENABLED=true. Needs COMPANY_TRADE_EMAIL and DEFAULT_FROM_EMAIL.

Before production: check official registration documents, inspect actual live site availability, run Django checks and full regression suite, verify WAF / server rate limit and HTTPS, verify valid anonymous form flow on controlled staging, confirm mail and back-ups, then obtain deployment approval. No claim of live activation, sales or independent trust metric is made by this source change.
