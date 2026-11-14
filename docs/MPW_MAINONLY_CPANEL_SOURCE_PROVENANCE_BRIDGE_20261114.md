# Independent, narrow owner-only cPanel source-provenance bridge

This branch is based directly on `main` and touches **only** the existing read-only GitHub Actions → VPS → cPanel bridge. It is an alternative to merging the unrelated 115-commit checkout audit PR merely to obtain source-provenance metadata.

## Why this is needed
The currently deployed `main` does not advertise `mpw_source_provenance` in the direct bridge, and its cPanel SSH hostname uses a stale direct IP instead of the known pinned DNS host. Meanwhile sanitized UAPI inventory identified a real `mojplaywin.com` Passenger registration root which did not match the old cutover's two expected candidate path fingerprints. The effective Django template is still unknown.

## Scope
- Adds **one** allowlisted `mpw_source_provenance` operation to the already existing main-only `workflow_dispatch` choices; no new broad SSH commands or elevated capabilities.
- Corrects only the known cPanel connection hostname, retaining the pinned expected ed25519 key fingerprint, `StrictHostKeyChecking yes`, no agent forwarding and a one-hourly owner-controlled run model.
- Streams one exact immutable Git blob (pin `da126a27de047239b46148ce0b878cebf53ad109`) to `python3 -B -` on the existing cPanel account; no source copied to server, no imports of Django, no SQL, payments, email or mutations.
- Exposes redacted category labels and 16-character file digest prefixes, never raw paths, customer information or credentials.
- The PR's own GitHub Actions uses only `ubuntu-latest` with `contents:read`; it does NOT access or authenticate to the owner's cPanel. The remote operation cannot run from a PR; requires manual workflow dispatch **from main after a separately authorized merge**.

Do **not** merge/deploy, restart, modify DNS or order systems, or spend money without explicit user approval. The branch improves an inspection capability, not storefront commercial readiness or settlement.