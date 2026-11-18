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

## Static mail-only fallback (source only, not live)
A separate /b2b/ English static trade page and /b2b/privacy/ have been added under public/b2b/. This path uses only an official mailto and does not claim CRM registration or a tracking reference. A link is added to public/index.html. Before releasing, verify whether a live public_html/b2b page already exists, preserve its immutable original and use a narrowly scoped static release; never run the generic destructive cPanel deployment script. Confirm public HTTP GET after publication and do not advertise as live earlier.

## Reproducible exact static artifact (no deployment)
The two independent /b2b/ and /b2b/privacy/ HTML assets are now built into a deterministic ZIP with exact SHA-256 hashes and an explicit not-deployed manifest; no user data, server credentials or checkout logic is included. The package workflow runs in GitHub-hosted CI, not on the cPanel factory runner; it cannot install pages. The artifact includes only b2b/index.html, b2b/privacy/index.html and MANIFEST.json. Never run generic cPanel deployment to publish it; before a separately authorized create-only site publish, prove absence of both live targets and review host route ownership. Full-site backup/restore remains the gate for the separate Django+CRM app release.

### Exact reviewed Git file identity enforcement
The two public static B2B HTML files are now pinned to verified Git blob objects in the package builder, not merely hashed after loading. Even well-formed changed HTML fails before ZIP assembly. Git object hash provides exact source byte identity but is **not** a digital owner authorization. Source-only regression tests cover this denial.
