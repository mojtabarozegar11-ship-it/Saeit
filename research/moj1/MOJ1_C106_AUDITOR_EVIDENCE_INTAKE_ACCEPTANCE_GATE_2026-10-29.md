# MOJ1 — independent security-audit evidence intake (R-01; 2026-10-29)
**Status:** READY_FOR_REVIEW as an evidence intake instrument; **NOT** an audit, certificate, legal approval, grant award, deployment, token issuance, or security assurance.

## Intended use
Give a prospective independent auditor a **redacted inventory** before any scope/price/contract discussion. Keep addresses, unreleased code, wallet keys, customer data, personal contact information and provider correspondence out of the public tracker. The project owner and F-01 supply approved confidential items directly to an auditor over an authorized private channel. This file is not evidence that they have been supplied.

| Evidence ID | Required verification | Acceptable evidence | Fail-closed decision |
|---|---|---|---|
| MOJ1-A01 | Target chain(s) and exact network identifiers | Chain ID / TRON network identifier with dated owner attestation | No chain-specific scope until verified |
| MOJ1-A02 | Source revision identity | Immutable commit SHA and SHA-256 of each compiler input | No reproducible audit target without hashes |
| MOJ1-A03 | Deployed bytecode equivalence, if any | Explorer-verified bytecode, compiler metadata and reproducible build | Do not claim deployed contract or source equivalence |
| MOJ1-A04 | Privileged roles and upgrade powers | Role graph, mint/burn/pausing/blacklist/ownership paths and authorized key custody evidence | No claims of decentralization or renounced authority |
| MOJ1-A05 | Token economics and cap invariants | Supply/decimals/allocation spec and source-level invariant tests for each chain | No supply/price or collateral claim |
| MOJ1-A06 | Cross-chain bridge, if any | Explicit bridge design, custody/escrow/mint-burn mapping, replay protections | No cross-chain interoperability claim |
| MOJ1-A07 | External dependency inventory | Oracle, multisig, proxy, router, timelock, chain RPC, external call matrix | No assumption that third parties are safe |
| MOJ1-A08 | Threat model | Assets, attacker capabilities, admin compromise, replay/reentrancy, chain reorg and DoS scenarios | Scope incomplete until covered |
| MOJ1-A09 | Test/review evidence | Deterministic test logs, fuzz properties, tool versions, reproducible environment | Internal tests are not independent audit |
| MOJ1-A10 | Independent auditor provenance | Legal identity, signed scope, immutable report URL and explicit limitations | No public claim of independent certification absent final signed report |

## Auditor response acceptance gate
Record **date, organization, independently verified domain, scope version, whether the review is free/conditional, deliverables, independence conflicts and explicit no-obligation status**. Do not infer a grant from an invitation to a call. A grant or audit remains **BLOCKED** until a real independent decision/report is documented.

## Immediate handoff to F-01
F-01 may populate only approved, non-secret identifiers in a private inventory. The research owner R-01 can review claim wording; only F-01 may adopt code changes or make contractual requests. Do not publish a token, spend funds, or represent an internal checklist as an independent security audit.
