# MOJ1 C140 — nonbinding auditor/grant diligence sheet (R-01 rotation)
Date 2026-10-31 | Stage READY_FOR_REVIEW | No external communication, no agreement, no audit certification

## Scope baseline (owner-supplied, not independently recompiled here)
- Guarded contracts: `MojCoinGuarded`, `MojGenesisFactoryGuarded`, `MojVestingVault`, `MojApprovalReserve`.
- Exclusions: `MojCoin`, `MojAssets`, `MojGenesisDistributor`, `MojPilotGovernance`, tests and OpenZeppelin dependencies unless independently added by an authorized scope decision.
- Owner-referenced source commit: `4411b28325be44c54d7917b4c67786348521b6a9` (**not independently verified as deployed bytecode or an audited commit**).

## Ready-to-use evidence acceptance grid
| Due-diligence item | Acceptable evidence | Red flag / gate |
|---|---|---|
| Scope | Exact repo commit, compiler version, dependency lock, contract list, chain target | Marketing name or unverifiable branch-only snapshot |
| TVM compatibility | Auditor states supported TRON/TVM tooling and limitations in writing | EVM-only report represented as TVM assurance |
| Privileged roles | Documented owner/minter/pauser/vesting authority and upgradeability, no private keys | Unbounded roles or hidden upgrade authority |
| Test evidence | Reproducible test commands and signed or traceable results, identified environment | Test count called security proof |
| Audit | Named independent firm, written scope, final report and remediation status | Quote or preliminary review called completed audit |
| Grant | Official program rules, jurisdiction/eligibility, written award and lawful receipt | Prospect or meeting called awarded funds |
| Token economics | Verifiable on-chain records and legal compliance clearance | Guaranteed value, returns, exchange listing or liquidity claims |
| Payment/engagement | Separate owner approval and legal/compliance gate | Unrequested transfer, wallet signature or binding terms |

## Safe factual one-paragraph external summary — **draft, not sent**
“MOJ1 is a proposed token and guarded-contract project whose specified source and permissions require independent technical review. The project is seeking nonbinding information about audit scope, TVM compatibility, eligibility for support and estimated delivery terms. No completed audit, grant award, production deployment, commercial valuation or guaranteed security is claimed here. Any engagement or transaction requires separate owner and compliance approval.”

## Next F-owner decision
Obtain a dated, verifiable written response from an actual auditor/grant administrator; compare with this matrix. **Do not pay, sign, transfer tokens, deploy, or reactivate the factory.**
