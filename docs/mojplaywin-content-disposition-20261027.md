# MojPlayWin main-domain content disposition — 2026-10-27

Scope: `https://mojplaywin.com/`, excluding the separately managed personal and child sites and their data.

## Evidence-based decisions

| Segment | Observed evidence | Disposition |
| --- | --- | --- |
| Main sitemap | 133 of 133 URLs returned HTTP 200 in the public audit; titles and H1s were individually unique. | Retain existing indexable URLs; do not bulk delete or 301 redirect. |
| 12 revenue service/detail pages | Shared template and navigation components, but different offer copy; pairwise body similarity commonly about 0.25–0.35 in 5-gram Jaccard. | Keep separate pages. Consolidate navigation and cross-links, not the distinct paid offers. |
| Three store items | Three independent products (IDs 72, 225, 879). Highest similarity was between two short shared product shells, not proof of duplicate substantive content. | Keep three distinct product URLs and legal ownership checks. |
| Home guide/offer blocks | Homepage footer was nested within main and before a revenue offer. | Correct HTML landmark order; preserve every section, script and footer item. |
| Services, Games, Studio and other main-brand guide links | Four obsolete homepage fragments (`mpw-insight-title`, `field-library-round2`, `field-library-business`, `field-library-advanced`) were used repeatedly. `/games/` renders through `core/templates/brands/mojplaywin/page.html` and `/studio/` is a separate static HTML source. | Redirect the **links** (not HTTP page URLs) to two existing guide libraries. Six service-page links, 53 dynamic-template references and the studio-page links were updated. Live postchecks passed; no page was deleted. |
| Django store layout | `site_base.html` already defines `<main id="main-content">`; `store.html` defined another nested main. | Replace nested inner main with a CSS-equivalent div without editing checkout or customer data. |
| Protected personal and sibling sites | Other properties have independent content and route lifecycles. | Preserve their URLs and all source/data; read-only uptime checks during any MojPlayWin-only release. |

## Limits and independent gates

- Public-page similarity is not a substitute for verified Search Console query-level cannibalization. No mass content merges or deletions without query and intent mapping.
- The GSC Wizard subscription/connection was unavailable in the current audit, so Google Search Console clicks, impressions, query entropy and CrUX field data must **not** be asserted.
- A visible product page, a checkout redirect to login and a code merge do **not** establish a successful transaction. Invoice creation, payment confirmation, email receipt and protected download need real end-to-end evidence.
- The `/store/` path still has a 307 passthrough redirect, and authenticated invoice/payment/email/download end-to-end confirmation is outstanding. Treat these as separate commerce/routing tasks; do not bypass payment or cross-site security protections to change them.
- The previously disabled broad Django/Passenger deployment must remain disabled. Changes are limited to guarded, hash-checked, reversible one-file or explicitly scoped main-site releases.

A page must only be removed/redirected after unique-content ownership, inbound links, search intent, traffic, internal links and canonical destinations have been verified.

## Live publication evidence

- Homepage and service links: [GitHub Actions run 40481534301](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40481534301), success.
- Single-main store landmark: [run 40481876505](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40481876505), success.
- Dynamic Games, static Studio and 53 template guide links: [run 40482970364](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/40482970364), success.

The release smoke tests verify live structure, link targets and protected route availability; they do not establish a successful paid transaction or Search Console improvement.
