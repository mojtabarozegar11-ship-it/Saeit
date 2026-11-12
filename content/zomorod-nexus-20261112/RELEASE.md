# Zomorod Melal NEXUS — homepage production release
Date: 12 November 2026
Domain: https://zomorodmelal.ir/
Scope: root homepage `/index.html` and ONE new, homepage-only stylesheet `/assets/zm-nexus-v1.css`.

## Intent
Replace the current overloaded landing page with a coherent Persian RTL dark-emerald, champagne-gold, high-end scientific homepage while retaining the existing navigation destinations and internal site files. Sections: hero, five business/scientific domains, service decision flow, real site entry points, knowledge and tools, research, collaboration, full footer. No Vancouver references, manufactured project counts, fake ISO seals, unsupported earnings or unverified live metrics.

## Safety / anti-regression
- Source is isolated under `content/zomorod-nexus-20261112/`; no common Django templates, apps, checkout, payments, credentials, database, `.htaccess`, site-wide CSS, or independent subsites are changed.
- Guard checks cPanel username, exact docroot, original root size and markers, local images, file types, collisions and at least five protected files. It refuses if the target has changed.
- Complete original homepage is saved byte-for-byte in a private verified backup, and in `/site-heritage/home-before-nexus-20261112/`. The new footer links to this archive so previous hundreds of category links remain accessible.
- Checksums of existing internal files are recorded before and after; any mismatch aborts.
- Publication uses atomic rename for exactly the homepage and new CSS; automatic rollback on verification failure; rollback refuses to overwrite concurrent user edits.
- No SSH fingerprint bypass. A pinned GitHub → VPS → cPanel relay is required; if credentials, ports, or verified host keys fail, no deployment occurs.
- Production release is attempted only by workflow on approved main branch; pull-request validation cannot modify the live server. User must not interpret PR/CI success as evidence of production publication.

## Validation
Local standalone structural and CSS parser checks: passed.
Local browser (headless Chromium) widths 360, 390, 768, 1024, 1440: no horizontal overflow; 7 page sections; no JS errors. Network-hosted image bytes could not be fetched in local sandbox: image rendering and LCP require live browser verification.
Public route destinations were read-only checked for `/research/projects/`, `/services/`, `/store/`, `/contact/`, `/topics/`, `/games/`, `/apps/`, `/auctions/`, `/newsletter/`, `/agriculture/genetics/`.

## Release
Validated via `.github/workflows/zomorod-nexus-20261112.yml` on PR. After merge to main, the release job checks the live original state and protected destinations, stages only these files privately, performs guarded atomic replacement, verifies public HTML/CSS and responsive browser views, and rolls back if post-install verification fails.

## Production claims
Do not report the new homepage as live without a verified successful publish job AND a subsequent read of the live public page.