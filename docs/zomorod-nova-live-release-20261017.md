# Zomorod Nova — verified live release, 17 October 2026

## User directive
The previous homepage design was rejected. Create and publish an entirely new design, not another layer over its old structure. Preserve every prior item and independent subsite.

## What actually changed live

1. **Original main homepage `/`** replaced atomically with the newly authored `content/zomorod-new-home/index.html` and `content/zomorod-new-home/nova.css`, with a completely new forest-green/cream/gold editorial interface, original corporate logo, existing image assets, a 4-group full mega menu, and 12 page sections.
2. **Previous live homepage preserved byte-for-byte** in the verified private deployment backup and in the publicly readable, search-excluded archive at [site-heritage/home-before-redesign/](https://zomorodmelal.ir/site-heritage/home-before-redesign/). Old articles and URLs were not deleted.
3. **All 17 agriculture pages** now use the separate Nova cream/forest visual system `content/zomorod-new-home/nova-agriculture.css`. The 16 pre-existing page HTML bodies were verified unchanged except the replacement of their old CSS link. The genetics page was deployed and tested first as a canary.
4. All images come from assets already hosted on this domain; broken `/static/site/heroes/laboratory.webp` was replaced with its independently verified working address under `/agriculture/assets/zomorod-olive-v1/`. No external font/template subscriptions or invented products.
5. RTL, mobile responsive layout, progressive CSS, keyboard-accessible navigation, image size hints, reduced-motion preference and semantic links are implemented.

## Actual GitHub Actions evidence

- [New homepage preview run 38966434105](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38966434105): successful read-only original-content backup and original root/subsite health, HTML/CSS HTTP 200.
- [New root live release run 38966812623](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38966812623): success, root 200, theme CSS 200, old original archive 200, old content exact byte match, unchanged root `.htaccess` and three independent subsite hashes.
- [Nova genetics canary run 38967220385](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38967220385): 200 / genetics and CSS; 200 on main site and independent sites; original genetics text preserved.
- [Nova all 17 agriculture release run 38967515685](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/38967515685): all 17 200; untouched main/root and old archive hash; `/mohammad/`, `/ghanadi/`, `/amozeshgah/` all 200.
- GitHub PR #391 source merged only after Django CI and CI succeeded.

## Remaining work that must not be misreported

- The original Django Passenger initialization and active production database linkage were previously broken. **Do not claim they were fixed by this static release.** Company, services, admin, agents, health APIs and dynamic subpages require separate protected repair and live validation.
- Bank Shahr real payments remain disabled pending official merchant/PSP documentation, production credentials, sandbox success and server-side settlement verification.
- Lighthouse/Core Web Vitals 100/100 was not measured; HTML/CSS/public HTTP success is not the same as a full visual-performance audit.
- Independent subsites are intentionally excluded from all Nova changes.

## Source-of-truth and revert

- Current main static HTML: `public_html/index.html`; CSS: `public_html/assets/zm-nova-v1.css`.
- Agriculture current page stylesheet: `public_html/agriculture/assets/zm-nova-agriculture-v1.css`.
- Private original root stored at `~/.backups/zomorod-nova-publish/<release SHA>/original-home.html`.
- Restored old public root: `/site-heritage/home-before-redesign/index.html`.
- Page snapshots: `~/.backups/zomorod-nova-agri-canary/` and `~/.backups/zomorod-nova-agriculture-all/`; each workflow contains automatic rollback code.
- Before any subsequent change, compare hashes and take a separate restorable snapshot. Never touch independent subsites.

