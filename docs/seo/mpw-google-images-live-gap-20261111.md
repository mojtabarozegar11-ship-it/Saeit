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
- Live `https://mojplaywin.com/robots.txt` returns **HTTP 404** even though the Draft source (`core/seo_views.py` and `config/urls.py`) implements a host-aware robots response. A robots 404 does not itself ban crawling, but it prevents advertising the sitemap at that location. Do not overwrite the active host configuration based only on Draft source.

## Completed full public sitemap crawl

Read-only scan of **all 152 / 152** listed pages completed successfully (0 skipped pages):

| Measure | Observed |
| --- | ---: |
| HTML `<img>` tags | 404 |
| Image references, including metadata/srcset | 431 |
| Distinct eligible same-origin image URLs (not yet HTTP-verified) | 282 |
| Page-to-image associations eligible for a draft sitemap (not yet HTTP-verified) | 396 |
| Pages containing public image URL candidates | 94 / 152 (61.8%) |
| Pages without public image URL candidates | 58 / 152 (38.2%) |
| Pages with no HTML `<img>` tags | 57 / 152 (37.5%) |
| `<img>` tags with empty `alt` | 32 / 404 (7.9%; may include decorative images) |
| `<img>` tags missing `alt` altogether | 0 |
| Pages using embedded data image URLs | 1 (`/taniya/`) |

The initial machine-readable report is `docs/seo/evidence/mpw-image-coverage-20261111.json`. Its counts represent **crawl discovery, not Google indexing**. The full HTTP validation was completed separately afterward, as recorded below; Google Search Console indexing evidence remains unavailable.

## Subsequent full HTTP image verification — 2026-11-11

A second bounded public crawl checked all 152 sitemap URLs with three concurrent
read-only requests, then verified the HTTP response of every unique discovered
image URL. Images were accepted only with status 200, a matching final URL,
an `image/*` MIME type, and no `noimageindex` restriction. HTTP 405/501 on
HEAD may be verified by an actual bounded GET request instead.

| Verification measure | Verified outcome |
| --- | ---: |
| Public URLs checked | **282 / 282** |
| Valid public image responses | **282 / 282 (100%)** |
| Failed image checks | **0** |
| Pages with at least one verified image | **94** |
| Verified page-to-image sitemap associations | **396** |
| Pages without any verified public image | **58** |

Release candidates (all versioned source artifacts, **not published**):

- `docs/seo/release-candidates/mpw-image-sitemap-20261111.xml` — separate XML
  image sitemap. Parsed and checked: 94 unique page URLs, 396 image associations,
  282 unique eligible same-origin images, no protected URLs, and at most 1,000
  images per page.
- `docs/seo/evidence/mpw-image-inventory-20261111.json` — page-to-image
  inventory before HTTP filtering.
- `docs/seo/evidence/mpw-image-verified-20261111.json` — detailed HTTP results,
  zero rejected image URLs, and the list of 58 image-less pages.

Important boundaries: this verifies **images referenced by the 152 public
sitemap-listed pages**, not every orphaned file on cPanel storage. The XML is
not yet hosted or submitted to Search Console. Neither inclusion in a sitemap
nor an HTTP 200 response proves Google has indexed an image. Publishing the
candidate requires an explicit owner-approved deployment and post-release
live verification, while keeping the original `/sitemap.xml` unchanged.

## Required production fix, not yet authorized or deployed

1. Identify the **active** server-side renderer for every URL. For `/store/`, use the owned static fallback as the current source of truth until a separate, owner-approved cutover has successfully been verified.
2. Publish accessible public cover URLs within the actual rendered `<img src>` for relevant product pages and `/store/`. The two named WebP assets already exist. The third product cover must be inventoried and validated; do not invent an asset URL. For `/taniya/`, migrate the data URI to a verified public image URL while preserving layout/visual content.
3. Make every intentionally indexable image discoverable from a relevant indexable canonical page with meaningful text and `alt`. Keep payment receipts, private PDF/ZIP downloads, signed URLs, and account files outside the public image sitemap.
4. After a full crawl and HTTP verification, publish a **separate additive image sitemap**. Leave the existing 152-page sitemap untouched. Only then consider Search Console submission/monitoring; sitemap membership does not prove Google indexing.

## Draft-only tooling

`scripts/mpw_google_images_audit.py` crawls sitemap-listed public pages in **read-only mode** and can write a **new** image sitemap when image URLs pass HTTP HEAD checks. Its report flags pages without `<img>` tags, pages without public `<img src>` URLs, embedded Base64 images, lazy image placeholders, and metadata-only image references. It does not touch live files or request Google indexing.

**Release status:** Live image SEO repair **not deployed**. Google Images indexed count **unknown** without Search Console evidence. No emails, tickets, payments, production rewrites, or merges are part of this evidence report.

## Commerce image release gate — subsequent cycle, 2026-11-11

The read-only `scripts/mpw_product_image_live_gate.py` fetched the **actual live**
store landing page, three product pages, and `/taniya/`, and verified both
existing WebP covers by HTTP status, MIME type and image robots header.
It is independent of the inactive Django store template and does not change
site appearance.

| Live URL | Ordinary public `<img src>` | Release issue |
| --- | ---: | --- |
| `/store/` | 0 | Two verified covers absent; **missing canonical** |
| `/store/product/72/` | 0 | Chess cover absent |
| `/store/product/225/` | 0 | Taniya storybook cover absent |
| `/store/product/879/` | 0 | Atelier cover absent; actual public asset URL unknown |
| `/taniya/` | 0 | One embedded Base64 image is not a public image URL |

Outcome: **5/5 pages have a release issue; two of two known cover files
remain fetchable; commercial image release gate = HOLD.** The `/taniya/`
page has one `<img>` element, but its `src` is a data URI rather than a
standalone public URL. The gate requires real ordinary HTML image references,
meaningful alt text, self-canonical landing URLs, a verified public image file,
and no `noimageindex` restriction. It never treats OG metadata or CSS
background images as a substitute for `<img src>`.

Offline validation: **30/30 image-audit and commercial-gate tests passed**.

**Owner design freeze:** the existing visual layout, templates and source/live
route ownership must remain unchanged until a separately approved release.
In particular, do not execute the pre-existing static-store cutover script,
replace `store/index.html`, or update the live product template from an older
workflow to force green image checks. First read and reconcile the active
cPanel files and create a visual-preserving, owner-approved placement for
the real image assets. A source-only Draft PR and green CI do not authorize
deployment or establish Google indexing.
