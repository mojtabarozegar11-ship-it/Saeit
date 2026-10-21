# MOJ1 pilot validation receipt — 2026-10-21

> Scope: experimental branch `moj1/shasta-pilot-20261021` at deployment-journal implementation commit [`0ce0011`](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/0ce0011367a8d5e9a7f4fadd470d4d317e915884). These are checks on an isolated, disposable CI runner, **not** on a production chain or VPS.

## Executed and verified in GitHub Actions

1. [Offline workflow run 39622568966](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39622568966) — **PASS, 19/19** Node tests: allocation arithmetic, offline invariants and release caps, approval guards, vesting boundary probes and Mainnet/missing-wallet refusal guards. These tests do **not** alone exercise smart-contract behavior.
2. The same offline run — **PASS**, Solidity `0.8.25` compilation via TronBox, offline ABI/bytecode preflight, SHA-256 digests, constructor/function checks and Shasta-only deployment guard. No blockchain RPC, test-wallet key, broadcast or real asset was used.
3. [Disposable local TVM workflow run 39622569011](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39622569011) — **PASS, 11/11** smart-contract integration tests. Verified fixed escrow supply and atomic six-vault funding; authorization/replay/invalid configuration reverts; capped liquidity and contingency reserves; time-simulated positive release after 30-day notice, 90-day spacing, cancellation and token conservation; vesting-cliff and NFT safeguards. Reserve clock advancement uses `contracts/test/MojApprovalReserveClockHarness.sol` **only in isolated test contracts**, and this harness is intentionally unsafe for production. Two additional tests use the **unmodified real linear-vesting contract** with funded standalone historical-start local fixtures: they prove fully matured payouts, underfunding and replay rejection, partial payout and exact conservation. Genesis distribution still prohibits historical starts.
4. The offline run also exercises the fail-closed Shasta deployment journal: exclusive locking, persistent pre-broadcast ambiguity marker, refusal to redeploy after an unknown outcome, idempotent reuse of confirmed entries, mismatched governance/artifact rejection, and refusal to run without an external absolute journal path. **These journal tests mock the filesystem state and never transmit a transaction.**
5. Earlier local source/install/syntax and asset-image checks were documented in prior revisions. Do not misinterpret these CI receipts as direct VPS tests.

## Not performed / still required

- **No Shasta or Mainnet deployment**, contract address, energy payment, wallet funding, public mint, transfer, sale, exchange listing or custody operation.
- No actual recovery of an uncertain Shasta deployment, no journaled pre-signed txID/on-chain source attestation, no production deployment-bytecode verification, vetted multisig or validated beneficiary addresses. The unsafe clock harness must be excluded from any real deployment manifest or genesis vault.
- No full-cliff time-advance test against an actual **genesis-funded** vesting vault, exhaustive adversarial token/NFT receiver or reentrancy simulation, property fuzzing, or independent third-party security audit.
- The production VPS reportedly lacks Docker/Podman/Node; tests ran on an ephemeral GitHub-hosted TVM runner, not on that VPS.
- Actual reserve schedules, beneficiary identities, final custody governance, required legal reviews and any irreversible transaction await **separate explicit owner approval**.

**Release decision: NO-GO for Mainnet, real assets, token sale, exchange listing or payouts.** These passing tests verify selected code paths only and do not establish production security, token value, legal compliance or deployment authority.

See [security review](SECURITY_REVIEW_2026-10-21.md) and [unapproved release schedule](RELEASE_SCHEDULE_PROPOSAL_2026-10-21.md).
