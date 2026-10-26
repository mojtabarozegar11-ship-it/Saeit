# Social Hub API Readiness — Read-only provider verification

**Status:** Code is an optional, explicit-trigger diagnostic; no provider credentials are shipped, no OAuth scopes are granted by the app, and all external publication remains OFF.

## What changed

Every social account has a separate secret variable and ownership-attested profile. The account may now undergo a *read-only* GET diagnostic. The result is written as a sanitized row in the pre-existing private SQLite database, not as a public channel entry, token or full remote response.

Three states must not be conflated:

| Private status | Meaning | Can automatically publish? |
| --- | --- | --- |
| `not_checked` | No read-only provider verification attempted | No |
| `identity_verified` | Provider read endpoint matched the configured identity/channel at the check instant | **No:** publish scopes, app review and a real receipt are still unverified |
| `credential_valid_only` | Credential was recognized, but the precise destination's publishing rights are NOT proven | No |
| `failed` | Authentication, identity matching, or account permissions did not pass the check | No |
| `stale` | Last result older than 24 hours | No |

All network diagnostics are explicit and use **GET only**. No test schedules or sends a message, deposits a DOI, uploads media, initiates paid advertising or posts social content. The check automatically blocks attempts repeated within ten minutes. The connection panel retains a separate `connected: false` and `publishing_scope_verified: false` until a separate authorized real publish and receipt verification is implemented.

## Supported read-only tests (14)

- Telegram Bot API `getMe` + `getChat` + `getChatAdministrators`; the bot must be an administrator allowed to post to its registered channel.
- Discord `users/@me` + permitted channel lookup; reports credential-valid only because this alone does not establish channel sending permissions.
- YouTube `channels.list(mine=true)` binding to immutable channel ID; does not establish video-upload scope or publication.
- Bluesky `com.atproto.server.getSession` DID/handle match; write grant not verified.
- Mastodon `accounts/verify_credentials` username match; the HTTPS instance origin must be in the private administrator allowlist.
- X `users/me` immutable account ID match.
- Facebook Pages `me?fields=id` binding to the page token's ID.
- Instagram Professional `/{id}?fields=id,username` binding to the professional account ID.
- TikTok `user/info` Open ID match.
- WhatsApp Business phone ID readable with a scoped token; opt-in and template delivery permission are separate.
- LinkedIn OIDC member identity; organization posting rights not inferred.
- Reddit OAuth user identity; subreddit posting rights not inferred.
- Pinterest account identity; board pin rights not inferred.
- GitHub authenticated user; per-repo release permission not inferred.

Other network accounts still use profile/registration status, not imaginary read-only API proof.

## One controlled connection phase (after owner authorizations)

1. Register actual owned accounts, IDs and their official URLs in the existing bulk account form. Do not use placeholders.
2. Record owner-provided proof in the staff dashboard. This is an administrative attestation, not proof of provider API authorization.
3. For each provider, complete its own developer-app and OAuth approval, then populate the per-account private environment variable with its least-privilege token. No credentials go into GitHub, site HTML, direct chats, or onboarding JSON.
4. Log in to the staff-only dashboard and choose **Read-only API verification** for each account. Confirm the limited GET check explicitly.
5. The private command line can also run one targeted check: `python scripts/mojtaba_social_hub_cli_20261026.py --db /PRIVATE/social.sqlite test-readonly --account ACCOUNT_ID --confirm`.
6. Inspect the separate identity-verification and publishing-permission states. Resolve failures and API approvals before a real test-channel send. The outbound publishing switch remains disabled.

**Important:** API/provider read-only success never implies a verified right to publish, a valid current OAuth refresh token, paid ad account access, or permission to mass-message third parties. A subsequent live test and per-provider capability gates remain necessary.

## Isolation and security

- `dr.mojtaba.rozegar` is excluded from promoting/publishing or verification.
- No credential string, provider response body, inbox message or roster is written to DB/logs.
- Mastodon instances are exact-allowlisted (`MPW_SOCIAL_ALLOWED_MASTODON_ORIGINS`). Redirects are refused by the existing HTTP transport.
- The UI action is Django-staff/superuser-only, CSRF protected and individually authorized by the operator. A private CLI is available for later owner-controlled batch orchestration.
- Provider result checks are cached for ten minutes and become stale after 24 hours; no default background polling or sends.
- Changes to the independent personal Django package use the existing private snapshot/rollback deploy. Both storefront/company sites and VPS factory remain unchanged.

## Official reference documentation

- Telegram: https://core.telegram.org/bots/api
- Mastodon: https://docs.joinmastodon.org/methods/accounts/
- YouTube: https://developers.google.com/youtube/v3/docs/channels/list
- Bluesky: https://docs.bsky.app/docs/api/com-atproto-server-get-session
- Discord: https://discord.com/developers/docs/resources/user

## Regression

`python -m unittest discover -s tests -p 'test_mojtaba_social_readonly_diagnostics_20261026.py' -v`

CI must pass and a smoke test must confirm both the authenticated dashboard and the public directory before the isolated deployment is called successful.

## Emergency account suspension (no provider-side effects)

An authenticated owner superuser can select an existing verified account and **Suspend account** in the private Django dashboard. It immediately un-verifies the account (so its public official link disappears), deletes its read-only API confirmation, cancels all approved-but-unsent posts, and preserves the original evidence and audit log. Drafts are retained. Any already-inflight remote send remains for manual reconciliation.

Private CLI alternative:

`python scripts/mojtaba_social_hub_cli_20261026.py --db /PRIVATE/social.sqlite suspend-account --account ACCOUNT_ID --confirm`

**This does NOT revoke a token at Telegram, Google, Meta, etc.** The owner must separately revoke or rotate that token at the provider or trusted secret manager; no system can claim successful remote revocation without an official API receipt.

The protected Instagram handle `dr.mojtaba.rozegar` remains excluded from marketing, verification and promotion.
