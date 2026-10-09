# Zomorod Melal — SEO execution specification (2026-10-09)

## Business goal
Increase qualified organic discovery for **کشاورزی** (P0, head term) and **شرکت خدمات کشاورزی** (P1, high-intent commercial term), followed by related non-brand terms. Ranking is not guaranteed; baseline impressions, clicks, position and conversions must be measured in Search Console.

## Keyword-to-page mapping
- P0: کشاورزی → /agriculture/ as the comprehensive agriculture pillar page, with original helpful content, credible sources, and links to all agricultural subtopics. Avoid thin keyword-stuffed content.\n- P1: شرکت خدمات کشاورزی → primary agricultural services landing page, with clear service offerings and contact/lead CTA.
- P1: کشت و صنعت → agricultural industry hub.
- P1: شرکت کشاورزی → company/agriculture overview; avoid competing duplicate pages.
- P1: شرکت تحقیقات کشاورزی → agricultural research page with real projects and methods.
- P1: شرکت اصلاح نژاد → breeding/genetics page; distinguish plant vs animal work and verify actual scope.
- P1: شرکت فناوری کشاورزی → agricultural technology page with genuine implemented capabilities.
- Support terms: خدمات کشاورزی، مشاوره کشاورزی، فناوری نوین کشاورزی، تحقیقات کشاورزی، اصلاح نژاد گیاهان، اصلاح نژاد دام.

## First diagnostic gate — collect evidence before edits
1. Check public homepage HTTP status, canonical domain, redirects, TLS, robots.txt and sitemap.xml from a network with access.
2. Inspect Google Search Console: indexing, pages, query impressions/clicks/CTR/position, coverage, manual actions, Core Web Vitals.
3. Crawl existing routes and extract titles, H1, meta descriptions, canonical, robots directives, internal links, schema, duplicate/thin pages.
4. Compare against search intent and real competitor landing pages; avoid unverified claims about rankings.

## Django implementation requirements
- Preserve all existing content and routes; make additive changes and avoid duplicate URLs.
- Choose one canonical URL per page; return 200 for indexable pages, redirect alternate slash/domain versions; use absolute canonical URLs.
- Generate accurate unique Persian title, meta description and one H1 per page; do not keyword-stuff.
- Add valid Organization schema with actual business details, WebSite schema, BreadcrumbList on relevant pages; Service schema only for genuine services; do not claim accredited or knowledge-based status without proof.
- Expose UTF-8 XML sitemap with only canonical, indexable, 200-status URLs; robots.txt should allow public pages and reference the sitemap while excluding admin/private endpoints.
- Ensure content is server-rendered, accessible in Persian RTL, mobile friendly, with useful internal links from homepage/services/company/research.
- Add credible author/reviewer, last updated date, real case studies and references; avoid invented credentials, outcomes and reviews.
- Optimize LCP/INP/CLS, compression, caching, images, semantic markup and accessibility.
- Make publication frequency quality-driven; no mass-generated near-duplicate doorway pages.

## Acceptance checks
- Unit/integration tests for 200 response, canonical, unique metadata, robots, sitemap, schema and private-page exclusion.
- Django system checks and existing CI green on feature branch.
- Staging crawl proves pages are indexable and linked; production untouched pending separate authorized deployment.
- Post-release: submit sitemap in Search Console and measure P0/P1 impressions, clicks and leads at 7/28/90 days.

## Ownership and safety
- Do not modify main or production or merge PR #32 as part of this specification.
- Confirm actual business service scope before publishing claims.
- No claim of completed SEO deployment or Google indexing without direct evidence.
