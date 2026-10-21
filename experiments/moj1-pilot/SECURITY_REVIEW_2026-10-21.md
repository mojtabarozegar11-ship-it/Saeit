# MOJ1 security review — 2026-10-21

> **Scope:** experimental branch `moj1/shasta-pilot-20261021`; `MojCoin.sol`, `MojAssets.sol`, `MojVestingVault.sol`, Shasta-only deployment code, dependency manifest, tokenomics and CI tests. This is a **preliminary internal review**, not an independent audit or certification. No Shasta/Mainnet token was deployed by this review.

## Verified evidence
- Commit with adversarial checks: `68af30092ce324a4b6810a512a710dc4fdc235f4`.
- [TVM integration pass](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39607596859): **5/5** actual local TRE contract tests. Includes fixed supply / transfer, funded vesting mathematics, valid NFT mint, insufficient-funding and before-cliff reversion receipt checks, blank metadata and former owner rejection.
- [Offline checks pass](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39607596890): **9/9** model/guard tests, compiler 0.8.25, bytecode preflight.
- [Dependency advisory scan](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39607834009): npm reports **3 high / 0 critical** vulnerable package names overall; **2 high / 0 critical** in `--omit=dev`: `axios` (transitive) and `tronweb` (direct). `tronbox` is dev tooling. Many distinct `axios` advisories are grouped under one package count; the number three does **not** mean only three security advisories.
- Public [GitHub advisory example: axios redirect SSRF](https://github.com/advisories/GHSA-r4gj-5m52-g5wh); npm output lists Axios affected ranges under 1.20.0. Check a fully compatible patched dependency tree; **do not blindly downgrade** TronWeb/TronBox based on npm's automated fix suggestion.
- VPS `githubops` read-only preflight succeeded, but Docker/Podman/Node/npm absent, so the TVM was run on an ephemeral GitHub-hosted runner rather than the production VPS. No live site/server installation.

## Findings (unresolved unless explicitly marked addressed)

| ID | Severity | Finding / evidence | Required mitigation |
|---|---|---|---|
| F01 | HIGH - release blocker | npm reports high-severity advisories in runtime dependency chain `tronweb` → `axios`; patched deployment-compatible tree not yet tested. | Confirm exact installed chain, select patched Axios/relevant TronWeb, regenerate the lockfile and prove `npm audit --omit=dev` clean and all TVM tests pass; assess actual exploitability. |
| F02 | HIGH - release blocker | `MojCoin` instantly mints the entire 100bn supply to one constructor treasury. Six allocation percentages in JSON are merely proposed; no allocation distribution or enforced reserve/team schedule is deployed. | Owner approval of allocations; separate independent vaults/locks for all release-limited buckets; immutable, verified beneficiary addresses; fully funded vault receipts; owner-controlled multisignature custody. |
| F03 | HIGH - release blocker | `MojVestingVault` allows any `cliffSeconds` (including zero), arbitrary `startTimestamp` (including historical), and arbitrary allocation/duration. A deployer could configure immediate team unlock contrary to the proposed 12-month cliff. | Deployment policy with fixed approved parameters, timestamp bounds, reproducible manifest and automated checks proving proposed policy; independent scrutiny of deployed constructor values. |
| F04 | MEDIUM-HIGH | A single `Ownable` NFT administrator can mint all 10k items and transfer/renounce ownership. Key theft or mistaken ownership transfer changes mint controls; renouncing ownership permanently blocks future minting. | Multisig owner, two-step ownership transfer, off-chain sign-off and monitoring; document permanent renounce behavior. |
| F05 | MEDIUM-HIGH | `deploy-shasta.mjs` deploys token and NFT sequentially without a durable deployment journal/idempotent resume. A partial failure followed by a retry can create duplicate testnet contracts and spend extra resources. | Store deployment receipt/txIDs and manifest per confirmed step, refuse duplicate deployments without explicit override, verify chain and constructor before any broadcast. |
| F06 | HIGH - test coverage | No actual positive release after cliff/end, partial/full/double-release invariants, reentrancy simulation, malicious token behavior, NFT receiver cases, or property fuzzing. Initial negative tests incorrectly expected JS exceptions; **this test-harness bug is fixed**, and true TVM `REVERT` receipts are now asserted. | Add time-travel TRE tests and post-release state/event assertions, static analysis, fuzzing, independent TVM-aware review. |
| F07 | RELEASE BLOCKER | No security report from an independent auditor, no Shasta contract/address/solidity verification, no energy-fee baseline, and no final legal market-by-market review (gaming/prizes/token sales/custody/sanctions/privacy). | Obtain independent third-party audit and relevant legal sign-offs before public sale, rewards convertible to money, exchange listing or Mainnet. |

## Positives confirmed by source and test
- Token is non-upgradeable and does not expose public owner-mint, freeze or tax setter functions. Solidity 0.8.25 checks arithmetic overflow by default.
- Vesting implements checks-effects-interactions for `release`: it updates `released` before `safeTransfer`; destination is the immutable beneficiary. This is positive design evidence, **not** proof of reentrancy safety under adversarial tokens.
- NFT `safeMint` has owner-only control, recipient/nonempty URI checks and a 10k cap.
- TronBox config exposes only localhost development; isolated CI does not load user wallet keys, Shasta keys or Mainnet endpoints. The optional deployment script is hard-coded to Shasta and gated.

## Release decision

**NO-GO for Mainnet, exchange listing, real reward payouts or sales.** Local test success is necessary but insufficient.

Recommended sequence:
1. Close F01 and run compatibility + npm audit clean.
2. Approve tokenomics and strengthen custody/vesting parameters F02-F04.
3. Complete adversarial TVM tests, static analyzers and third-party audit F06.
4. Verify reproducible Shasta receipts, deployment idempotency, fee limits F05.
5. Complete legal/operational requirements F07, then request **separate explicit owner approval** for any actual Mainnet transaction.

No secret phrase or real private key should ever be supplied to chat, CI logs or the repository.
