# MOJ1 V2 — immutable four-contract scope and dependency closure for independent auditor
**R-01 scientific/claim-quality workstream · 2026-10-30 · READY_FOR_REVIEW as an auditor intake artifact; independent security audit BLOCKED.**

## Scope anchored to real repository objects
Frozen public revision: [4411b28325be44c54d7917b4c67786348521b6a9](https://github.com/mojtabarozegar11-ship-it/Saeit/tree/4411b28325be44c54d7917b4c67786348521b6a9/experiments/moj1-pilot/contracts). The four target Solidity files were individually retrieved at this exact commit; the following are **Git blob SHA-1 identifiers**, not SHA-256 of source bytes or an independent security attestation.

| Audit target | Exact Git blob SHA-1 at frozen commit | Direct source-level dependency / critical review focus |
|---|---|---|
| `MojCoinGuarded.sol` | `bf13bb38a1898bb38dae168ab80af7d689466f0e` | Imports `@openzeppelin/tron-contracts/token/TRC20/TRC20.sol` and factory; 100-billion × 10^18 fixed mint to newly constructed distributor |
| `MojGenesisFactoryGuarded.sol` | `cd5e0eca4c06c75c5511a40f34513c5ae39749f9` | Imports `ITRC20`, `SafeTRC20`, `MojVestingVault`, `MojApprovalReserve`; six-beneficiary uniqueness, one-shot distribution, allocation sum, token escrow and TVM energy |
| `MojVestingVault.sol` | `10bb26738dc97d71975fb473ba69d6d1cca95b4a` | Imports `ITRC20`, `SafeTRC20`, `Math`; fully-funded release, cliff/duration arithmetic, beneficiary-only transfer and reentrancy assumptions |
| `MojApprovalReserve.sol` | `39d945d7aa27b3782315adea126aedd99b89165b` | Imports `ITRC20`, `SafeTRC20`; fixed beneficiary, tranche ceiling, scheduling/cancellation, 30-day delay and 90-day interval |

**Important scope boundary:** the frozen directory also contains other files such as `MojCoin.sol`, `MojGenesisDistributor.sol`, `MojAssets.sol` and `MojPilotGovernance.sol`. Their presence **does not make them audited**. A separate experimental Merkle reward-claims module is excluded unless the independent auditor expressly extends the scope. A four-file quote is insufficient if imported libraries and deployment/build inputs are silently excluded.

## Compiler/dependency evidence required before any audit signoff
1. Pin `solc 0.8.25` build settings, optimization, target TVM/TRON compiler toolchain and **exact package-lock / dependency tree** for `@openzeppelin/tron-contracts`; a Solidity import path alone does not identify immutable dependency bytes.
2. Independently calculate SHA-256 for all four source files **and** transitive imported library inputs. Match compiler metadata, constructor arguments and verified deployed bytecode where deployment is claimed. The Git blob IDs above are not substitutes.
3. Resolve and document the governance address and six beneficiary roles **privately**. No personal addresses, keys, customer records or unpublished deployment parameters belong in this public handoff.
4. Include a negative-test threat matrix for unauthorized distribution, duplicate beneficiaries, vault underfunding, vesting underflow, reserve double release, callback/reentrancy, and gas/energy failure of atomic six-vault construction.
5. Include explicit independent review of the historical **V1 F08 destination-impersonation issue**, and explain why guarded factory construction changes that threat. A source comment is not evidence of vulnerability remediation.
6. Require signed independent findings, exact commit/hash binding, severity and remediation retest. Internal static checks, testnet operation and a grant application are **not** an independent audit.

## Funding and release decision
Current source is **pre-Mainnet**. A grant application, an invitation to a call, a quote or a conditional token-denominated offer does **not** constitute funding, signed engagement, security certification or approval. No owner payment, deposit, contingent liability, contract, transfer or Mainnet launch is authorized by this packet. Any written sponsor proposal must be routed to F-01 and owner approval gates. R-01 has not changed any contract or initiated any engagement.

**Next F-01 adoption action:** use this exact frozen file inventory to request an independent written scope-confirmation and dependency-inclusion checklist through an already-authorized channel, without new financial commitments. The auditor must independently verify the package lock, bytecode and actual on-chain state.
