# MojPlayWin isolated release readiness — updated 2026-10-09

## Verified source-control facts
- Draft PR #38: https://github.com/mojtabarozegar11-ship-it/Saeit/pull/38
- Branch: `seo/mojplaywin-40-isolated-20261009`; parent branch: `main`.
- Verified feature commit: `ef63ba364371f9dd881b6c5c8ef1b23e55f28768`.
- At that commit both PR workflows, **CI** and **Django CI**, completed successfully.
- PR metadata at verification: open, draft, mergeable, 18 changed files, no merge.
- 25 product and 15 service editorial specialty pages, directory views, and /about/ founder biography are present in branch source.
- Brand-specific routes preserve the other site's /about/ redirect. Editorial views return `noindex` and `no-store`.
- Founder photo has a placeholder; verified portrait asset is not committed.

## Important scope limits
- Passing CI verifies the tested repository snapshot, **not** the actual cPanel/Passenger runtime, production database, static files, hostname routing, SSL, or the currently deployed application.
- Earlier feature branch `seo/mojplaywin-global-products-20261009` contains unrelated factory changes; do not merge it as a substitute.
- This branch must not be merged or deployed without separate owner approval.
- Do not change the VPS factory, payments, public indexability, or other company site.

## Required host preflight (not yet evidenced)
1. Obtain read-only evidence of cPanel Python version, Passenger startup entry point, virtualenv, current deployed commit, configured WSGI app and actual Django settings.
2. Confirm site root and document root, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, domain/alias routing, SSL, and database backend without exposing credentials.
3. Capture a restorable site+database backup and verify its restoration procedure before touching production.
4. Compare the actual deployed tree against this isolated PR; identify template, URL, static, middleware and dependency conflicts.
5. In a separate staging location, install dependencies, run Django `check --deploy`, migrations plan (do not apply blindly), collectstatic, and tests with the actual hosting Python/database.
6. Test all 40 specialty URLs, two directory URLs, /about/, /company/ cross-host behavior, /robots.txt, /sitemap.xml, mobile navigation, 404s, security headers and static assets.
7. Keep pages noindex until content, accuracy, ownership, availability and business approval are verified. Do not enable checkout from editorial drafts.
8. Present evidence, rollback plan and exact file manifest to owner; obtain explicit approval before any production transfer or merge.

## Release gate
**CODE/PR-CI: PASS at ef63ba3. HOST COMPATIBILITY: UNVERIFIED. PRODUCTION DEPLOY: HOLD.**
