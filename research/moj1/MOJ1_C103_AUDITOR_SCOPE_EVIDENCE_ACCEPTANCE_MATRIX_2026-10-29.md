# MOJ1 — independent audit evidence acceptance matrix (R-01 C103)
**Date:** 2026-10-29. **Status:** usable auditor-intake template; NO external audit, grant, token approval, financial transaction, or mainnet authorization. **Owner:** F-01 for adoption. **R-01** scientific/evidence reviewer only.

## Pre-audit identity and reproducibility gates
The auditor should receive **only after secure private exchange**: (1) the exact in-scope source commit SHA and chain/compiler/runtime versions; (2) the frozen, reproducible build instructions and artifact SHA-256; (3) the precise EVM and/or TRON contract list and proxy/implementation relations, if any; (4) role/upgrade/mint/burn/pause policy and threat model; (5) independently executable tests and deploy simulation; (6) documented deviations and unresolved known issues. Never publish private keys, credentials, production wallets, customers, unpublished commercial terms, or exploit details in this public repository. The publicly recorded result is only a non-sensitive artifact ID, reviewer identity validation status, acceptance stage and next action.

| Audit question | Evidence required from auditor | Minimum acceptance | Hold condition |
|---|---|---|---|
| Exact binary/source identity | Verified commit, compiler flags, dependency locks, bytecode correspondence | Reproducible result with file hashes | Source mismatch or unverified proxy target |
| Privileged operations | Role graph and authorization test evidence | Every mint, burn, pause, blacklist, fee and upgrade path enumerated and tested where implemented | Unreviewed admin path |
| Token accounting | Supply/balance invariants and adversarial transfer scenarios | Conservation and authorization invariants demonstrated against exact build | Unexplained supply delta |
| EVM / TRON differences | Per-chain deployment and execution evidence; decimals, fees, energy/resource limits | Explicit separate chain scope and reproducible chain-specific tests | Treating an EVM-only result as TRON coverage |
| Upgrade / governance | Timelock/multisig/implementation-owner documentation if applicable | Upgrade and emergency procedures reviewed; privileged key custody privately verified | Unverified unilateral upgrade authority |
| Findings and remediation | Signed report or independently verifiable auditor deliverable with severity, reproduction, fix and retest | Critical/high findings remediated and independently retested; residual risk disclosed | Self-declared certification, unsupported clean bill |
| Sponsorship / grant | Authenticated sponsor identity and written non-binding scope before negotiation | No commitments without separate owner approval | Payment request, wallet transfer, NDA/contract or grant guarantee |

## Evidence ledger for actual auditor to fill (no prefilled PASS)
| Finding ID | Contract + commit (private reference) | Chain | Severity | Reproduction reference | Fix commit | Independent retest | Remaining risk | Status |
|---|---|---|---|---|---|---|---|---|
| AUD-001 | pending | pending | unassessed | pending | pending | pending | unassessed | BLOCKED |

**Next handoff to F-01:** attach this public checklist to the already frozen **private** auditor input package, verify external reviewer identity through independent official channels, request non-binding availability/scope; do not send confidential package or enter a contract until approved. Existing [R-01 checkpoint issue #1514](https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1514) is the coordination point. This is a QA intake artifact, **not an audit certificate**.
