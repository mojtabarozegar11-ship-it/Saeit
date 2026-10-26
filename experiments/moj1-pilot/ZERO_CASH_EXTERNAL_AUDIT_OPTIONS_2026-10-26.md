# MOJ1 V2 — external independent-audit financing options
**Evidence date:** 2026-10-26  
**Binding decision:** no owner cash outflow; no debt, indemnity, subscription, deferred bill, token consideration, exclusivity, transfer, or Mainnet activity. **This is research; no funding is awarded and no auditor is retained.**

## What we verified from first-party sources

| Rank | Path | Public evidence | MOJ1 fit | Owner cost / contractual issue | Verified execution status |
| --- | --- | --- | --- | --- | --- |
| **1** | **Guardian Security Fund (direct independent auditor)** | https://www.guardian.security/grants/ | **Plausible**: fund has active applications and advertises full Guardian two-team/invariant audits; **TRON support not proven** | Fund page calls this *audit grant coverage*, but does not unambiguously promise zero copayment or a liability-free engagement. Terms at https://www.guardian.security/terms/ say a separate signed engagement may govern. **Obtain written 100% cover, zero liability, exact scope first.** | **Nonbinding detailed eligibility email actually sent 2026-10-26 to site's verified audits@guardianaudits.com**. No acceptance or reply is asserted. |
| **2** | **Callisto / EthereumCommonwealth public free queue** | https://github.com/EthereumCommonwealth/Auditing | **Conditional**: issue template explicitly lists TRX; first audit may be free but review is discretionary; network not on priority list | No free-service fee if accepted as such; **paid plans exist and paid re-audit is explicitly required for updates**. Standard disclosure requires publication within 15 days of review completion for serious issues; repository has a sparse recent issue queue with no demonstrated response. | Draft request prepared for free queue; **external GitHub create-issue attempt failed with 403 Resource not accessible by integration; NOTHING submitted**. Do not bypass the permission failure. |
| **3** | **TRON DAO direct sponsor, outside TBL** | https://trondao.org/tron-builders-league | Most directly aligned with TRON, potential audit funding | The formal **TBL** terms, by applying, entail §6.2 entrant indemnity and §6.4 Hong Kong arbitration; **binding application refused**. Only separate sponsor-to-auditor route without these terms is permissible. | Official support@trondao.org contacted 24 and 26 Oct already; wait for response without another repetitive email. |
| **4** | **Zealynx future fully covered Core grant** | https://grants.zealynx.io/grants/season-2 | **Unconfirmed** for TRON/TVM; standard public supported list stresses EVM, Solana, StarkNet, Fuel | Season 2 closed 4 Oct; **one** competitive Core award was 100% subsidized, most other tiers 25–50%; no active Season 3 acceptance verified. | Watch for an objectively announced new batch; do not pay for any discounted tier or represent closed season as open. |
| **5** | **Kann Audits grant** | https://kannaudits.com/audit-grants | Other chains and Solidity may apply; TRON final eligibility unconfirmed | Free to apply but required checkbox acknowledges **$250 upon approval** plus supervised junior reviewers. Violates zero-owner-fee requirement unless a named sponsor directly pays in full and the obligations are amended in writing. | Fee waiver/sponsor inquiry sent previously; **form not submitted**. |
| **6** | **Nethermind/Arbitrum, Hacken/Superchain, Uniswap/Ethereum programs** | https://www.nethermind.io/audit-subsidy-programs ; https://blog.arbitrum.foundation/introducing-the-arbitrum-security-program-apply-to-secure-your-smart-contracts/ | **Not eligible as a TRON-only candidate on the published chain criteria** | Cross-chain redevelopment, migration or new obligations are out of scope and would undermine frozen TRON review target. | **Rejected as current financing routes**; no application. |

## Stop / GO criteria for any external auditor

An auditor **may be evaluated** only after written confirmation of all below:
1. **Fee:** USD 0 owed by owner, now or later; no deposit, co-payment, deferred invoice, referral obligation or token allocation. A named sponsor pays the auditor directly, or the auditor explicitly offers unconditional pro bono.
2. **Terms:** no owner indemnification/guarantees or automatic obligation from submitting an initial enquiry; scope and all material terms disclosed **before** owner engagement acceptance.
3. **Expertise:** demonstrable TRON TVM + Solidity work, TVM energy and `fee_limit` understanding, named reviewers, conflict disclosure.
4. **Scope:** exact frozen source commit `4411b28325be44c54d7917b4c67786348521b6a9`, associated dependencies, six allocation paths, governance, escrow, V1 F08 reproduction, V2 mitigation and actual bytecode.
5. **Deliverable:** independent signed dated severity-rated report, precise scope/exclusions, source/bytecode identifiers and fix re-test as agreed.
6. **Publication:** written responsible-disclosure process permitting safe remediation; no confidential evidence released without owner review.
7. **Separate release gates:** independent legal/custody signoff and owner-specific approval before Mainnet, sale, rewards, exchange liquidity or checkout integration.

## Why minting a second token is not a cashability solution

SUN.io's [primary liquidity guide](https://docs.sun.io/liquidity/how-to-create-liquidity/) requires **both assets** (e.g., MOJ1 and TRX/USDT) to be deposited for a fresh pool; the ratio initializes price but **does not evidence real demand or create freely redeemable market value**. There is no sponsor-funded quote-asset pool, security clearance, legal approval or verified external buyers here. A new token would multiply, not remove, these barriers. Remain on MOJ1 V2 Shasta with NO-GO release.

## Immediate evidence status
- Owner question resolved: independent audit financing and token cashability are **different gates**; both unsatisfied.
- Working code/evidence: [internal hardening branch](https://github.com/mojtabarozegar11-ship-it/Saeit/tree/moj1/internal-hardening-20261024); [grant data pack](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/moj1/internal-hardening-20261024/experiments/moj1-pilot/AUDIT_GRANT_APPLICATION_DRAFT_2026-10-26.md).
- External release issue: https://github.com/mojtabarozegar11-ship-it/Saeit/issues/853
- No financial quote accepted, no transaction sent, no independent signed audit received.