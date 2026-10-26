# One-phase API credentials: private owner procedure

This release adds an owner-only **batch credential vault** to the standalone Mojtaba Roozegar social command center. It does not create provider accounts, obtain OAuth permissions, grant publishing scopes, send posts or handle paid advertising. The prohibited Instagram account remains excluded.

## Before entering credentials

1. Use the personal staff panel at https://mojplaywin.com/mojtaba.roozegar/social-command/ and register real owner-held profiles for the 3 brands, including their exact account IDs and public URLs.
2. Attest ownership of each account independently. Profiles remain unverified until explicitly attested. No secrets may be pasted into the website.
3. Obtain each token/app approval via the official provider OAuth, bot or developer account flow. Several platforms require paid access, review, user opt-in or verified domains, and many manual platforms have no general publishing API.
4. Open a TRUSTED OWNER SSH terminal. Prepare a private directory outside every webroot, checked-out repository, static folder, and hosted uploads.

Example operator commands (replace the private DB path with the ACTUAL location from the personal site's private configuration):

    umask 077
    mkdir -p "$HOME/.private_social_provider_tokens"
    chmod 700 "$HOME/.private_social_provider_tokens"
    export MPW_SOCIAL_CREDENTIAL_VAULT="$HOME/.private_social_provider_tokens/vault.json"

By default, the installed PERSONAL Django app now automatically looks for provider-api-vault.json in the SAME owner-only directory as its private social.sqlite. Therefore no extra cPanel application environment variable is needed when provisioning to that default private path. Use the verified absolute PRIVATE_DB parent directory, not a guessed path. MPW_SOCIAL_CREDENTIAL_VAULT remains an optional explicit override for a different private 0700 directory; when overriding it must be configured consistently in the standalone personal Django process. No real tokens, accounts, or external publishing rights are generated automatically.

Generate a mode-0600 JSON template containing only already registered owner-attested account IDs and BLANK credential strings:

    python scripts/mojtaba_social_hub_cli_20261026.py --db /PRIVATE/OWNER/social.sqlite credential-template --output-private-file "$HOME/.private_social_provider_tokens/provision-once.json"

Fill the blank token strings offline, directly on the trusted owner host. Input JSON fields are schema_version=1, owner_confirmed=true and credentials (array of account_id and token). Example only: {"schema_version":1,"owner_confirmed":true,"credentials":[{"account_id":"REPLACE_WITH_REAL_32_CHARACTER_ID","token":""}]} . This example is NOT importable until filled with actual authorized details.

Preview all 3 brands without modifying a credential file:

    python scripts/mojtaba_social_hub_cli_20261026.py --db /PRIVATE/OWNER/social.sqlite credential-import-preview --vault-file "$MPW_SOCIAL_CREDENTIAL_VAULT" --input-private-file "$HOME/.private_social_provider_tokens/provision-once.json"

Then do the whole private import in ONE atomic owner-confirmed batch:

    python scripts/mojtaba_social_hub_cli_20261026.py --db /PRIVATE/OWNER/social.sqlite credential-import --vault-file "$MPW_SOCIAL_CREDENTIAL_VAULT" --input-private-file "$HOME/.private_social_provider_tokens/provision-once.json" --confirm

For the default standalone production deployment, the private path resolves from the installed site_config.PRIVATE_DB rather than from GitHub or the shared site's settings. The private JSON vault is OS-mode 0600 under an owner-only 0700 directory. It is **not encrypted at rest**; use a dedicated secrets manager for stronger threat models. Do not upload the one-time input file to GitHub, chat, Gmail, a web form, or backup services accessible to others. Delete the one-time input under your normal security procedure after provisioning (SSD snapshots and backups may retain copies).

The staff-only readiness URL then reports credential PRESENCE and the next required verification step:
https://mojplaywin.com/mojtaba.roozegar/social-command/connection-plan/

After importing, explicitly run each provider's READ-ONLY connection test in the private panel. Identity verification does NOT prove publishing scope, remote token refresh capability, posting rights, message delivery or paid advertising access. All outbound operations stay disabled.

## Rotation, revocation, safeguards

To rotate existing credentials, repeat import with --replace --confirm. Previous read-only verifications of changed accounts are invalidated. Without --replace, existing records cannot be overwritten.

To remove a locally stored credential, use:

    python scripts/mojtaba_social_hub_cli_20261026.py --db /PRIVATE/OWNER/social.sqlite credential-disconnect --vault-file "$MPW_SOCIAL_CREDENTIAL_VAULT" --account REAL_REGISTERED_ACCOUNT_ID --confirm

Local disconnect cannot revoke a grant remotely. Revoke it separately in the provider's official security/developer settings. The staff dashboard's separate Suspend Account action also removes the verified public listing and cancels approved but unsent posts.

Safety: account-brand-platform-bound aliases, only administratively owner-attested write-capable accounts, capacity 120, no duplicates, strict source-file permissions, no symlinks/webroots, no mixing an environment variable and vault token for the same account, private locking and one atomic replace, no secret values in CLI output, logs, public JSON, HTML or SQLite, no provider HTTP calls during import. The existing personal-site rollback/deployment never deletes or rewrites this private vault.

Offline tests:

    python -m unittest discover -s tests -p 'test_mojtaba_social_private_bulk_credentials_20261026.py' -v
