# Pilot validation receipt — Moj 1 revision 0.5, 2026-10-21

## Executed checks

1. `npm test` — **PASS**, 9 of 9 Node tests: allocation arithmetic, approvals and basic source guards, independent vesting arithmetic with 2,000 boundary probes, and tests that the deployment script refuses Mainnet and refuses missing test-wallet keys. They do **not** execute the smart contracts.
2. `node --check scripts/deploy-shasta.mjs` — **PASS**, script syntax.
3. `npm install --ignore-scripts --no-audit --no-fund` — **PASS**. Dependencies installed from npm; this is not a security audit.
4. `npm run compile` — **PASS**, `tronbox compile` with Solidity `0.8.25`, including the new `MojVestingVault.sol` on 21 October 2026.
6. `npm run preflight` — **PASS** (21 October 2026): offline review confirms compiled ABI constructors (1/1/6 args), required functions, Solidity compiler, bytecode presence and SHA-256 digests, no exposed mint/revoke/upgrade methods in ABI, and Shasta-only deployment guard. No wallet, blockchain RPC or real funds accessed.
5. User-provided artwork copied byte-for-byte to `assets/moj1-coin-reference.jpg` (SHA-256 `a0092ccbd7e4d7e51e2a44fe5193e2d7834d9b1c895b2cb06ace7c1a5361e8f0`). Source uses JPEG encoding even though its uploaded filename ended in `.png`; the checkerboard background is not actual transparency.

## Not yet validated / not performed

- No Shasta deployment, contract address, TRX funding, NFT mint, or token transfer.
- No executed local TVM behavioral, property-based, fuzzing, or re-entrancy tests. `tests/tronbox/vesting.integration.js` is written but cannot run without local TRE, which was not available in this environment.
- No independent security audit, on-chain source verification, deployed/funded vesting controls, or multisig. A draft non-revocable team vault has been compiled only.
- No public sale, offer, liquidity pool, exchange listing, launch, or applicable regulator approval.

**Hard stop:** This code must not be used for Mainnet until tokenomics is approved, allocation vaults are deployed/funded/tested, a multisig treasury is established, independent audit and behavioral tests pass, and legal gates are complete.
