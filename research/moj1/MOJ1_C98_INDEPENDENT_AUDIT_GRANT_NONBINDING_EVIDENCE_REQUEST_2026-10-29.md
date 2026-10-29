# MOJ1 — independent audit/grant evidence request and acceptance gate
**Owner of MOJ1 and external contacts:** F-01. **R-01 scientific/evidence handoff only.** 2026-10-29. No application, audit, grant, license, payment, token transfer or contract is claimed.

## Purpose
Provide an auditable, nonbinding technical scope for independent reviewers and potential audit-grant providers. This is an **internal request template** for F-01, not a sent message, authorization, a contract, a verified deployment or a security certification. It must not include wallet seeds, API tokens, user PII or private credentials.

## Evidence that F-01 must collect privately before auditor handoff
| ID | Required non-secret artifact | Pass condition | Current R-01 evidence |
|---|---|---|---|
| M01 | Exact source revision and repository visibility, compiler version/settings, reproducible build and verified contract address **if actually deployed** | Bytecode provenance can be reproduced independently; testnet and mainnet clearly distinguished | NOT PROVIDED |
| M02 | Token standard and chain (TRON TRC20 vs EVM ERC20), proxy/upgrade architecture, owner/admin/minter/burner/pauser/blacklist roles | Privilege graph is complete; hidden or inherited privileges examined | NOT VERIFIED |
| M03 | Supply invariants, decimals, initial allocations, mint/burn caps, allowances, transfer-fee or freeze logic, treasury controls | Invariants expressed as tests and checked against exact revision | NOT VERIFIED |
| M04 | Unit/integration tests, fuzz/property tests, static analysis, compiler warnings, known issues and remediation log | Reproducible results tied to the exact source hash | NOT VERIFIED |
| M05 | Threat model for governance keys, upgrade authorization, multisig/timelock if present, bridge/oracle dependencies, token-sale assumptions | Auditor can inspect all trust boundaries; missing dependencies declared | NOT VERIFIED |
| M06 | Previous independent reviews, bug bounty disclosures and outstanding critical findings **if any** | Each finding linked to a remediation commit and independent retest | NOT VERIFIED |
| M07 | Audit grant terms, scope, independence, deliverables, public disclosure rules, conflicts and payment requirements | Owner separately approves any binding terms, costs or publication | NOT REQUESTED HERE |

## Nonbinding technical inquiry (F-01 may adapt and send after identity/recipient verification)
> We are seeking an independent security audit or an audit-grant assessment for the MOJ1 smart-contract project. Please provide your eligibility criteria, supported chain/standard, expected scope, evidence checklist, auditor independence policy, reporting format, remediation/retest provisions, timeline, disclosure policy and any financial or contractual conditions. We are **not** placing an order, agreeing to a fee, claiming grant eligibility, or authorizing a public launch by this inquiry. We can provide a sanitized source revision and reproducible build details through an agreed secure channel once the audit scope is established.

## Safety and delivery conditions
- No assertions of deployed token, completed audit, zero vulnerabilities, grant approval, license or revenue until independently documented.
- A passing synthetic test or internal review is not a third-party audit.
- Do not publish private signing keys, confidential contract addresses, KYC or customer details in the public R branch.
- Any external correspondence is F-01's responsibility; avoid duplicate outreach where existing Guardian/InterFi contacts are awaiting replies.
- Acceptance for an actual independent audit: named auditor and scope, exact code hash, signed report with findings, remediation verification, explicit publication authorization. Funding approval is separate.

**Status:** Standalone nonbinding audit-scoping artifact READY_FOR_REVIEW for F-01. Audit, grant and launch **BLOCKED** until independent evidence and required approvals. **Next:** F-01 reconciles M01–M07 against private contract repository and existing correspondence, then requests only missing audit-grant conditions.
