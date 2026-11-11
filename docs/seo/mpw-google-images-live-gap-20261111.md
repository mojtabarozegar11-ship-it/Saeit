# MojPlayWin Google Images: live evidence and release boundary — 2026-11-11

## Verified publicly (read-only)

- The active `https://mojplaywin.com/sitemap.xml` has **152 page URLs** and **zero** `image:image` entries.
- The sitemap lists `/store/`, all three public product pages (`/store/product/72/`, `/store/product/225/`, `/store/product/879/`), and `/taniya/`.
- The live `/store/` and the three live public product pages have **zero HTML `<img>` elements**. They cannot directly introduce product cover images to Google Images through an ordinary `img src`.
- The source `core/templates/mojplaywin/store.html` contains four `<img>` elements, but this is **not** the HTML served at `/store/`.
- The repo's existing `scripts/mpw_dynamic_store_cutover_20261108.py` identifies an owned **`MPW_STATIC_STORE_FALLBACK_V1`** rewrite mapping live `/store/` to `store/index.html`. This explains the source/live discrepancy; it is not a license to run the cutover script.
- The live `/taniya/` page uses an embedded `data:image/jpeg;base64,...` HTML image, not an independently fetchable public image URL.
- Two existing cover assets open successfully and decode as **1122 x 1402 WebP** files:
  - `https://mojplaywin.com/static/site/mojplaywin-products/chess-improvement.webp?v=20261026`
  - `https://mojplaywin.com/static/site/mojplaywin-products/taniya-baker-worms.webp?v=20261026`
- The live editorial knowledge collection has ten distinct public image elements with descriptive `alt` attributes.

## Required production fix, not yet authorized or deployed

1. Identify the **active** server-side renderer for every URL. For `/store/`, use the owned static fallback as the current source of truth until a separate, owner-approved cutover has successfully been verified.
2. Publish accessible public cover URLs within the actual rendered `<img src>` for relevant product pages and `/store/`. The two named WebP assets already exist. The third product cover must be inventoried and validated; do not invent an asset URL. For `/taniya/`, migrate the data URI to a verified public image URL while preserving layout/visual content.
3. Make every intentionally indexable image discoverable from a relevant indexable canonical page with meaningful text and `alt`. Keep payment receipts, private PDF/ZIP downloads, signed URLs, and account files outside the public image sitemap.
4. After a full crawl and HTTP verification, publish a **separate additive image sitemap**. Leave the existing 152-page sitemap untouched. Only then consider Search Console submission/monitoring; sitemap membership does not prove Google indexing.

## Draft-only tooling

`scripts/mpw_google_images_audit.py` crawls sitemap-listed public pages in **read-only mode** and can write a **new** image sitemap when image URLs pass HTTP HEAD checks. Its report flags pages without `<img>` tags, pages without public `<img src>` URLs, embedded Base64 images, lazy image placeholders, and metadata-only image references. It does not touch live files or request Google indexing.

**Release status:** Live image SEO repair **not deployed**. Google Images indexed count **unknown** without Search Console evidence. No emails, tickets, payments, production rewrites, or merges are part of this evidence report.
