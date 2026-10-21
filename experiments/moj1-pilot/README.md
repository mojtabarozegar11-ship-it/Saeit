# Moj 1 and Moj Digital Assets — pilot 0.5

**Current status:** draft testnet code. The owner approved the project name `Moj 1`, ticker `MOJ1`, and 100-billion-unit supply on 21 October 2026. Uniqueness, trademarks, issuer identity, allocation schedule and legal assessments remain open. No currency has been issued; no Mainnet contract or market has been launched. The artwork supplied by the owner is included as a reference image, not an on-chain identity claim.

## What is implemented

| Component | Scope | Limit |
|---|---|---|
| `contracts/MojCoin.sol` | TRC-20, 100 billion MOJ1 initial and maximum, 18 decimals, supply minted once to test treasury | No mint extension, freeze, taxes or upgrade admin |
| `contracts/MojAssets.sol` | TRC-721, 10,000 maximum unique items, restricted mint, per-item URI | Not a live NFT store; metadata hosting and rights are not built |
| `contracts/MojVestingVault.sol` | Non-revocable cliff and linear vesting for a **single funded allocation** | Draft team vault only; not yet deployed, funded or exercised on TVM |
| `tokenomics.json` | Six proposed allocation buckets and release schedules | Other buckets still lack enforceable on-chain locks |
| `tests/` | Nine passing allocation, vesting-model, deployment-refusal and source-guard tests; TronBox integration suite prepared | Model tests are **not** smart-contract behavior tests or an audit; TVM suite **not run** |
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

The provisional team allocation is **10 billion MOJ1** (10% of supply). `MojVestingVault` enforces a **365-day cliff followed by 1,095 days of linear vesting** if deployed with those parameters, rather than literal calendar-month calculations. Each vault requires a separately chosen immutable recipient, allocation and start time; the current script deploys the token and NFT, **not** a vault. After deploying a vault, the treasury must transfer the full allocated amount to its contract address before releases are enabled. No tokens have been locked or vested on a live chain.

The behavioral suite `tests/tronbox/vesting.integration.js` requires a running local TRON Virtual Machine runtime (TRE); run `npm run test:onchain:local` only when that runtime is configured. Local Docker/TRE was unavailable during pilot validation, so the suite was not executed. Do not mistake the nine passing Node tests or the offline preflight for on-chain validation.

For optional on-chain testing: only after tests and security review, the owner creates a **new, dedicated Shasta-only test wallet**, funds it with free test TRX, and controls its signing key privately. Never send private keys or seed phrases to a chat, repository or contractor.

```sh
export MOJ1_DEPLOY_CONFIRM=SHASTA_ONLY
export MOJ_SHASTA_TREASURY=YOUR_SHASTA_WALLET_ADDRESS
export TRON_PRIVATE_KEY=YOUR_TEST_ONLY_PRIVATE_KEY
npm run deploy:shasta
unset TRON_PRIVATE_KEY
```

The script points only at `api.shasta.trongrid.io`; it has no mainnet option. A successful deployment must then be verified on Shasta TRONSCAN, with source verification, transfer tests, NFT metadata inspection, and a receipt. The current pilot does not contain those test receipts.

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
