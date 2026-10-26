# One-phase Social and Professional Network Onboarding — Owner Guide

## Current verified scope

The Mojtaba personal Django social command panel is installed independently. Its database and code are separated from the two commercial sites and factory. Until explicitly enabled, all outbound publishing remains OFF. Platform authorization is necessarily individual: there is no legitimate universal API key for all providers.

## Prepare one manifest (NO TOKENS OR PASSWORDS)

Create a UTF-8 JSON object of the following shape, replacing placeholder values only with REAL account details. Do not register these fictitious examples as accounts:

```json
{
  "schema_version": 1,
  "owner_confirmed": true,
  "accounts": [
    {
      "brand": "personal",
      "platform": "telegram",
      "destination": "@YOUR_REAL_CHANNEL",
      "public_url": "https://t.me/YOUR_REAL_CHANNEL"
    },
    {
      "brand": "zomorod",
      "platform": "linkedin",
      "destination": "urn:li:organization:YOUR_REAL_ORGANIZATION_ID",
      "public_url": "https://www.linkedin.com/company/YOUR_REAL_COMPANY/"
    },
    {
      "brand": "mojplaywin",
      "platform": "youtube",
      "destination": "YOUR_REAL_CHANNEL_ID",
      "public_url": "https://www.youtube.com/@YOUR_REAL_HANDLE"
    }
  ]
}
```

**Important:** These placeholders are only a structural illustration; the sample is not executable until actual accounts and exact destination IDs are substituted. Never include passwords, access tokens, API secrets, refresh tokens, 2FA codes, or cookies in manifest, chat, website forms, source control or email.

Up to 120 account records can be validated and registered together across `personal`, `zomorod`, and `mojplaywin`. Every row is strictly validated against recognized platforms, known HTTPS hosts, duplicate identities and restricted profiles. The handle `dr.mojtaba.rozegar` is excluded. Unsupported API providers are registered only as manual presence listings, not publishers.

### Step A — token-free registry in one batch

Use staff-only panel: https://mojplaywin.com/mojtaba.roozegar/social-command/

1. Log in as the authorized Django superuser. Access is denied to visitors.
2. Paste your manifest into **Batch validation** and select preview; check new/existing/conflicting rows.
3. Select batch register using the same owner-confirmed manifest. The entire import is atomic. All imported records start unverified, with no token and no publication.
4. Admin attestation of account ownership requires separate proof, and does NOT mean the provider has approved an OAuth scope.
5. Future API credentials are stored individually in the private server secret environment, never in source control.

### Step B — provider consent / app approvals later

Perform per-provider OAuth/app approval using each official provider interface. Each account receives a separate per-record environment key name of the form `MPW_SOCIAL_<BRAND>_<PLATFORM>_<ACCOUNT_ID>_TOKEN`. Set secrets only on your private trusted host, with appropriate restricted file/secret store permissions.

Providers may also require dedicated callback redirect URIs, app approval, creator consent, paid plans, verified business pages, image/video ownership, proof of opt-in and/or account review. There is no way to pre-authorize all providers through a universal key. For manual-profile platforms, maintain verified public profile links instead of unauthorized automation.

### Step C — safe publication verification

- Before any production campaign, independently verify account identity, API token scope, provider permission and original source/content rights.
- Keep `MPW_SOCIAL_OUTBOUND_ENABLED=0` until tests prove actual provider connectivity and a publication receipt.
- The platform catalog's availability denotes a local adapter/endpoint, **not** live provider authorization.
- A submitted TikTok upload or WhatsApp message is NOT confirmed published/delivered without a follow-up provider status callback.
- News, scientific achievements and marketing claims require fact-checking and approval before any distribution.
- No promotional actions on `dr.mojtaba.rozegar`.

## Safe repeat upgrades

With each new vetted release, the isolated installer checks the previously published exact SHA256 code fingerprints, stores a new private rollback copy, and swaps only the personal `social_hub` package. It preserves the unchanged Django URLconf and private account/draft SQLite database. If files differ from verified backups, it aborts without touching the live site. This is tested using disposable Django roots.

## Operational reality

The dashboard currently supports planning, private account registries, drafts, approval, and audit receipts. It does **not** constitute proof of live connections, cross-platform comment/message readback, paid ad management or marketplace fulfillment. Those features require separate provider APIs/permissions and validated implementations.
