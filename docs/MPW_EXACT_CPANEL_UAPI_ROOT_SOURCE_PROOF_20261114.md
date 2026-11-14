# Exact Passenger registration vs MojPlayWin paid checkout — 2026-11-14

## Root-cause progress, not another guessed path
Existing **real read-only cPanel UAPI** reports one MojPlayWin app whose root fingerprint differs from both previously assumed stage/public paths. The prior neighbor scan in PR #2291 only checks candidates and cannot distinguish which of them is **the registered application root**. This changes the pinned one-operation source inspector to query the same fixed read-only PassengerApps `list_applications` function **locally from the authorized cPanel user** at the time the existing `mpw_source_provenance` command is deliberately dispatched after a separately approved main merge.

## Security contract
- Executes exactly `uapi --output=json PassengerApps list_applications` using a fixed argument array, without `shell=True`, redacted stderr and a 12-second timeout; refuses response bodies larger than 128 KiB, duplicate JSON keys, invalid JSON, non-success and ambiguous target registrations.
- Accepts one **literal original** UAPI root. The path must be an absolute subdirectory of the authorized account home, with no dot traversal, double-slash or symlinks anywhere below the home. Other accounts, missing or unsafe paths and inconsistent registrations categorically fail closed.
- Reports only fixed classifications, capped marker counts, and SHA-256[:16] digests of the registered root, checkout source and static template. Never emits raw roots, UAPI JSON, source bodies, customer records or secrets. The known cPanel owner account guard stays enforced.
- Distinguishes a **single usable required email field in a static POST HTML form** and a literal `script-src` source marker from the effective Passenger worker, template loader, live CSP, verified POST order, confirmed TRX settlement, paid entitlement and collected revenue; all latter remain unverified/unknown.
- Retains direct read-only handler on two SSH hops with an updated immutable Git source pin, pinned host fingerprints, fixed operation allowlist and owner-only `main` dispatch. No new workflow automatically connects to cPanel.

## Acceptance & deployment boundary
54 new adversarial Python tests plus 156 earlier relevant tests execute in unprivileged GitHub CI using synthetic fixtures and stubbed UAPI. This **does not** run the new code against the live cPanel until a separately approved merge and main-only dispatch. Existing public GET evidence still shows `/store/` static fallback and six checkout responses with missing expected `script-src`; after source origin is determined, separately plan an approved reversible patch and independently verify real payment and delivery.

**NO-GO** for production release, funds, user emails, order creation, merges or source deletion. Sole organizational robot: `mojtaba.bot.ai`.