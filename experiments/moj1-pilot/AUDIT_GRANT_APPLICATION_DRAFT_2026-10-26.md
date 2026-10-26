# MOJ1 V2 — Grant / sponsorship application data pack (not submitted)

**Prepared:** 2026-10-26  
**Authority:** internal preparation only; no external application, checkbox acceptance, payment, contract or fee authorization.  
**Release:** NO-GO (Mainnet, sales, exchange pools and token rewards).  
**Owner cash budget:** USD 0, including no contingent, deferred, or participation fee.

## Auditable project facts

| Field | Verified response |
| --- | --- |
| Project name | MOJ1 V2 |
| Chain / technology | **TRON (TVM)**; select **Other: TRON** where not offered |
| Language | Solidity **0.8.25**, deployed TRC-20 candidate |
| Stage | **Testnet** (guarded V2 on Shasta only) |
| Previous independent audit of this exact V2 scope | **No** (internal tests and prior private discussions do not qualify) |
| Project description | TRON/TRC-20 token candidate for a proposed future MojPlayWin ecosystem utility. A 100-billion-unit supply is held by a guarded testnet genesis escrow; six allocation buckets are provisional. No public sale, withdrawal, paid rewards or Mainnet launch has been authorized. |
| Frozen code target | `4411b28325be44c54d7917b4c67786348521b6a9` |
| Core in-repo first-party contracts | `experiments/moj1-pilot/contracts/MojCoinGuarded.sol`; `MojGenesisFactoryGuarded.sol` |
| Approx. source scope size | **75** nonblank, noncomment lines across those **two first-party Solidity files** (12 + 63; measured on the frozen commit). This excludes third-party imported contracts and any additional treasury, vesting, governance or integration scope. **Not a complete audit nSLOC estimate.** |
| GitHub repository | `https://github.com/mojtabarozegar11-ship-it/Saeit`; frozen commit above (access/permissions must be separately arranged when an auditor is engaged) |
| Contact | `mojtaba.rozegar11@gmail.com` (internal reference; transmitting this to a form requires specific approval if applicable) |
| V2 Shasta testnet token | `TA8dcG3b9GByaY9vZ1LVjsFohZrZ4CveAY` |
| V2 factory escrow | `TCBNLE1ZgEcAWXRZ6jjYPSyUH7WiHpLyBm` |
| Expected audit timeline | **Not sure yet**; only when independent funding and scope exist |
| Project website / X / Telegram | Leave optional fields empty unless authenticated project-specific channels are independently verified |

## Requested full review — do not underscope

1. Review exact full first-party and imported source, compiled bytecode, constructor arguments, deployment and owner privileges, integer accounting, minting/supply invariants, factory escrow and allocation releases.
2. Reproduce the **V1 HIGH F08 destination-impersonation bug**; verify V2's mitigation and all privilege/replay/front-running paths.
3. Map/quote **six beneficiaries/vaults, vesting, governance, reward, treasury and external integrations** separately; exclude these explicitly if not delivered.
4. Confirm TVM energy and `fee_limit` behavior under edge cases; verify actual deployed bytecode.
5. Provide an independent named, dated report with methodology, severity-ranked findings, precise commit and bytecode hashes and fix/retest attestations.

## Verified application channels & binding conditions

| Channel | What the primary source says | Safe present action |
| --- | --- | --- |
| TRON DAO — Builders League | Discretionary builder/ecosystem support may fund audits; program application has its own participation terms and no automatic award. | Continue non-binding direct-pay sponsor inquiries; **do not submit formal terms without owner-specific approval.** |
| Kann Audits — Audit Grants, Batch 1 until 2026-11-15 | **Free initial application**, but required form checkbox acknowledges approved projects pay a **$250 participation fee** and may be reviewed with supervised juniors/AI plus senior QA. | **Do not check/submit** under the present zero-fee mandate. Already requested fee waiver / direct sponsor funding by email. |
| Nethermind audit subsidy programs | Publicly lists up to 30% Ethereum or up to 100% Arbitrum support. | **Not applicable** to this **TRON-only** audit without chain change; do not imply eligibility. |
| Hacken Superchain audit grants | Applies to OP/Superchain projects; advertised grant window does not cover TRON. | **Not applicable** to current MOJ1 project. |

**No audit sponsorship or funds has been awarded.** This document is not an acceptance, offer or legal approval.

## Evidence package & safeguards

- GitHub issue: https://github.com/mojtabarozegar11-ship-it/Saeit/issues/853
- Auditor input: `moj1-v2-unsigned-auditor-input-39734674912` artifact **12406875421**, SHA-256 `280b7964221dd989707f8e5f788b821c5465f8a68167e2a99e9fa840c1aa9169`, public retention expiry **2026-11-05**; owner-private hash-verified archive reportedly preserved. **Do not upload or expose private contents without owner authorization.**
- Internal hardening: PR #1270 merged into isolated branch only. Tests 13/13, additional TVM governance run passed. Tests are **not** an independent audit.
- Mandatory controls: no payments, wallets or private keys; no seed words; no sponsor transaction; no Mainnet; no liquidity-pool activation; no public token sale or redemption representations.

## Missing facts before any actual grant form submission

- Confirmed **full-scope** nSLOC and dependency manifest, independently checked against frozen build.
- Target auditor names/quality, quote details and identified **third-party direct payer** willing to assume 100% of costs.
- Explicit owner approval of **the specific program terms** and permitted disclosures.
- Clear project-use description verified as technically deployed, not hypothetical, and legally reviewed before external marketing.

**Decision:** continue source preparation and non-binding funding conversations; require **zero total owner liability** before proceeding with grant/engagement.
