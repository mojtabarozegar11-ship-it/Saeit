# Zomorod Melal — verified modern AgriTech design system, October 2026

## Implementation and source of truth

This is an additive redesign, **not** a template replacement. The restored main website, existing URLs, logos, articles and images are immutable. Independent `/mohammad/`, `/ghanadi/` and `/amozeshgah/` are excluded. The VPS factory is unrelated.

### Live agriculture section (17 URLs)

- Modernization source: `content/zomorod-design/agritech-luxe-v3.css`.
- Reusable 17-category accessible HTML `details/summary` mega menu: `content/zomorod-design/agritech-mega-menu.html`.
- Deployment: [first canary run 38963659949](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38963659949), [all 17 agriculture pages run 38964031301](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38964031301). Both passed; protected root and independent subsite checks returned HTTP 200 with unchanged hashes.
- All HTML source content was preserved byte-for-byte **after removing just the inserted CSS link and mega menu**. The first page also has a non-content-changing LCP image priority/dimension hint.
- A dedicated copy of each original is retained under `~/.backups/zomorod-luxe-ui-canary/<commit>/` and `~/.backups/zomorod-luxe-all-guides/<commit>/`. Rollback is automatic on failed checks.
- Original domain homepage `/` was **not** redesigned. Only `/agriculture/` and its 16 existing children use the new stylesheet.

### Corporate Django redesign (staged, not deployed)

- [Draft PR #387](https://github.com/mojtabarozegar11-ship-it/Saeit/pull/387) updates the corporate services page with ten unique images, responsive sections, accessible navigation and color tokens.
- The extra CSS is scoped to `body.zomorod-olive-site.services-page`; it must never alter MojPlayWin pages or independent sites.
- The scoped stylesheet restores a missing `site/emerald-system.css` that previously caused staticfiles-manifest rendering errors in the isolated Django test.
- Do not deploy until Passenger, production database selection and compiled static asset manifest are confirmed healthy.

## Research and specific adopted techniques

| Technique | Applied safeguard | Documentation |
|---|---|---|
| Container queries and responsive cards | CSS `@container`; plain mobile-first grid as fallback | https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/At-rules/@container |
| Bento editorial architecture | Uneven featured panels and clear image-led sections; no fake statistics | https://www.behance.net/gallery/248859963/Website-design-for-an-agritech-company-UniferX |
| Cohesive olive/gold tones | CSS variables and `color-mix()` only inside support guard | https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Values/color_value/color-mix |
| Refined Persian headings | `clamp()` sizes, `text-wrap:balance`, with safe fallback | https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/text-wrap |
| Better LCP resource discovery | Priority hint on actual first hero image, width and height defined | https://web.dev/articles/fetch-priority |
| Accessible navigation and motion | Native `details`, 44px targets, focus outlines, reduced-motion CSS | https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/ |
| Gentle behavior instead of unnecessary effects | No third-party JS, web fonts, trackers, or heavy animation dependencies | https://web.dev/articles/prefers-reduced-motion |

These sources document techniques; external design showcases are visual inspiration only. No external template, images, proprietary assets or code was copied.

## Release quality rules

1. No removed original content, broken prior URL, or changed root homepage / independent subsite hashes.
2. Public content and the stylesheet must return 200; CSS should be cached on the same domain.
3. Verify mobile widths, keyboard focus, native menu toggle, image accessibility, Persian RTL and `prefers-reduced-motion`.
4. Actual Lighthouse/Core Web Vitals numerical results are **not measured** yet; never claim 100/100 based on a CI pass.
5. After Passenger and database recovery, extend the same design system to company, about, services, contact, admin and additional pages through staged review and rollback.
