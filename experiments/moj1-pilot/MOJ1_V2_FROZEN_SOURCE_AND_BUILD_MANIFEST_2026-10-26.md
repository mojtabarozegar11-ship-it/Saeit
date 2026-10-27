# MOJ1 V2 — frozen source and build manifest

**Review target:** `4411b28325be44c54d7917b4c67786348521b6a9`  
**Prepared:** 2026-10-26  
**Purpose:** handoff context for an independent auditor; not a certification.  
**Network status:** Shasta testnet records exist; do not infer Mainnet deployment or production readiness.

## Project-authored Solidity scope

These four source units comprise the guarded V2 first-party contract set at the review target. The factory imports and creates two of the other project-authored contracts, so a two-file intake would omit executable parts of the system.

| File | Git blob SHA | Nonblank, noncomment, non-import lines |
|---|---|---:|
| `contracts/MojCoinGuarded.sol` | `bf13bb38a1898bb38dae168ab80af7d689466f0e` | 10 |
| `contracts/MojGenesisFactoryGuarded.sol` | `cd5e0eca4c06c75c5511a40f34513c5ae39749f9` | 59 |
| `contracts/MojVestingVault.sol` | `10bb26738dc97d71975fb473ba69d6d1cca95b4a` | 53 |
| `contracts/MojApprovalReserve.sol` | `39d945d7aa27b3782315adea126aedd99b89165b` | 83 |
| **Total, first-party V2 source only** |  | **205** |

The total excludes imports, OpenZeppelin package sources, compiler-generated code, and any unlisted or future reward/governance modules. It is a reproducible source-line count under the stated rule, **not** a complete audit nSLOC or price estimate. The auditor must establish final in-scope files, count all dependencies consistently, and sign off on the scope before quoting.

### Import and construction graph

- `MojCoinGuarded.sol` imports OpenZeppelin TRC20 and creates `MojGenesisFactoryGuarded`.
- `MojGenesisFactoryGuarded.sol` imports OpenZeppelin ITRC20/SafeTRC20 and creates `MojVestingVault` or `MojApprovalReserve` for six buckets.
- `MojVestingVault.sol` imports ITRC20, SafeTRC20, and Math.mulDiv.
- `MojApprovalReserve.sol` imports ITRC20 and SafeTRC20.
- OpenZeppelin dependencies are pinned in the project manifest to `@openzeppelin/tron-contracts 5.6.0`; relevant imported source paths include TRC20, ITRC20, SafeTRC20, and Math.

## Reproducible build inputs

| Input | Value |
|---|---|
| Solidity pragma | `0.8.25` in all four project-authored contracts |
| Compiler config | `tronbox-config.js` |
| Optimizer | enabled, 200 runs |
| OpenZeppelin TRON contracts | `5.6.0` |
| TronWeb | `6.5.0` |
| TronBox | `4.10.0` |
| Dependency lock | `package-lock.json`, lockfileVersion 3 |
| Package manifest Git blob SHA | `23d868954682c3477c3e88b8e1544fcc7b321264` |
| Compiler-config Git blob SHA | `fe3b5ca9bd4b1477ad1c513baf3396724284537c` |
| Lockfile Git blob SHA | `e3bbabefa703ca7bde281238397d4cc016320c0f` |

These are repository-pinned inputs. A production audit must independently rebuild from the frozen source and verify artifact hashes; these pins alone do not establish that an on-chain address matches this build.

## Reconciliation required before audit sign-off

The repository source comments and status records require explicit reconciliation:

- `MojCoinGuarded.sol` is labelled “LOCAL TVM ONLY”.
- `MojGenesisFactoryGuarded.sol` says “NOT DEPLOYED”.
- The MOJ1 security gate records V2 Shasta token/factory addresses and a later public Shasta attestation.

The reviewer must independently map the exact reviewed build to each Shasta address using build artifacts, creation inputs, transaction receipts, and on-chain bytecode. If the source comments are stale, record that as documentation drift and fix it in a new source revision only after preserving this immutable baseline. No source edit is made here.

## Scope exclusions unless separately added and provided

- V1 contract(s), except the relevant F08 exploit reproduction and comparison evidence.
- NFT contracts and metadata.
- Future reward, Merkle-claim, or game integration contracts.
- Any production multisig bytecode or key custody system not supplied and mapped.
- External services and off-chain bookkeeping.

The audit report must name every exclusion and avoid describing a partial review as a complete MOJ1 ecosystem audit.
