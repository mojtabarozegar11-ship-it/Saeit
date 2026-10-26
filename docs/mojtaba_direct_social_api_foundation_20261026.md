# Central social API infrastructure — 2026-10-26

This is a NON-DEPLOYED connector foundation, not evidence that any social account has been connected.
The previously published personal website hub (PR #1217) is separate; its verified public social registry is still empty.

## Scope
- Three isolated brands: personal, zomorod, mojplaywin.
- Personal homepage: https://mojplaywin.com/mojtaba.roozegar/
- No changes to live websites, other websites, shops, the factory, VPS, or shared hosting from this PR.
- The Instagram handle dr.mojtaba.rozegar must not be promoted or used for campaigns.
- Never commit tokens or secrets.

## Implemented sender adapters (code and offline tests, not connected accounts)
| Service | Protocol | Status |
| --- | --- | --- |
| Telegram | Official Bot API sendMessage | Implemented locally; no verified destination/token |
| Discord | Official Bot API POST /channels/{id}/messages | Implemented locally; no verified destination/token |

Instagram, Facebook, Threads, YouTube, LinkedIn, TikTok, X, WhatsApp, Pinterest, Reddit, Bluesky, Mastodon, scholarly networks and marketplaces require separate approved integrations. Do not treat them as ready.

## Execution controls
1. Validate brand and platform.
2. Verify account/destination in MPW_SOCIAL_<BRAND>_<PLATFORM>_VERIFIED_TARGETS.
3. Require brand-specific MPW_SOCIAL_<BRAND>_<PLATFORM>_TOKEN in private server environment.
4. Require approved=true and a reference approval_id.
5. Require MPW_SOCIAL_EXECUTION_ENABLED=1 and an explicit CLI --execute flag.
6. Require a persistent private SQLite ledger path via --ledger.
7. Prevent duplicates and automatic resends after ambiguous remote outcomes.

WARNING: the CLI cannot independently establish that approval_id is authentic. The future authenticated Django dashboard must validate approval database records and role permissions before invoking it. Never make this tool a public unauthenticated HTTP endpoint.

## Preview (no network or disk writes)
Create a JSON file with job_id, brand, platform, destination, text, approved, and approval_id fields.
Run: python scripts/mojtaba_direct_social_publisher_20261026.py --job /private/draft.json
Preview reports readiness booleans; never reveals tokens. Real sends are disabled by default.

## Requirements before live integration
- Administrator authentication, CSRF protection, RBAC and brand isolation.
- Profile/destination ownership confirmation.
- Private secret storage and least-privilege permission scopes.
- Enforced approval checks in the server-side database (not just supplied JSON flags).
- Outbound API rate limits, queues, privacy policy, opt-in where required, moderation and logs.
- Private restricted-permission SQLite ledger stored on a durable volume.
- Integration testing in authorized test channels, then real remote receipt verification.
- Per-platform API authorization and compliance review.

## Offline tests
python -m unittest discover -s tests -p 'test_mojtaba_direct_social_publisher_20261026.py' -v
No CI stage sends real messages.
