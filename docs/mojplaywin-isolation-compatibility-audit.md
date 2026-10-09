# MojPlayWin 40-page isolation audit — 2026-10-09

## Verified status

- Full feature branch: `seo/mojplaywin-global-products-20261009`; commit `67f6f8e3d7c88b6d9cf0e193ea439d58dda78972` passed all four GitHub Actions workflows.
- Full branch cannot safely merge to `main`: GitHub comparison showed **405 ahead, 8 behind, 127 changed files**, including unrelated factory and infrastructure changes.
- Isolation branch: `seo/mojplaywin-40-isolated-20261009`, created from `main`. Six relevant specialty/source/test/documentation files were copied. This branch is **not runnable yet**, and no CI pass is claimed for it.

## Exact compatibility blockers

The current `main` does not contain:
- `core/brand.py` required by `core/mojplaywin_specialty_views.py`;
- `core/brand_views.py` used by the feature branch's products/services hub integration;
- `core/templates/brands/mojplaywin/base.html` extended by the specialty template;
- `core/brand_seo_views.py` used for brand-specific sitemap logic;
- `core/templates/brands/mojplaywin/page.html` used for directory links.

The `config/urls.py` on `main` is materially different and lacks the two specialty route declarations. The existing `main` home and services endpoints are not equivalent to the feature branch's multi-brand routing.

## Required integration plan (not yet executed)

1. Determine whether MojPlayWin's brand router, settings, templates, and assets can be introduced without changing the behavior of the primary Zomorod Melal domain. Audit middleware, host routing, existing URL ordering, and all brand-specific views.
2. Port the **minimum coherent brand foundation** as reviewed, bounded changes. Do not copy unrelated factory agents, VPS workflows, secrets, migrations, or commerce/payment code.
3. Integrate the 40 specialty URLs and products/services directory into MojPlayWin only. Preserve other domain routes.
4. Port sitemap draft/cross-brand safety checks only when the actual data model and brand SEO foundation exist. Preserve noindex and no-store behavior.
5. Run Django system checks, complete CI, both MojPlayWin SQLite/PostgreSQL suites, host isolation, security, and visual/mobile browser checks against the exact isolation commit.
6. Create a **draft**, minimal-file PR against `main` only when coherent and tests pass. Do not merge or deploy without owner approval.

## Release decision

**HOLD / NOT READY.** The 40 specialty pages are implemented and CI-verified in the full feature branch, but this isolated branch has unresolved integration dependencies. No production deployment, payment enablement, or factory VPS changes are authorized.
