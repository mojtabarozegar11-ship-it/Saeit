# MojPlayWin SEO release safety: 152-page baseline and two known book covers

Date: 2026-11-12. **Draft artifacts, not deployed or submitted.**

## Provenance and safeguards

- Reconstructed the **152 same-origin public page URLs** from two independent sections of the prior 2026-11-11 live audit: 94 distinct pages with HTTP-validated image URLs in `mpw-image-inventory-20261111.json`, plus the 58 pages in `mpw-image-verified-20261111.json:pages_without_verified_images`. The sets are disjoint. This is a **derived historical baseline**, not a fresh read of the live `/sitemap.xml`.
- Created `docs/seo/evidence/mpw-public-152-page-reconstructed-baseline-20261112.xml`. It captures all the previously seen page URLs as a read-only input to the existing `scripts/seo_sitemap_parity_guard.py`. Do **not** publish this baseline XML as the current sitemap; it has no `lastmod` and is not a dynamic publisher.
- The draft Django sitemap implementation still returns **only `/store/`** on the MojPlayWin host. A parity comparison against this historical 152-page baseline yields **HOLD: 151 removed pages**, including all three known product pages. This is a concrete pre-release hazard. Never merge/deploy the entire PR without resolving runtime routing and parity.
- Created additive `docs/seo/release-candidates/mpw-image-sitemap-20261112-book-covers.xml`. The original image sitemap's **94 pages / 396 page-image references / 282 unique HTTP-verified image URLs** are preserved byte-for-byte as an unchanged prefix; **two product-page mappings** are appended:
  - `/store/product/72/` → first-party chess-improvement WebP cover
  - `/store/product/225/` → first-party Taniya book WebP cover
- Candidate totals: **96 image-bearing landing pages, 398 page-image mappings, 284 distinct image URL candidates**. These two additional image URLs were found fetchable in the previous live audit but **were not re-fetched today**, and they have not passed a fresh full-file decode in this cycle.
- `/store/product/879/` intentionally receives **no invented cover URL**; product `Atelier Interior` was identified as preview-only in the catalog. Do not misrepresent its sellability.
- Google allows an **independent image sitemap**, including images not otherwise readily discovered. However, an image sitemap is a *discovery hint*, not a substitute for appropriate image landing-page HTML or proof that Google indexed the image. The five commercial/editorial pages still fail the live release gate; this candidate is **not** publication authorization.

## Release checklist

1. Read/confirm actual cPanel PHP/static/Passenger serving provenance and owner-approved, visual-preserving page changes.
2. Re-fetch the live sitemap and save an immutable before-release XML snapshot; use the existing parity guard to preserve every currently listed public URL and all three product pages. **Historical reconstructed baseline alone is insufficient to approve deployment.**
3. Verify the two cover file responses and actual image decoding, and inspect public product HTML and its self-canonical URL.
4. Independently verify the additive image sitemap, deploy only with separate owner approval, keep the original root sitemap intact, and verify both resulting live URLs.
5. Submit/monitor in owner-authorized free search console tools if available; do not claim rankings, traffic, or indexing without measurements.

## Checks

`tests/test_mpw_sitemap_release_candidates.py` verifies baseline derivation, 152-to-1 rejection, exact preservation of original image mapping, both added cover associations, origin/private-path safety, and exclusion of the unverified third cover.

**No production deployments, template/CSS changes, tickets, emails, paid services, or Search Console requests were performed.**
