# MPW registered Passenger root candidate discovery — source-only, owner-gated

## Concrete revenue blocker
The previous real, owner-authorized cPanel UAPI `PassengerApps list_applications` reported exactly one MojPlayWin mapping whose app-root SHA256[:16] did not equal the two hard-coded candidate roots in the cutover code. This discrepancy prevents trustworthy claims about which version of the digital shop, checkout and CSP is live. The existing `/store/` public GET still served the static fallback; six checkout pages lacked the desired script-src CSP in the last public observation.

## Implemented safe inspection
**Only the owner-controlled read-only cPanel source probe is extended**, and its exact Git blob is independently pinned in both relay hops. The probe checks at most 96 immediate non-symlink entries beneath the same cPanel account home for regular, bounded WSGI, manage.py and two MojPlayWin commerce source markers. Unlike a broad filesystem audit it does not recurse, inspect neighboring source contents or expose directory names/absolute paths. It reports at most 16 SHA256[:16] candidate fingerprints with coarse classes. Overflow returns an empty unverified result. This cannot see nested roots or actual WSGI workers and does not claim to.

An additional **offline-only** joiner accepts just the existing redacted UAPI inventory and new redacted source report, rejects raw UAPI, conflicting duplicates, invalid/unsafe reports or inconsistent counts, and returns one of four fixed classifications: matching immediate candidate, no immediate match, incomplete scan, or ambiguous mapping. **A matching 64-bit prefix is not a cryptographic runtime attestation and does not prove a loaded Django template**.

## Verification and further approved execution
- `35` adversarial scan tests, `35` adversarial joiner tests and existing provenance/bridge regressions are run in source-only unprivileged GitHub CI. The CI does not have SSH keys, access cPanel, use customer data or create orders.
- Before any production fix, separately approve and merge the exact main-only source-provenance bridge and then deliberately dispatch the **existing named read-only** `mpw_source_provenance` operation. Match its source evidence with the existing UAPI inventory on a trusted runner. Do not force the website's root to an assumed path merely because a fingerprint corresponds.
- Effective Passenger registration, active worker, Django template, applied migrations, live CSP, email-bound POST, settled TRX and paid private delivery require independent evidence. Production deployment and payment still require separate approval and a reversible release plan.

Canonical organizational bot only: `mojtaba.bot.ai`. No paid dependency, no live edits, no new robot.

## Cycle 11 — exact UAPI-registered path source evidence (main-only, owner-dispatched)
The source-only probe now makes one fixed **read-only** local cPanel UAPI call (`uapi --output=json PassengerApps list_applications`) with no shell interpolation, a 12-second timeout, stderr suppressed, and a strict maximum JSON response size. It rejects malformed/ambiguous registrations. The registered app root is inspected **only if** the literal path is absolute, within the designated cPanel home account, has no traversal or symlink components, and contains bounded regular files. The report emits 16-character SHA prefixes, fixed category labels and boolean existence checks, **never paths, raw UAPI JSON, source contents or customer information**. The exact streamed source blob SHA was updated to `dfefb70fb137b8c9daaa20b2713846745dc8ec78` on both pinned-SSH paths.

This is a **more precise source ownership diagnostic** than guessing two hard-coded roots, but neither UAPI registration nor static source proves which Passenger worker serves the live `/store/` or the six checkout pages. Only an owner-approved later read-only dispatch after a separately approved main merge can measure the real environment. Never infer real payment, delivery or collected revenue from the UAPI source report.
