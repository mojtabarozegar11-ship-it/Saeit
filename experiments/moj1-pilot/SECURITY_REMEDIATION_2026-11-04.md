# MOJ1 security remediation — 2026-11-04

Status: **unmerged candidate, Mainnet NO-GO**. No real-token operation or release approval.

## Implemented in this isolated branch

- Introduced `MojGovernanceGuarded.sol`, a separate candidate from the existing deployed Shasta pilot governance.
- Two distinct signer approvals are required per nonce/domain-bound operation. The first two approvals schedule an immutable call hash; a third approval cannot shorten the delay.
- External-contract operations wait at least 48 hours; self-operations (including signer replacement and nonce cancellation) wait seven days.
- Signer rotation requires a self-call approved by two current signers and passing the seven-day delay. Nonzero and distinct signer sets are enforced.
- Nonces are advanced before external calls to block replay and reentrant execution; failed calls roll back the nonce and side effects.
- An additional stacked, **unmerged emergency-veto candidate** now lets two distinct current owners cancel a pending nonce immediately. This fixes the previously identified gap between a 48-hour external-operation timelock and the seven-day self-operation cancellation path. See `EMERGENCY_GOVERNANCE_VETO_2026-11-04.md` for the remaining audit gates.
- A separate **unsafe local-only** clock harness and actual TRON TVM tests were added. The harness must never be authorized as production governance.

## Reward liability: do not turn a rightful obligation into a treasury sweep

`MojRewardClaimsPilot` reserves the unpublished/unused portion of a claimed epoch. This can look like stranded tokens if an operator publishes a budget larger than the total Merkle entitlements. However, an **unclaimed valid reward is still a liability**. Blindly freeing any remainder after the first claim, or imposing an unapproved expiry, can confiscate valid users' rewards.

The existing offline proposal builder enforces `budgetUnits == sum(amountUnits)` and no duplicate wallets or indices; the contract still cannot independently prove that a conventional Merkle root contains the asserted complete list and sum. A signer can bypass the offline builder and publish arbitrary calldata. This is an unresolved trust/control boundary, **not a safely removable bookkeeping balance**.

Required before a live reward launch:

1. Freeze an independently auditable complete entitlement manifest from the actual reward ledger; independently verify its root, sum, unique beneficiaries and source event receipts.
2. Bind the signed authorization to the exact root, domain, recipient count, total entitlement, source digest, contract and chain. Make the validated proposal-to-governance-call path fail closed.
3. Decide a disclosed, legally reviewed policy for never-claimed rewards. Until a policy is authorized and independently audited, keep legitimate unclaimed allocations reserved with an indefinitely available claim path. **No automatic confiscation/sweep.**
4. Include the reward escrow, root-builder and payout integration in the independent TVM audit, beyond the original four-contract quote.

## Not yet satisfied

- New governance bytecode and integration tests must pass isolated TVM CI, be independently reviewed, and be bound to a frozen release manifest.
- Key owners, independent signers, secure storage, backup, quorum-loss recovery and legal entitlements require genuine owner-controlled decisions/evidence.
- Prior F08 V1 Shasta distribution remains prohibited. The current V2 Shasta escrow and existing mainnet restrictions are unchanged.
- Energy/fee_limit must be estimated and bounded on the actual target chain for each approved deployment or multi-vault distribution.
- No developer, ChatGPT, automatic tool or self-signed review may claim to replace a qualified independent auditor or give legal clearance.
