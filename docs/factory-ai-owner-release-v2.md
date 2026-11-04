# Factory F-01 release policy v2: ChatGPT-assisted review with real owner approval

**Approved by product owner in conversation on 2026-11-04.** This policy replaces the obsolete expectation that three distinct human reviewers have signed. It does **not** represent ChatGPT as a human, independent legal entity, licensed rights examiner, or holder of a private signing key.

## Authority and separation

- **ChatGPT**: perform and record internal AI-assisted scientific, technical, rights-screening, usability, security and commercial-readiness assessment of the exact SKU archive. The written review is evidence, **not** a digital signature or external independent attestation.
- **Owner Mojtaba Roozegar**: independently decide whether to accept the findings, assert authority to release/rights, and sign the exact clearance JSON with a genuinely owned private key. No other automation may sign on the owner's behalf.
- **Actual recipient**: verify the delivered archive and sign a receipt with a separately trusted receiver key. A self-composed JSON receipt is not acceptance.
- **Factory VPS**: enforce a single product slot and fail closed without these records. It does not need GitHub Actions for its production runtime.

## Storage contract

1. Artifact: `private/autonomous-product-cycle/digital-products/<recipe>/<recipe>-internal-qa.zip`
2. Technical manifest: `private/autonomous-product-cycle/digital-products/<recipe>/manufacturing_manifest.json`, referencing the exact artifact SHA-256, with `qa_status=passed`.
3. AI report: `private/autonomous-product-cycle/quality-excellence/ai-reviews/<recipe>/current.json` with:
   - `schema: saeit.factory.ai-assisted-internal-review.v1`
   - `reviewer_kind: chatgpt_ai_assisted_internal`, `independent_human_review: false`
   - `artifact_sha256` exactly matching the artifact
   - `review_status: completed`, `verified_grade_total: 1000` **only if actually supported by inspection**
   - exactly one passed, artifact-grounded evidence check for each of `scientific_accuracy`, `technical_correctness`, `rights_screening`, `usability`, `security`, `commercial_readiness`; each includes a 64-character SHA-256 evidence reference. Mere hashes without actual reviewed evidence are not substantive proof.
4. Owner clearance: `private/autonomous-product-cycle/quality-excellence/signed-clearances/<recipe>/current.json` with:
   - `schema: saeit.factory.ai-assisted-owner-clearance.v2`
   - `reviewer_kind: chatgpt_ai_assisted_internal`, `independent_human_review: false`
   - `ai_review_sha256` of the **exact** report bytes, `artifact_sha256` of exact archive
   - `eligible: true`, `verified_grade_total: 1000` only after genuine assessment
   - `owner_authorization_kind: direct_owner`, `owner_rights_attestation: true`
   - `publication_executed: false`, `payment_activated: false`
5. Owner detached signature: `owner.sig` adjacent to clearance, produced by the actual owner over **unchanged** `current.json`.
6. Trusted owner's *public* key: `/etc/saeit/factory-owner-approval-public-keys/owner.pem` (root-owned file and root-owned, non-group/world-writable parent directories). A qualified administrator enrolls this after verifying the actual owner's identity and proof of key possession.
7. Receiver `product.zip`, `receipt.json`, `receipt.sig`: under `product-lifecycle/hourly-cycle-handoffs/<R-01|B-01|S-01|G-01>/<recipe>/`, with an authentically enrolled receiver public key under `/etc/saeit/hourly-cycle-receiver-public-keys/`. The receipt binds both artifact and clearance SHA-256.

The owner may produce `owner.sig` on an independently controlled device using OpenSSL `dgst -sha256 -sign`; the factory only verifies it with `openssl dgst -sha256 -verify`. Never send the private key, PIN, recovery seed, or private signing credential to ChatGPT, GitHub Actions, or the VPS worker.

## Fail-closed order of operations

1. One product remains active; rework it as often as justified. The queue is preserved.
2. An AI review of the real build and each applicable source is performed and recorded with actual traceable evidence. If any check is unresolved, grade is **not** 1000 and no exit is permitted.
3. The real owner signs the exact release clearance. A forged/signatureless/silent AI clearance does not release the product.
4. An authorized actual recipient signs proof of exact-build delivery.
5. Only after BOTH owner-authorized clearance AND genuine receiver handoff can the same product be archived as exited and the next queued product admitted.
6. No publication, sale, payment activation or destruction of user-owned backlog is implied by this internal factory handoff.

## Current rollout state

The policy has been prepared in a development branch, **not deployed to the VPS**. The 2026-11-04 read-only inventory showed that AGRI200 retained an unresolved active order, line41 retained one active SKU, global ownership was unverified, and the `githubops` account could not read root's crontab. The new owner public key is not yet proven to exist under admin control. Do not start a competing worker or claim a QC1000 commercial release until administrative preflight is clear.

The obsolete three-human-signature gate should remain on any already-deployed version until a reviewed deployment atomically changes the versioned contract. It must never be replaced by pretending ChatGPT has three real reviewer identities.
