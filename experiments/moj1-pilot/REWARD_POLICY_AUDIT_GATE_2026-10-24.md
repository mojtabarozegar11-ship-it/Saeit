# MOJ1 reward entitlement, anti-abuse and external audit gate — DRAFT (2026-10-24)

**Release verdict: NO-GO.** This file is a proposed control specification, **not** the token owner's approval, a security attestation, an anti-Sybil identity service, a legal opinion or authorization to issue/claim transferable MOJ1. This branch is test-only. Do not share personal records, mnemonic seeds, API keys or actual customer exports in GitHub/CI.

## 1. Proposed entitlement policy — requires owner and legal approval

| Control | Draft decision / required evidence | Status |
|---|---|---|
| Reward event | A uniquely identified, verifiable completed activity; immutable source-event receipt, timestamp and category | **Unapproved** |
| Unit of entitlement | Only the amount demonstrated by a signed/retained source-of-truth reward ledger, not a wallet balance or self-declared input | **Unapproved** |
| Person/account eligibility | Opt-in terms, age/jurisdiction/sanctions/privacy assessment where applicable, and proof appropriate to reward value | **Unapproved** |
| Wallet ownership | A challenge signature from the beneficiary, verified without storing wallet private keys | **Unimplemented** |
| Replay | Reject repeated source-event IDs across all epochs and duplicate claim indices within an epoch | Synthetic-only checks |
| Multi-wallet abuse | Review stable pseudonymous subject-to-wallet links, wallet sharing, and wallet rotation; do not equate one wallet with one human | Synthetic-only flags |
| Amount limits | Configurable owner-approved per-event, per-person, per-epoch limits; on-chain pre-funded escrow and total liability reconciliation | **Unapproved** |
| Appeals | Human review of false positives, immutable decision record, appeal deadline and withheld-claim process | **Unimplemented** |
| Data handling | Store only minimum pseudonymous attributes in screening; avoid names, IDs, addresses, email/IP in public logs | Synthetic test schema enforces exclusions |
| Approval of a Merkle root | Independent evidence sign-off, compliance clearance, approved rewards policy, on-chain funding/contract/domain verification and owner-controlled 2-of-3 governance with signed root digest | **Not satisfied** |

The proposed categories TEST-GAMEPLAY and TEST-RESEARCH in code are **invented synthetic test labels**, not approved real earning programs. Neither user participation nor exchange/value expectations establish legal entitlement. No automatic decision may conclude human uniqueness based on wallet, IP, device or a single account identifier.

## 2. Current automated controls

- `scripts/reward-eligibility-offline.mjs` produces **synthetic** Merkle proposals, never signatures, publish calldata or approvals.
- `scripts/reward-policy-review-offline.mjs` screens **synthetic** pseudonymous histories for duplicate index/wallet/subject/event/evidence, event replay across epochs, reused wallet/subject, wallet rotation and proposed per-event/batch caps. Both code paths reject real/approved modes and unsupported fields. All outputs remain `NO_GO`; even a zero-flag result is **not** an approval.
- `tests/reward-policy-review-offline.test.mjs` contains adversarial abuse cases. Integration tests additionally verify local TVM Merkle domain separation, anti-double-claim and exact funding liability.
- The existing off-chain `fundedAvailableUnits` remains **self-reported test input**. It is not an on-chain balance attestation. No root is publishable based on it.

## 3. Independent external audit scope / request for proposals

Send the **immutable audited commit SHA** to a genuine independent, TVM/TRON-capable Solidity auditor, and request:

1. Line-by-line review of `MojRewardClaimsPilot.sol`, `MojPilotGovernance.sol`, Merkle leaf encoding, total liabilities, budget funding, expiry/cancel logic, authorization and all affected escrow/token contracts.
2. Adversarial tests: malicious/fee-on-transfer/reentrant tokens, governance replay/front-run, cross-chain and cross-contract proof substitution, duplicate subject, corrupted source ledger, partially claimed epoch liability lock and rollback.
3. Static analysis, property tests/fuzzing, deterministic builds/compiler verification and TRON TVM-vs-EVM behavioral differences.
4. Review of the entire token distribution dependency chain, especially unresolved genesis vault impersonation finding F08 / relevant security-review findings.
5. Explicit limitations of anti-Sybil verification, off-chain identity/beneficiary controls and data protection. Merkle proof authenticates inclusion **only**.
6. A signed report with severity, proof-of-concept, precise fixes, retests, reviewer identity, conflict-of-interest disclosure and final disposition of each finding.

**Acceptance:** independent report + issue-level remediation + code re-review + reproducible test evidence. The authors and ChatGPT cannot certify their own code as independently audited.

## 4. Shasta integration gate

The existing `shasta-deployment.json` names **previously deployed pilot governance/token/NFT/genesis contracts**, **not** a published rewards Merkle escrow. The new reward claim escrow has **no verified Shasta deployment address or transaction receipt in this branch**. Do not treat the prior token deployment as a reward-claims integration pass.

Before any *testnet-only*, irreversible reward transaction, gather and independently check:

- Approved Shasta-only owner-controlled test wallet/signer process **outside CI and ChatGPT**, only free test TRX; never use Mainnet or production funds.
- The exact compiled reward-escrow runtime bytecode, constructor token/governance addresses, contract creation tx, confirmed solidified receipt and independently reproduced source hash.
- On-chain `block.chainid`, `availableToCommit()`, `outstandingCommitments`, token balances, owner/governor identities and nonce at a pinned solidified block.
- A synthetic test root from the **same** chain/contract/epoch; verify a valid claim, forged proof, cross-domain proof, duplicate beneficiary/index, unfunded epoch, cancellation and revert receipts.
- Complete journal, gas/energy/fee ceiling and emergency/incident procedure.

**Stop condition:** if no verified reward escrow, governance signers, journal or separately approved testnet operation exists, the Shasta reward payout test must remain **NOT RUN / BLOCKED**. Do not invent Shasta receipts.

## 5. Hard release gates

- Keep PR #1051 a draft, no production merge, no Mainnet, no public token rewards or merchant-wallet integrations.
- A successful local CI run is evidence about **the tested code**, not an audit or legal approval.
- The existing offline release checker must continue emitting `BLOCKED` with independent audit, eligibility policy, anti-Sybil, Shasta claim escrow, legal review, signer and owner-approval blockers.
- When all prerequisites are later genuinely obtained, a separate source-controlled, human-reviewed owner authorization and repeat audit is required before any new release mechanism is even considered.
