# MOJ1 V2 | Frozen build inputs for an independent TRON/TVM auditor
F-01 independent intake supplement · 2026-10-30 · FILE DELIVERED / SECURITY AUDIT NOT DONE

**Frozen commit:** `4411b28325be44c54d7917b4c67786348521b6a9`.
Read-only verification of repository objects; **no contract changes, no compilation claim, no deployment, no sponsor commitment**.

| Immutable input | Git blob SHA-1 at frozen commit | Observed build pin |
|---|---|---|
| `experiments/moj1-pilot/package.json` | `23d868954682c3477c3e88b8e1544fcc7b321264` | `@openzeppelin/tron-contracts=5.6.0`; `tronweb=6.5.0`; `tronbox=4.10.0` |
| `experiments/moj1-pilot/package-lock.json` | `e3bbabefa703ca7bde281238397d4cc016320c0f` | lockfileVersion 3; locked `@openzeppelin/tron-contracts=5.6.0` |
| `experiments/moj1-pilot/tronbox-config.js` | `fe3b5ca9bd4b1477ad1c513baf3396724284537c` | `solc=0.8.25`, optimizer enabled, 200 runs, local development host `127.0.0.1:9090` |
| `MojCoinGuarded.sol` | `bf13bb38a1898bb38dae168ab80af7d689466f0e` | fixed pragma 0.8.25 |
| `MojGenesisFactoryGuarded.sol` | `cd5e0eca4c06c75c5511a40f34513c5ae39749f9` | factory + vault/reserve dependencies |
| `MojVestingVault.sol` | `10bb26738dc97d71975fb473ba69d6d1cca95b4a` | imported TRC20/SafeTRC20/Math |
| `MojApprovalReserve.sol` | `39d945d7aa27b3782315adea126aedd99b89165b` | imported TRC20/SafeTRC20 |

The lockfile's `node_modules/@openzeppelin/tron-contracts` entry records integrity
`sha512-hkgVIsvxn1qJDlg5spxRH9YYSupgk4EW9axTLu+xHjrJyVgnQ8GMztmn/lHVQYLiSFeJ7t8Mmvp1lCDUg9adsQ==`.
This is **registry tarball metadata only**; package bytes and transitive imports have **not** been independently downloaded, hashed or compared in this run. Git blob SHA-1 values are not source SHA-256 or independent audit evidence.

## Safe reproducibility acceptance contract
1. Check out the exact frozen commit in an isolated environment and independently hash all four sources plus transitive imports with SHA-256.
2. Use `npm ci --ignore-scripts` only in a trusted isolated environment with network policy and dependency verification; do not install or run dependencies on production VPS.
3. Independently reproduce `solc 0.8.25` and optimizer settings, record compiler binary digest and build artifacts; compare metadata and deployment parameters only where independently documented.
4. Perform human TRON/TVM review including the historic V1 destination-impersonation issue, atomic factory gas/energy, vesting, reserve, governance, access control and reentrancy.
5. Independent signed findings and legal/security approval remain mandatory before any Mainnet or funding claim. No keys, addresses, customer data or private quotes in this public artifact.

**Next F-01 action:** obtain verified independent auditor written scope acceptance, zero owner cost/obligation, and separately reproduce the locked dependency bytes. This handoff is not an audit report.
