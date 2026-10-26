# Moj 1 and Moj Digital Assets — pilot 0.8 (F02 capped reserve prototype)

**Current status:** draft testnet code. The owner approved the project name `Moj 1`, ticker `MOJ1`, fixed 100-billion-unit supply, and the six allocation percentages on 21 October 2026. Uniqueness, trademarks, issuer identity, beneficiary addresses, release schedules and legal assessments remain open. Test-only V1 and guarded V2 token contracts are recorded on Shasta; no Mainnet token, public sale, or liquid market has launched. The artwork supplied by the owner is included as a reference image, not an on-chain identity claim.

## Guarded V2 status and release gate (26 October 2026)

The guarded **V2** testnet candidate has its own [Shasta V2 manifest](shasta-v2-deployment.json), separate from legacy V1 `shasta-deployment.json`: candidate token `TA8dcG3b9GByaY9vZ1LVjsFohZrZ4CveAY`, candidate factory/escrow `TCBNLE1ZgEcAWXRZ6jjYPSyUH7WiHpLyBm`. The source audit anchor is commit `4411b28325be44c54d7917b4c67786348521b6a9`; development hardening is not itself an external security attestation. The V2 manifest records the full 100-billion supply in escrow and no distribution, real payments, sale or Mainnet deployment.

The zero-key, zero-network [V2 market gate](scripts/v2-market-readiness-offline.mjs) checks V1/V2 separation, the fixed supply, all six allocations, frozen audit anchor and closed distribution/sale flags. Run `node scripts/v2-market-readiness-offline.mjs --assert-blocked` only from this project directory; the script **always** reports `NO_GO` even when the manifests are consistent. It must not be used as a release authorization. The [offline liquidity calculator](tools/liquidity-scenario.mjs) is a hypothetical constant-product model and does not discover a live price or supply a market. Independent audit, real custody, beneficiaries, legal review, genuine paired liquidity and separate owner authorization remain mandatory gates.

## What is implemented

| Component | Scope | Limit |
|---|---|---|
| `contracts/MojCoin.sol` | TRC-20, 100 billion MOJ1 initial and maximum, 18 decimals, supply minted into a newly created genesis escrow contract, not to an external wallet | No mint extension, freeze, taxes or upgrade admin |
| `contracts/MojAssets.sol` | TRC-721, 10,000 maximum unique items, restricted mint, per-item URI | Not a live NFT store; metadata hosting and rights are not built |
| `contracts/MojVestingVault.sol` | Non-revocable cliff and linear vesting for a **single funded allocation** | Locally deployed/funded/tested on TVM only; no Shasta/Mainnet vault or lock |
| `contracts/MojGenesisDistributor.sol` | Initial escrow validates six distinct bucket vaults and atomically funds all 100bn units once | Six percentages are owner-approved; release schedules, governance and beneficiaries are not |
| `contracts/MojApprovalReserve.sol` | Two governed, individually capped liquidity/contingency tranches with 30-day notice and >=90-day spacing | These release rules are only code in an experimental branch; owner schedule approval, real multisig and audit outstanding |
| `tokenomics.json` | Six owner-approved allocation percentages cross-checked with on-chain constants | Release schedules, recipients and execution not approved |
| `tests/` | Offline and disposable TVM behavioral tests, including capped releases and simulated passage of time | No Shasta or Mainnet transactions; no independent auditor attestation |
| `scripts/preflight-offline.mjs` | Verifies bytecode, ABI, compiler version, forbidden admin interfaces and Shasta-only guard; prints immutable bytecode SHA-256 digests | Static/offline review, not a broadcast or an independent audit |
| `scripts/deploy-shasta.mjs` | Testnet deployment and basic on-chain token verification | No Mainnet deployment capability |

Do not use this prototype for public deposits, sales, guaranteed returns, or production rewards. A fixed-supply token does not have intrinsic market value or an automatic exchange listing. The token and NFT smart contracts are distinct from **Moj Points**, which should remain a non-transferable, non-redeemable game account balance.

## Safe test sequence

```sh
npm install
npm test
npm run compile
npm run preflight
```

The F02 pilot now mints the entire fixed 100-billion-unit supply directly into an immutable genesis escrow, not a treasury wallet. A single atomic transaction can fund six independently deployed, precisely validated vaults: player rewards 35% (1,825-day linear vesting), development 20% (1,460 days), liquidity reserve 15% (proposed 1bn maximum per 90-day tranche, each with at least 30-day notice), team 10% (365-day cliff followed by 1,095-day linear vesting), partners 15% (1,460 days), contingency reserve 5% (proposed 250m maximum per 90-day tranche, each with at least 30-day notice). The distributor verifies the fully funded escrow, future vesting start, immutable vault parameters (including tranche caps and timing), distinct destinations and full supply conservation; there is no unilateral withdrawal or second distribution. Capped reserve release behavior passed **9/9 integration checks** on a disposable local TVM, including positive releases after simulated time advances. The public-clock test harness is deliberately unsafe for real funds and must never be used as an actual vault; the governance and deployed vault bytecode must be independently verified before any real distribution. Only owner-approved, independently verified production vault addresses can be distributed to. **The six allocation percentages were owner-approved on 2026-10-21; the specific release schedules, beneficiaries, security audit, live lock and distribution remain unapproved or unperformed.** The six real beneficiaries and externally audited multisig controller remain unselected.

At experimental code commit [`7c50f2b`](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/7c50f2be5e9a15cda1b10930a682b89a24bf22ef), the expanded F02 suite `tests/tronbox/vesting.integration.js` [passed **9/9 behavioral contract tests on disposable local TRE**](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39616657537), including escrow funding of all six allocations, restricted calls, vesting cliff, NFT checks, reserve tranche caps, positive release after simulated delay, mandatory spacing, cancellation, and replay rejection. [Offline CI passed **13/13**](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39616657566), plus compiler and bytecode preflight. The production VPS lacks Docker/Podman/Node, so TRE was not installed there. These tests are **not** Shasta/Mainnet deployments or an independent security audit. See [security review and release blockers](SECURITY_REVIEW_2026-10-21.md), including resolved F01 pilot dependency vulnerabilities and remaining F02-F07 release blockers.



**Latest linear-vesting test extension:** [implementation commit `6e3834c`](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/6e3834c5f208f3a218788bea13874253e8da45ad) passed [**11/11 real TVM checks**](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39620243446) and [**14/14 offline checks**](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39620243558). Additional tests fund *unmodified production vesting vault code* from disposable test tokens and prove a matured team-style vault releases to its immutable beneficiary exactly once, an unfunded matured vault cannot release, and a half-vested vault pays only the accrued fraction while retaining its unvested balance. Historical start timestamps are used solely for **standalone** test vaults; genesis distributor still rejects historical starts, and no clock override is added to the production vesting contract.

See [unapproved staged release design](RELEASE_SCHEDULE_PROPOSAL_2026-10-21.md). Neither adding cap logic nor having passing CI approves the schedule or real beneficiaries.

For optional on-chain testing: only after tests and security review, the owner creates a **new, dedicated Shasta-only test wallet**, funds it with free test TRX, and controls its signing key privately. Never send private keys or seed phrases to a chat, repository or contractor.

```sh
export MOJ1_DEPLOY_CONFIRM=SHASTA_ONLY
export MOJ_SHASTA_GOVERNANCE=YOUR_VERIFIED_SHASTA_MULTISIG_CONTRACT_ADDRESS
export MOJ1_DEPLOY_JOURNAL_PATH=/PRIVATE/PERSISTENT/PATH/moj1-shasta.json
export TRON_PRIVATE_KEY=YOUR_TEST_ONLY_PRIVATE_KEY
npm run deploy:shasta
unset TRON_PRIVATE_KEY
```

The deployer requires an operator-controlled, **persistent external journal path** and saves the **signed transaction ID, exact raw-payload SHA-256, and expected contract address before the first possible broadcast**; no private key, signature or signed payload is saved. A single submission is attempted. On a subsequent run it checks the existing transaction's raw payload, solidified execution receipt, precomputed address and deployed code **read-only** before marking a contract verified. It never automatically generates or broadcasts a replacement transaction. Recovered addresses are rechecked against the MOJ1 token/escrow or NFT-owner invariants. **Never delete a pending journal or lock merely to retry**. Pre-existing legacy `BROADCAST_UNCERTAIN` entries without a recorded txID are intentionally not auto-cleared. A finalized failure, missing chain evidence or RPC uncertainty also remains blocked. This is transaction recovery, **not** a full independent source-code audit.

To reconcile without loading any signing key (no transaction can be sent by this command), compile the identical pinned artifacts, then run:

```sh
export MOJ1_DEPLOY_JOURNAL_PATH=/PRIVATE/PERSISTENT/PATH/moj1-shasta.json
npm run compile
npm run reconcile:shasta
```

Run the command only against the original external journal; copy it safely to preserve the audit trail. A surviving `.lock` after a crashed process must be investigated by the operator before any lock cleanup. A missing journal or absent txID is **never** permission to redeploy.

The script points only at `api.shasta.trongrid.io`; it has no mainnet option and requires a previously deployed Shasta governance contract, which must separately be verified as an approved multisig. It does not distribute the escrow. A successful deployment must then be verified on Shasta TRONSCAN, with source verification, transfer tests, NFT metadata inspection, and a receipt. The current pilot does not contain those test receipts.

## Required production upgrades

1. Approve brand, issuer, token rights, supply and economics; confirm ticker/name uniqueness.
2. Verify and explicitly approve beneficiary identities, release schedules and treasury governance; independently review the six pilot vaults, deploy/fund only after separate approval, and establish an externally verified owner-controlled multisignature governance wallet.
3. Implement unit, integration and adversarial tests for TRC-20/NFT/vaults on a local chain and Shasta; obtain independent audit.
4. Add on-chain event indexing, double-entry reward accounting, rate limits, anti-fraud, age/location controls and transparent user statements.
5. Decide where prizes are fully funded; do not require MOJ1/NFT staking for a chance to win real-world value. Keep Google rewarded-ad points separate from crypto.
6. Complete applicable legal analyses and white-paper/disclosure requirements by market before any public sale, custody, exchange listing or advertising of profit expectations.
7. Obtain separate explicit owner authorization for each irreversible Mainnet transaction.

## Primary documentation

- https://developers.tron.network/docs/issuing-trc20-tokens-tutorial
- https://developers.tron.network/docs/trc-721-token-issuance
- https://developers.tron.network/docs/token-standards-overview
- https://support.google.com/googleplay/android-developer/answer/13607354
