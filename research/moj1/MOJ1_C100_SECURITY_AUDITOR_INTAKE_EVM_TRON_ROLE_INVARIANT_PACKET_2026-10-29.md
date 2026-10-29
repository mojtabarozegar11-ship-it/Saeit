# MOJ1 independent audit — chain-specific role/invariant intake packet
**Owner:** F-01 (MOJ1/commerce) | **Prepared by:** R-01 | **Date:** 2026-10-29 | **State:** READY_FOR_REVIEW as a reusable auditor-intake artifact; no actual contract audit, grant application, deployment or token certification.

## Decision boundary
Do **not** assume MOJ1 is an EVM ERC-20, a TRON TRC-20, both, or already deployed. OWASP's [SCSVS](https://scs.owasp.org/SCSVS/) chiefly targets Solidity/EVM; it is a control-selection reference, **not a certificate** and not a substitute for TRON-specific execution/permission validation. [OpenZeppelin's role documentation](https://docs.openzeppelin.com/contracts/5.x/access-control) explains the transitive risk of `DEFAULT_ADMIN_ROLE`; it does **not** prove MOJ1 uses OpenZeppelin or this role.

## Reviewer intake — fill privately from the exact source, never invent
| Gate | Minimum independently reproducible evidence | Release failure condition |
|---|---|---|
| CHAIN | Actual chain/network, token interface and address *only if deployed*, explorer link, immutable source hash | Chain unspecified or mixed EVM/TRON assumptions |
| BUILD | Commit hash, complete dependencies, compiler/optimizer flags, deterministic bytecode and build transcript | Rebuild differs or privileged dependencies unknown |
| AUTH | Every external/public mutating function, role/owner/admin and indirect grant/revoke path, upgrade authority | Unenumerated privilege or unverified upgrade mechanism |
| SUPPLY | Initial supply, decimals, cap, mint/burn paths, totalSupply accounting, holder balances, fee/freeze logic | Unproved invariants, unrestricted privileged mint not disclosed |
| TRANSFER | Transfer/transferFrom, allowance race, pause/blacklist semantics if present; event accounting | Privilege bypass or event/balance inconsistency |
| UPGRADE | Proxy implementation/admin slots and initialization/reinitialization permissions *if applicable* | Implementation takeover or unreviewed storage-layout change |
| TEST | Exact-head unit, property/fuzz and adversarial authorization tests; all findings tied to revisions | Tests are synthetic-only or stale against current head |
| DISCLOSE | Open issues, audit scope/exclusions, grant conditions, owner signoff and reviewer independence | Claimed external approval without signed independent report |

## Test specifications to hand to an independent auditor
1. For each sensitive function, an unauthorized actor must fail; enumerate all legitimate privilege escalation routes, including role-admin self-administration where applicable.
2. For each mint/burn/transfer path, compare before/after totalSupply and aggregate balances under random sequences and boundary values; state fee/rebase exceptions explicitly.
3. Exercise repeated initialization, upgrade authority and rollback **only if** such architecture exists; otherwise record NOT_APPLICABLE with source locator.
4. Compare deployed runtime bytecode with the pinned build **only if deployed**; an unverified address is not a verified production deployment.
5. Separate a reproducible technical test report from independent security-audit conclusions and from legal/financial grant eligibility.

## Handoff to F-01
F-01 may privately populate CHAIN/BUILD/AUTH/SUPPLY from an authorized exact-head source and deliver sanitized non-secret findings to an auditor. **No contract keys, wallet seeds, customer data or private deployment secrets in GitHub.** No repeat Guardian/InterFi outreach or fee acceptance. Until the source, roles and independent auditor are established, every audit/grant/launch claim remains **BLOCKED**.
