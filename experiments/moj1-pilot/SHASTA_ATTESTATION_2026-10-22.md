# MOJ1 Shasta read-only security evidence — 2026-10-22

Status: **TESTNET TECHNICAL ATTESTATION PASS; MAINNET / SALES NO-GO**.

This is an automated, keyless verification of a four-contract Shasta pilot. It is not a professional third-party security audit, a token valuation, a legal clearance, or an authorization to launch.

## Exact source and CI receipts

- Repository branch: `moj1/shasta-pilot-20261021`
- Attested code commit: `cc2e7a06b2133380eff5d4173b916e7348748289`
- Offline tests: [GitHub Actions 39727409984](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39727409984) — **48/48 passing**; TronBox Solidity 0.8.25 preflight passed.
- Isolated disposable TVM: [GitHub Actions 39727410189](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39727410189) — **15/15 passing**, including actual local transaction recovery with exactly one broadcast and no retry.
- Shasta RPC read-only proof: [GitHub Actions 39727410259](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39727410259) — **PASS**; no signing keys used.

## Public Shasta contract identities

| Contract | Address |
|---|---|
| MOJ1 token | `TKg1oVb91qHzeLC74djmeeAnMMmb9PYJ6F` |
| NFT | `TM1V6UqsfcpySZWKYze3i5PKPdk9Cxh4N8` |
| Pilot 2-of-3 governor | `TPvMW5cSHKfCuttghjWqmUEScH33vaA1Yy` |
| Genesis escrow | `TDYGu1oTf9bhAU3S6qMZE7BRC3HDZJ6QVP` |

Token supply: `100000000000` whole units at 18 decimals. At the time of the proof, escrow held the entire supply and `distributed=false`.

## Bytecode identity results

The verifier recompiled public source and queried Shasta `getContractInfo` for runtime bytecode. It checked exact creation bytecode when provided by the chain, and compared every runtime byte outside separately validated immutable address slots.

| Contract | Attestation method | Immutable slots | Runtime SHA-256 |
|---|---|---:|---|
| `MojPilotGovernance` | CREATION AND EXACT RUNTIME MATCH | 0 | `66f9821dfad1aa46bf0a4e42c322fc1cf184f59299e98f3740fb8cb79271e68e` |
| `MojCoin` | CREATION AND RUNTIME MATCH WITH VERIFIED IMMUTABLE ADDRESS SLOTS | 1 | `866eccbb8193bce93b44a1ebc6fb16bf2547b5c6e909170482b7f69a89b99ba8` |
| `MojGenesisDistributor` | ATTESTED PARENT PLUS RUNTIME MATCH WITH VERIFIED IMMUTABLE ADDRESS SLOTS | 10 | `9024dffa1ab4130063e0c55f1fbfa227c96e9d1f243e83a45686821e70f6b95f` |
| `MojAssets` | CREATION AND EXACT RUNTIME MATCH | 0 | `c56eed7a739fc8460e141b23888a49d55bfb9134dae4c6e91ae393d01ff6e04e` |

**Factory-child qualification:** TRON's `getContractInfo` did not supply creation bytecode for the escrow created inside the token constructor. Instead, the verifier requires the exact-creation-attested `MojCoin` parent, compares the escrow's entire runtime code outside address-bound immutable slots, and checks token-to-escrow, governance, supply and undistributed state through read-only calls. It does **not** claim independent exact creation-code matching for that internally created child.

The runtime hashes are public evidence values, not cryptographic signatures from an external auditor. Tests reject altered opcodes, constructor bytecode mismatches, unknown immutable addresses, missing runtime artifacts and an unauthorized factory-child fallback.

## Scope exclusions and release gates

- No Mainnet transaction, token distribution, public sale, payment connection or real wallet use.
- MojPlayWin remains `READ_ONLY_STAGING`; no production checkout integration or buyer purchase proof was exercised here.
- Independent third-party source/security audit remains required, including contract logic, vesting, issuance economics, key custody and TVM-specific behavior.
- Production governance owners, recovery/backup, beneficiary addresses, release schedules, fee baseline, full payment workflow and applicable market-by-market legal requirements remain separate approvals.
- Do not publish a Mainnet contract, activate transferable rewards, exchange listing or public sale based only on these CI receipts.

## Next safe technical gate

Build an isolated MojPlayWin staging adapter that reads only public MOJ1 Shasta state; use synthetic orders and explicit feature flags, with all payment posting, distribution and real-money settlement disabled. Run E2E staging assertions and record reversible evidence before discussing production integration.
