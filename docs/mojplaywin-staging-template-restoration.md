# MojPlayWin staging-template restoration — controlled migration

Target: https://mojplaywin.com/
Visual reference: https://staging.zomorodmelal.ir/
Working branch: restore/mojplaywin-staging-template-20261009

## Verified source files (branch factory/integration-control-bridge-20261005)
- core/templates/base.html — Zomorod Melal shell; references site/main.css, site-standard-v1.css, luxury-pages.css, page-themes.css, site-standard-v2.css, site-rtl-standard-v1.css, site-polish-v3.css, hero-images-v1.css.
- core/templates/brands/mojplaywin/base.html — separate MojPlayWin shell; links site/mojplaywin.css and contains brand-specific navigation, canonical URL, meta tags and logo reference.
- core/static/site/mojplaywin.css — MojPlayWin styling.
- core/static/site/main.css — Zomorod styling.
- core/brand_views.py — MojPlayWin catalog routing and views.
- core/brand_seo_views.py — domain-specific SEO routes.

## Non-negotiable migration conditions
1. Obtain and verify actual staging HTML/CSS/assets or a trustworthy backup; repository base.html is NOT proven identical to deployed staging.
2. Preserve MojPlayWin's own brand name and logo; never substitute Zomorod Melal identity, logo, legal text, company details or canonical URLs.
3. Migrate presentation templates and their required static dependencies only. Do not overwrite product, user, payment, game or database modules.
4. Keep existing MojPlayWin URL endpoints and domain-aware routing.
5. Validate missing assets, mobile layout, HTML/Django template syntax, security headers, canonical and OpenGraph URLs.
6. Capture backups and a rollback commit/deployment plan before any production change.
7. Run Django checks and relevant tests in staging; visually compare screenshots of reference and candidate.
8. Production deployment requires separate explicit owner approval after test evidence.

## Current state
- GitHub restoration branch created.
- Source template and CSS locations identified.
- Live staging and production websites not accessible through current public-web fetch.
- Exact visual-template match not established.
- No production deployment, no database changes, no remote desktop use.

## Next implementation gate
Acquire actual reference template or backup and compare against the candidate GitHub files before writing replacement template code.
