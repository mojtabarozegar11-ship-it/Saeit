# Mojtaba Roozegar Omnichannel Control Center — implementation and activation contract

Date: 2026-10-26. Owner: independent personal Django app on MojPlayWin hosting.

## Release policy

- Central public hub is already a separate existing release. This package adds a *staff-only* social command panel, not a public API.
- Scope of modification: `/home/zomorod2/mojtaba_personal/mojtaba_roozegar_personal_v17` and a dedicated private backup/ledger directory only. It must not touch the two business sites, existing business apps, factory, storefront, customer orders, shared MySQL or VPS production workloads.
- Social publishing is **OFF by default**, and there are no connection tokens, creator profiles or scheduled tasks shipped with this repository.
- Publishing through, linking for marketing, or promoting `dr.mojtaba.rozegar` is expressly prohibited.
- Only owned accounts and consented communications can be onboarded; platform TOS, anti-spam, opt-in and advertising spend constraints remain binding.

## Architecture and delivered modules

| Component | File | Purpose |
| --- | --- | --- |
| Platform registry | `social_hub/catalog.py` | >40 accurately classified networks/research/business/sales platforms |
| Official API writers | `social_hub/adapters.py` | Telegram, Discord, Bluesky, Mastodon, X, LinkedIn, Facebook Pages, Threads, Reddit, Google Business Profile, Instagram, Pinterest, TikTok, WhatsApp Business, Zenodo draft, GitHub Releases draft |
| Video uploads | `social_hub/youtube.py` | YouTube resumable official video upload from private file root |
| HTTP execution | `social_hub/transport.py` | Bounded responses, no arbitrary redirects or bearer-token leakage |
| Ledger | `social_hub/store.py` | Private SQLite accounts, drafts, approval records, state transition, immutable remote IDs, audit events |
| Private worker | `social_hub/service.py` | Single-item and bounded due dispatcher; explicit opt-in and no automatic ambiguous retries |
| Django command panel | `social_hub/portal.py` | Persian responsive staff-only account management, composer, approvals, receipts, safe status JSON |
| Private CLI | `scripts/mojtaba_social_hub_cli_20261026.py` | Account registration, verification, drafting, manual approval, dispatch-one/due, readiness |
| Transactional installer | `scripts/mojtaba_social_hub_install_personal_20261026.py` | Isolated personal app route, backups, hash checks, auto-rollback |

### Implemented outbound integrations: 17 official API workflows

1. Telegram Bot API text.
2. Discord Bot API text (mass mentions disabled).
3. Bluesky AT Protocol text.
4. Mastodon write:statuses (private allowed server list).
5. X API text.
6. LinkedIn REST Posts API text.
7. Facebook Page Feed API text.
8. Threads text with container and publish.
9. Reddit OAuth submission.
10. Google Business Profile Local Posts.
11. Instagram Professional image container/publish.
12. Pinterest image Pin.
13. TikTok creator-info plus explicitly consented video Direct Post initiation — *submitted, not published*, until status verification.
14. WhatsApp Business approved template for an individually opted-in recipient — *submitted, not delivered* until webhook receipt.
15. Zenodo metadata deposition *draft only* — no automated DOI release.
16. GitHub release *draft only* — no automated public release.
17. YouTube authorized resumable video upload from server-owned private media root.

Each of these needs separate provider access approval, compatible scopes, correct identities, official API subscriptions if required, per-brand token and end-to-end live verification. Mock success is not live success.

### Catalogued, but not generically publishable

Google Scholar, ResearchGate, Academia.edu, SSRN, Medium, Substack, Quora, DEV, ORCID writes, Hugging Face, Alibaba, Global Sources, Made-in-China, Europages, Kompass, Crunchbase, Trustpilot, Steam, itch.io, Google Play, Apple App Store, Amazon KDP, Gumroad, Payhip, Udemy, Patreon, Ko-fi, Product Hunt and Snapchat are not falsely declared direct connected networks. For several, separate marketplace/product-release processes or manual verification are the only permitted routes.

## Three independent brand environments

- `personal`: academic biography, research, writing, personal public professional profile.
- `zomorod`: Zomorod Melal scientific and agro-industrial B2B material.
- `mojplaywin`: video games, digital publications, educational content, products.

Token variables are derived per record, e.g. `MPW_SOCIAL_PERSONAL_TELEGRAM_<32_CHARACTER_HEX_ACCOUNT_ID>_TOKEN`; tokens are never embedded in source or displayed in UI. Create a separate credential per account with least-privilege scopes.

### One later onboarding phase — not one universal login

1. Create and verify the actual account on each chosen provider. For every account, record brand, network, immutable destination ID and its authentic public URL.
2. Obtain each provider's approved developer app, individual OAuth consent / API token and required subscription. A single common authorization cannot bypass provider OAuth consent.
3. Use the staff console to register planned account identities and attach independent owner-verification evidence; accounts remain unverified until approved.
4. Set matching per-account token aliases in the *private* hosting secret environment; never post secrets to GitHub, chat, templates or public profile fields.
5. Configure `MPW_SOCIAL_MEDIA_ROOT` for YouTube videos, `MPW_SOCIAL_ALLOWED_MASTODON_ORIGINS` for approved Mastodon HTTPS server origins, and private DB path if needed.
6. Enable `MPW_SOCIAL_OUTBOUND_ENABLED=1` **only after** end-to-end dry-run, ownership, scopes and explicit content approval gates are verified.
7. Start with one authorized test publication per provider and capture the real remote publication ID. TikTok/WhatsApp submission requires follow-up finality verification.
8. Schedule the private bounded worker separately: the deployment ships NO pre-enabled cron. External advertising expenditure needs a separate payment and explicit per-campaign approval.

## Staff-only web routes

- Login-protected dashboard after installation: `https://mojplaywin.com/mojtaba.roozegar/social-command/` (validate routing on the deployed personal app).
- Login-protected machine-readable status: `.../social-command/status/`.
- Users must be Django staff. Superuser or `social_admin` may inspect all brands; `social_personal`, `social_zomorod`, `social_mojplaywin` can inspect and draft only within assigned brands; `social_approver_<brand>` may approve within that brand.
- No POST from web invokes external network sends. Only the private worker can publish.

## Durable states and proof

`draft → approved → dispatching → published | submitted | draft_created | needs_review`, with cancellations only before dispatch. The original approval, SHA256-bound payload, event log and remote receipt remain in private storage. A timeout after dispatch is marked `needs_review` and is NOT automatically retried.

## Test and recovery

- Offline contract and integration simulation: `python -m unittest discover -s tests -p 'test_mojtaba_social_hub_20261026.py' -v`.
- Installer isolation and rollback fixture: `python -m unittest discover -s tests -p 'test_mojtaba_social_hub_installer_20261026.py' -v`.
- Dedicated GitHub Actions workflows execute both regression groups before any authorized guarded deployment.
- Installer's `check` refuses unknown URLs, existing route conflicts or unexpected target structure; `install` protects the original URLconf and isolates the package; `rollback` only restores checksum-matching version and **preserves** any private account database.

## Unfinished until credentials and evidence exist

Individual OAuth login/refresh flows for all providers, actual token/scopes and verified destination identity, provider app review, real network post receipts, analytics and inbound comment/message support for every platform, plus paid advertising campaign management, cannot truthfully be claimed complete from token-free code. These require a later controlled integration step; some platforms have no general public write API at all.

**Quality terminology:** green offline tests prove implementation contracts, not that external providers have approved or accepted real content. The dashboard must display that distinction.
