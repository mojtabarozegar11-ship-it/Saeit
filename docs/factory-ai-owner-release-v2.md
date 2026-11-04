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
   - The six referenced evidence files MUST exist at `private/autonomous-product-cycle/quality-excellence/ai-review-evidence/<recipe>/<check_id>.json`. Each uses `schema: saeit.factory.ai-review-evidence.v1`, the exact `check_id` and `artifact_sha256`, `status: passed`, `reviewer_kind: chatgpt_ai_assisted_internal`, `independent_human_review: false`, a nonempty review `method`, and nonempty, specific `observations`. The review's `evidence_sha256` must be the real SHA-256 of that particular evidence file's bytes; a syntactically correct invented digest no longer passes.
   - These files make claims traceable and alteration-detectable; they **do not**, by themselves, prove scientific truth, independence, regulatory approval, rights ownership or legitimate professional-quality 1000. All substantive checks still require actual inspection and owner judgment.
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

## Verified rollout state — 2026-11-04

- **Run #214**: 7 new AI-owner signature tests and 28 existing factory tests passed. Integrity-verified source was staged only in `/home/githubops/factory-runtime/operations/ai-owner-release-79d469bb8ac0cd7df3f8ef8e21b167e610d3d013`. Production install, scheduler edits and activation were skipped: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/41782703870
- **Run #215**: separate pinned-SSH, **read-only** administrative/production inventory; the quality test and staging jobs were skipped to conserve quota: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/41783627845
- Actual VPS fields: `AGRI200_ACTIVE_ORDER_PRESENT=YES`, `AGRI200_ALL_COMPLETE=NO`, `LINE41_ACTIVE_COUNT=1`; a global singleton reservation state was not readable/present under the checked path. These records do not establish that both processes are running; neither record may be arbitrarily discarded.
- Real owner public key under root-controlled trust path **not proven**; real receiver trust directory **not proven**, trusted public receiver key count `0`. Mere public key file existence would not prove human identity.
- `githubops` may read its own cron (zero lines matching the keywords `factory` or `agri`) but **cannot read root's crontab**. The system and user systemd timer listings returned zero keyword matches; this does not prove there are no other launch mechanisms.
- **Run #216**: a separate read-only process/freshness inventory was successful: https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/41784241046 . At observation time, the AGRI200 state file was approximately **14,374 minutes** (~10 days) old and line41 state file **9,032 minutes** (~6.3 days) old. Among **40 readable processes**, no command line matched the known AGRI200, line41 or factory-runtime markers; related named running systemd services were also 0. This supports a *possible stale-record hypothesis*, **not proof of zero hidden/root-initiated scheduled jobs**. Never set `all_complete=true` or clear an active slot based only on age and nonmatching process names.
- **Mandatory hold**: no switch of effective factory runtime, no global reservation claim, no second active product, no archive exit, no claim of ChatGPT as independent human, and no publication/payment. These depend on the real owner's privately held signing key with administrator-validated public-key enrollment, genuine receiver identity/acceptance, documented privileged scheduler inventory, and preservation/reconciliation of the live orders.

The obsolete three-human-signature gate may still govern an existing deployed runtime. The new ChatGPT-assisted owner clearance contract exists in reviewed source and isolated VPS staging only; it has **not** been adopted as the production policy.
