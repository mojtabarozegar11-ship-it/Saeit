# Moj 1 and Moj Digital Assets — pilot 0.7 (F02 escrow prototype)

**Current status:** draft testnet code. The owner approved the project name `Moj 1`, ticker `MOJ1`, and 100-billion-unit supply on 21 October 2026. Uniqueness, trademarks, issuer identity, allocation schedule and legal assessments remain open. No currency has been issued; no Mainnet contract or market has been launched. The artwork supplied by the owner is included as a reference image, not an on-chain identity claim.

## What is implemented

| Component | Scope | Limit |
|---|---|---|
| `contracts/MojCoin.sol` | TRC-20, 100 billion MOJ1 initial and maximum, 18 decimals, supply minted into a newly created genesis escrow contract, not to an external wallet | No mint extension, freeze, taxes or upgrade admin |
| `contracts/MojAssets.sol` | TRC-721, 10,000 maximum unique items, restricted mint, per-item URI | Not a live NFT store; metadata hosting and rights are not built |
| `contracts/MojVestingVault.sol` | Non-revocable cliff and linear vesting for a **single funded allocation** | Locally deployed/funded/tested on TVM only; no Shasta/Mainnet vault or lock |
| `contracts/MojGenesisDistributor.sol` | Initial escrow validates six distinct bucket vaults and atomically funds all 100bn units once | Percentages remain provisional and governance/beneficiaries are not approved |\n| `contracts/MojApprovalReserve.sol` | Two governed liquidity/contingency reserve vaults with a 30-day release delay | Real multisig control and off-chain approvals still outstanding |\n| `tokenomics.json` | Six provisional allocations cross-checked with on-chain constants | No owner approval of allocation or recipients yet |
| `tests/` | Ten local offline tests; expanded F02 contract-level TVM tests pending CI | No Shasta or Mainnet transactions; no independent auditor attestation |
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

The F02 pilot now mints the entire fixed 100-billion-unit supply directly into an immutable genesis escrow, not a treasury wallet. A single atomic transaction can fund six independently deployed, precisely validated vaults: player rewards 35% (1,825-day linear vesting), development 20% (1,460 days), liquidity reserve 15% (governance approval plus 30-day delay), team 10% (365-day cliff followed by 1,095-day linear vesting), partners 15% (1,460 days), contingency reserve 5% (governance approval plus 30-day delay). The distributor verifies the fully funded escrow, future vesting start, immutable vault policy, distinct destinations and full supply conservation; there is no unilateral withdrawal or second distribution. **This is a provisional design, not an owner-approved allocation, security audit, live lock or distribution.** The six real beneficiaries and externally audited multisig controller remain unselected.

The behavioral suite `tests/tronbox/vesting.integration.js` runs on disposable local TRE in GitHub Actions (five passing as of 2026-10-21): [TVM receipt](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39607596859). The new F02 TVM suite has not yet been independently verified; older TVM results apply only to older contract versions. The production VPS lacks Docker/Podman/Node, so TRE was not installed there. These tests are **not** Shasta/Mainnet deployments or an independent security audit. See [security review and release blockers](SECURITY_REVIEW_2026-10-21.md), including high-severity runtime dependency advisories.

For optional on-chain testing: only after tests and security review, the owner creates a **new, dedicated Shasta-only test wallet**, funds it with free test TRX, and controls its signing key privately. Never send private keys or seed phrases to a chat, repository or contractor.

```sh
export MOJ1_DEPLOY_CONFIRM=SHASTA_ONLY
export MOJ_SHASTA_GOVERNANCE=YOUR_VERIFIED_SHASTA_MULTISIG_CONTRACT_ADDRESS
export TRON_PRIVATE_KEY=YOUR_TEST_ONLY_PRIVATE_KEY
npm run deploy:shasta
unset TRON_PRIVATE_KEY
```

The script points only at `api.shasta.trongrid.io`; it has no mainnet option and requires a previously deployed Shasta governance contract, which must separately be verified as an approved multisig. It does not distribute the escrow. A successful deployment must then be verified on Shasta TRONSCAN, with source verification, transfer tests, NFT metadata inspection, and a receipt. The current pilot does not contain those test receipts.

## Required production upgrades

1. Approve brand, issuer, token rights, supply and economics; confirm ticker/name uniqueness.
2. Independently audit and deploy the draft team vault, plus additional on-chain mechanisms for reward allocations, development, partnerships, reserves and liquidity-lock commitments; use owner-controlled multisignature treasury.
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
