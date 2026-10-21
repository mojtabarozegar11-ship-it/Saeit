# MOJ1 pilot validation receipt — 2026-10-21

> Scope: experimental branch `moj1/shasta-pilot-20261021` at test implementation commit [`6e3834c`](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/6e3834c5f208f3a218788bea13874253e8da45ad). These are checks on an isolated, disposable CI runner, **not** on a production chain or VPS.

## Executed and verified in GitHub Actions

1. [Offline workflow run 39620243558](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39620243558) — **PASS, 14/14** Node tests: allocation arithmetic, offline invariants and release caps, approval guards, vesting boundary probes and Mainnet/missing-wallet refusal guards. These tests do **not** alone exercise smart-contract behavior.
2. The same offline run — **PASS**, Solidity `0.8.25` compilation via TronBox, offline ABI/bytecode preflight, SHA-256 digests, constructor/function checks and Shasta-only deployment guard. No blockchain RPC, test-wallet key, broadcast or real asset was used.
3. [Disposable local TVM workflow run 39620243446](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39620243446) — **PASS, 11/11** smart-contract integration tests. Verified fixed escrow supply and atomic six-vault funding; authorization/replay/invalid configuration reverts; capped liquidity and contingency reserves; time-simulated positive release after 30-day notice, 90-day spacing, cancellation and token conservation; vesting-cliff and NFT safeguards. Reserve clock advancement uses `contracts/test/MojApprovalReserveClockHarness.sol` **only in isolated test contracts**, and this harness is intentionally unsafe for production. Two additional tests use the **unmodified real linear-vesting contract** with funded standalone historical-start local fixtures: they prove fully matured payouts, underfunding and replay rejection, partial payout and exact conservation. Genesis distribution still prohibits historical starts.
4. Earlier local source/install/syntax and asset-image checks were documented in prior revisions. Do not misinterpret these CI receipts as direct VPS tests.

## Not performed / still required

- **No Shasta or Mainnet deployment**, contract address, energy payment, wallet funding, public mint, transfer, sale, exchange listing or custody operation.
- No production deployment-bytecode verification, vetted multisig or validated beneficiary addresses. The unsafe clock harness must be excluded from any real deployment manifest or genesis vault.
- No full-cliff time-advance test against an actual **genesis-funded** vesting vault, exhaustive adversarial token/NFT receiver or reentrancy simulation, property fuzzing, or independent third-party security audit.
- The production VPS reportedly lacks Docker/Podman/Node; tests ran on an ephemeral GitHub-hosted TVM runner, not on that VPS.
- Actual reserve schedules, beneficiary identities, final custody governance, required legal reviews and any irreversible transaction await **separate explicit owner approval**.

**Release decision: NO-GO for Mainnet, real assets, token sale, exchange listing or payouts.** These passing tests verify selected code paths only and do not establish production security, token value, legal compliance or deployment authority.

See [security review](SECURITY_REVIEW_2026-10-21.md) and [unapproved release schedule](RELEASE_SCHEDULE_PROPOSAL_2026-10-21.md).
