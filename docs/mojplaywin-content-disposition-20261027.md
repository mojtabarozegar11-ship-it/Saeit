# MojPlayWin main-domain content disposition — 2026-10-27

Scope: `https://mojplaywin.com/`, excluding the separately managed personal and child sites and their data.

## Evidence-based decisions

| Segment | Observed evidence | Disposition |
| --- | --- | --- |
| Main sitemap | 133 of 133 URLs returned HTTP 200 in the public audit; titles and H1s were individually unique. | Retain existing indexable URLs; do not bulk delete or 301 redirect. |
| 12 revenue service/detail pages | Shared template and navigation components, but different offer copy; pairwise body similarity commonly about 0.25–0.35 in 5-gram Jaccard. | Keep separate pages. Consolidate navigation and cross-links, not the distinct paid offers. |
| Three store items | Three independent products (IDs 72, 225, 879). Highest similarity was between two short shared product shells, not proof of duplicate substantive content. | Keep three distinct product URLs and legal ownership checks. |
| Home guide/offer blocks | Homepage footer was nested within main and before a revenue offer. | Correct HTML landmark order; preserve every section, script and footer item. |
| Services and Games guide links | The obsolete `/#mpw-insight-title`, `/#field-library-round2` and `/#field-library-advanced` fragment targets no longer exist on the homepage. | Consolidate references to existing `/mpw-editorial/field-guides/original-ten/` and `/mpw-editorial/field-guides/20261023/index.html`. Services is a static HTML target; Games is a PHP-rendered route requiring its own source audit. |
| Django store layout | `site_base.html` already defines `<main id="main-content">`; `store.html` defined another nested main. | Replace nested inner main with a CSS-equivalent div without editing checkout or customer data. |
| Protected personal and sibling sites | Other properties have independent content and route lifecycles. | Preserve their URLs and all source/data; read-only uptime checks during any MojPlayWin-only release. |

## Limits and independent gates

- Public-page similarity is not a substitute for verified Search Console query-level cannibalization. No mass content merges or deletions without query and intent mapping.
- The GSC Wizard subscription/connection was unavailable in the current audit, so Google Search Console clicks, impressions, query entropy and CrUX field data must **not** be asserted.
- A visible product page, a checkout redirect to login and a code merge do **not** establish a successful transaction. Invoice creation, payment confirmation, email receipt and protected download need real end-to-end evidence.
- The `/store/` path currently has a 307 self-canonical passthrough redirect and the public Games PHP route needs source discovery. Treat these as separate unresolved routing tasks; do not bypass payment or cross-site security protections to change them.
- The previously disabled broad Django/Passenger deployment must remain disabled. Changes are limited to guarded, hash-checked, reversible one-file or explicitly scoped main-site releases.

A page must only be removed/redirected after unique-content ownership, inbound links, search intent, traffic, internal links and canonical destinations have been verified.
