# Expansion blueprint — 30 websites + 30 blogs + specialist social accounts

**Status:** capacity plan only. No domains, blogs, accounts, or platform integrations have been provisioned.

## Multi-tenant model
- 2 initial tenants: personal and company. Support additional distinct brands.
- Capacity target: 30 websites and 30 blogs, each with unique ID, owner, purpose, language, market, domain, CMS adapter, content strategy, SEO properties, analytics, revenue ledger, and account associations.
- Each platform account has platform, account ID, tenant ID, verified ownership, credential secret reference, permitted actions, and rate-limit policy.
- Keep content, assets, permissions, audiences, analytics, financial data, and audit trails isolated by tenant.

## Channel registry and purpose
- Core discovery: YouTube, Instagram, Facebook, TikTok, Pinterest.
- Professional: LinkedIn, X, Threads.
- Community and retention: Telegram, WhatsApp Business, Discord, Reddit.
- Long form/newsletters: Medium, Substack, LinkedIn articles, Blogger, WordPress.com.
- Specialty only where relevant: GitHub, ResearchGate, Academia.edu, Behance.
- Search visibility/measurement (not social networks): Google Search Console, Bing Webmaster Tools, Google Business Profile where eligible, Google Analytics, sitemaps, structured data.
- Eligibility, regional access, terms, and API support must be verified individually before account creation or automation.

## SEO operating rules
- No link farms, reciprocal-link rings, doorway sites, mass duplicate translations, bulk low-value AI pages, purchased ranking links, or automated spam posting.
- Cross-link only when editorially relevant and genuinely useful. Use canonical and hreflang when applicable, and rel=sponsored/nofollow for paid or untrusted links.
- Maintain independent value proposition and editorial ownership for each site/blog.
- Publishing gate: originality, sources, rights, accessibility, schema validation, indexability, legal review when needed, and human approval for first external publishing.
- Social platforms are for audience discovery/referral; no guaranteed direct ranking benefit.

## Services to build in phases
1. Asset registry and provisioning queue (no automatic signups).
2. Editorial calendar, evidence and deduplication.
3. Multilingual localization and human-readable QA.
4. CMS adapters with idempotent publishing, rollback, and approval.
5. Official platform integrations, quotas and retry queues.
6. Analytics (GSC, Bing, social metrics), attribution, and conversion events.
7. Monetization: direct sales, subscriptions, leads, legitimate affiliate programs, sponsorships, ads where eligible.
8. Budget/cost guardrails, consent, security, privacy, backup and incident response.

## Scale strategy
Pilot with 2 brands and a few high-value properties; expand to 60 only after validated audience demand, quality, operational reliability and positive unit economics. Never auto-create accounts in violation of platform rules.

## Security
No passwords, dates of birth, OTPs, tokens, or payment credentials in Git. Keep production, main, existing factory branch, and PR #32 untouched.
