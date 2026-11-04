# MOJ1 reward sum-guard — security review, 2026-11-04

**Status: UNMERGED, UNDEPLOYED CANDIDATE. Mainnet NO-GO.** This contract is not included in the prior four-contract BlockHat quote. A separate independent TVM audit and rights/claims review are required.

## What the contract actually verifies

- A proof binds an eligible-looking `(epoch, leaf index, beneficiary, amount)` to the exact chain ID and escrow address.
- Internal node hashes bind each child hash, sum and leaf count. A proven leaf can pay only if the full path reconstructs the governance-published root, epoch budget and leaf count.
- Contract balance must fund all previously committed but unpaid epochs before another epoch may be published.
- Each leaf index and beneficiary may be paid at most once per epoch. Relayers can submit proofs but cannot redirect a valid payment.
- Payments reduce the outstanding liability only by what was actually claimed. No cancellation, expiry, administrative seizure, treasury sweep or general external-call function exists in this escrow.

## What a sum proof does NOT establish

- A valid root does **not** prove every legitimately eligible player was included. An authorized publisher could omit players or use false source data.
- It does not establish that the published manifest represents real game-play events or real-world claims. Completeness, correct amounts, source ledger receipts and anti-Sybil/identity policy require **independent, off-chain verification**.
- Hash binding does not guarantee a correctly constructed off-chain tree; the root and accompanying signed manifest must be independently reproduced from a canonical entitlement ledger.
- One claim per beneficiary *per epoch* assumes the manifest consolidates legitimate multiple rewards to one leaf per wallet. Dedup errors may leave valid funds locked; no emergency confiscation is authorized as a workaround.
- `scripts/reward-sum-guard-offline.mjs` is a **synthetic-only candidate** for the exact on-chain Merkle-sum format; its SHA-256 digest covers the synthetic proposal, not a verified live source-of-truth ledger. It intentionally cannot certify or authorize any real payout.
- This candidate only tests with a synthetic, ordinary TRC20 token. Transfer-tax, rebasing, blacklisting, nonstandard responses and malicious token behavior are not approved.
- All reward eligibility, custody, legal rights, policy, energy limits, upgrade/migration paths, signer recovery and independent security review remain unresolved for production.

## Required release gates

1. Freeze the input game-event ledger and its audited receipts, deduplicate wallets by a declared policy, and sign the complete entitlement manifest plus source digest.
2. Independently reproduce the exact root, aggregate sum and leaf count. Validate proofs for **every** source leaf, not merely samples. Reject duplicate wallet/index, missing player, zero entitlement, inconsistent amount or stale epoch.
3. Obtain independent security audit covering this reward escrow, canonical tree builder, governance and live game purchase/award integration. Earlier BlockHat scope is insufficient.
4. Confirm each beneficiary can obtain a claim proof without account creation and that support/recovery and non-expiring unclaimed rewards are documented.
5. Prohibit Mainnet deployment, public reward funding, real user claim migration and any new financial commitment until the prior gates, verified signers, audit report and owner authorization are satisfied.

## Test evidence

The separate workflow tests the contract only on a disposable localhost TRON TVM, including forgery, replay, cross-domain claim refusal, exact two-leaf sums, duplicate beneficiary and protection of unpaid liabilities. It also tests the synthetic builder deterministically offline and reconstructs the same leaf/root on the actual local TVM. CI success alone is not an independent audit or production authorization.
