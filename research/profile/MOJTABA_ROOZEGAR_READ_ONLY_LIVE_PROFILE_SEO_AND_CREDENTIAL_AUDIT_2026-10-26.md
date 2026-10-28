# Mojtaba Roozegar — read-only live-site and scholarly identity audit

**Observed:** 26 October 2026, using independent read-only public-page fetches with current cache preference. **Site:** https://mojplaywin.com/mojtaba.roozegar/ . **No deployment, profile edit, login, social-account access, or GSC indexing claim.**

## Directly observed technical facts

| Public route | Observed page title | Canonical | Robots directive |
|---|---|---|---|
| [Home](https://mojplaywin.com/mojtaba.roozegar/) | Mojtaba Roozegar (مجتبی روزگار) | Official Website | matches exact route | `index,follow,max-image-preview:large` |
| [About](https://mojplaywin.com/mojtaba.roozegar/about/) | About Mojtaba Roozegar | Research, Leadership & Technology | matches exact route | same |
| [Work](https://mojplaywin.com/mojtaba.roozegar/works-activities/) | Work & Research Activities | Mojtaba Roozegar | matches exact route | same |
| [Resume](https://mojplaywin.com/mojtaba.roozegar/resume/) | Professional Resume | Mojtaba Roozegar — Research & Enterprise | matches exact route | same |
| [Blog](https://mojplaywin.com/mojtaba.roozegar/blog/) | Research Journal & Intelligent Web Engineering | Mojtaba Roozegar | matches exact route | same |
| [Contact](https://mojplaywin.com/mojtaba.roozegar/contact/) | Enterprise Website Collaboration Enquiries | Mojtaba Roozegar | matches exact route | same |

- The home page returned English-language semantic content, a viewport meta tag, matching canonical, OG title/description/image, and a main heading. This is **evidence of HTML metadata presence**, not a Core Web Vitals, schema-validation, security, or ranking result.
- [robots.txt](https://mojplaywin.com/robots.txt) explicitly allows general crawling and disallows `/admin/` and `/api/`; it links both main and personal [sitemap](https://mojplaywin.com/mojtaba.roozegar/sitemap.xml). The personal sitemap currently describes **104 URLs** and includes the homepage, resume, works, blog and contact routes. Listing in a sitemap is **not** evidence of Google indexing.
- All six listed public HTML routes and the sitemap were retrieved successfully in this read-only check. This does not certify all links, images, JS, mobile UX or forms; no live checkout or contact submission was performed.
- The profile resume currently reports **no independently verified journal publication** and **no verified manuscript receipt**. This distinction is correct. However, its **research in preparation** still shows an obsolete MR scoping-review protocol description rather than the current MR V5 irrigation evidence-chain perspective; AE and ZM current statuses are not visibly listed in the inspected resume extract.
- A staged, evidence-gated replacement JSON at `content/mojtaba_scholarly_cv_20261024.json` now tracks MR, AE and ZM separately, with truthful draft/major-revision/incomplete-data statuses and **no DOI or Manuscript ID invented**. This staging edit is **not a live publication**.
- The live home/about/resume contain owner-reported academic claims, including a PhD at UPM, and the home page mentions a move to Vancouver. The public fetch confirms these **claims appear on the site**, not that an independent university credential or current geographic residence has been verified. Do not amplify these into third-party-verified assertions without documentary support.
- The extracted public HTML does not establish whether valid `Person` or `ProfilePage` JSON-LD is present. A raw-DOM schema test remains required; do not assert absence or validity based on an extraction that strips scripts.
- The GSC Wizard connector previously returned `subscription_required`. No verified Search Console impressions, clicks, CTR, indexing coverage or position are available from that connection; no subscription purchase is authorized.

## Prioritized evidence-first release gate

1. Verify the owner's academic credential/affiliation and geographic biography **before** adding externally authoritative `sameAs` or alumni assertions. Keep existing self-reported status visible until verified.
2. Reconcile the current public CV's obsolete MR entry with the staged MR V5, AE and ZM entries, but **only** after an owner-specific live-site approval, fresh backup and tested rollback. Do not merge PR #1054 as a shortcut.
3. For future research pages, use `Research in progress`, `Under author scientific review`, `Submitted with verified Manuscript ID`, and `Published with publisher DOI` as **mutually exclusive, evidence-gated states**. No current project has a verified submission receipt.
4. Verify raw JSON-LD schema, responsive layout, form and internal-link behavior and performance with appropriate read-only tests before publishing technical SEO conclusions.
5. Do not access, alter, or publish to Instagram `dr.mojtaba.rozegar` or associated Facebook profiles.

**Decision:** read-only live metadata and sitemap checks **PASS for the observed routes**; public CV research status **NEEDS UPDATE**; Google indexing, full SEO quality, credentials and structured-data validity **NOT VERIFIED**. **No live change made.**
