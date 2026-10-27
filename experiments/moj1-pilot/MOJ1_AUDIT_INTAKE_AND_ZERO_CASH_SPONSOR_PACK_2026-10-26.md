# MOJ1 V2 — Independent Audit Intake & Zero-Cash Sponsor Pack

**Prepared:** 2026-10-27  
**Branch:** `moj1/audit-intake-ready-20261026`  
**Purpose:** audit readiness and non-binding funding discussions only  
**Owner cash / contingent liability:** USD 0  
**Release decision:** NO-GO for Mainnet, public sale, DEX liquidity, withdrawals, real rewards, and live checkout integration.

This pack is a factual intake package. It is **not** an application, engagement letter, offer, acceptance, investment solicitation, or permission to disclose private evidence. It does not certify MOJ1 as secure.

## 1. Verified project snapshot

- Project: MOJ1 V2, a TRON / TVM Solidity token candidate.
- Proposed total supply: 100,000,000,000 MOJ1; six allocation buckets remain provisional and are not cash, sale proceeds, or redeemable value.
- Frozen V2 source: [commit 4411b28325be44c54d7917b4c67786348521b6a9](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/4411b28325be44c54d7917b4c67786348521b6a9).
- First-party contracts: [MojCoinGuarded.sol](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/4411b28325be44c54d7917b4c67786348521b6a9/experiments/moj1-pilot/contracts/MojCoinGuarded.sol) and [MojGenesisFactoryGuarded.sol](https://github.com/mojtabarozegar11-ship-it/Saeit/blob/4411b28325be44c54d7917b4c67786348521b6a9/experiments/moj1-pilot/contracts/MojGenesisFactoryGuarded.sol).
- Current chain deployment is **Shasta testnet only**: token `TA8dcG3b9GByaY9vZ1LVjsFohZrZ4CveAY`; factory/escrow `TCBNLE1ZgEcAWXRZ6jjYPSyUH7WiHpLyBm`.
- Shasta read-only verification: [workflow run 39738660931](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39738660931). It proves only the recorded testnet facts, not an external security audit or production custody.
- V1 has a reproduced **HIGH** destination-impersonation issue (F08). V1 must not distribute.
- Internal behavior and regression checks are recorded in [MOJ1 security gate #853](https://github.com/mojtabarozegar11-ship-it/Saeit/issues/853) and [reward-claim review #1055](https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1055). Internal checks are not independent assurance.
- Auditor packet: GitHub Actions artifact 12406875421, archive SHA-256 `280b7964221dd989707f8e5f788b821c5465f8a68167e2a99e9fa840c1aa9169`. Actions retention expires 2026-11-05; issue #853 records that a hash-verified private archive was preserved. Do not attach or publish the archive until an auditor's identity, secure handling, scope, and terms are checked.

## 2. Required independent audit scope

The quote and final report must list each included and excluded artifact. At minimum, request review of:

1. The exact frozen V2 source, compiler/build settings, constructor arguments, deployed bytecode, and source-to-bytecode correspondence.
2. Token supply, minting/privilege boundaries, transfers, re-entrancy/external calls, integer behavior, and all state transitions.
3. Genesis factory, escrow, allocation release, and the six vault/vesting paths, including factory-created instances and immutable beneficiaries.
4. Governance and production custody design, including signer separation, rotation/recovery assumptions, and owner privileges. A local 2-of-3 test is not proof of secure production custody.
5. The V1 F08 reproduction and whether V2 fully closes the attack path, plus replay, front-running, address substitution, and authorization edge cases.
6. TVM-specific behavior: Energy, `fee_limit`, deployment receipts, failure/rollback behavior, and actual Shasta bytecode.
7. Imported libraries and any relevant off-chain reward/claim integration. Future reward/Merkle contracts must be explicitly excluded from this V2 engagement unless their source is supplied and separately scoped.

**Required deliverables:** named reviewers and independence/conflict statement; methods and exact scope; severity-ranked findings; commit, build, and bytecode hashes; signed/verifiable report; remediation consultation and independent re-test of critical/high findings; explicit exclusions; timeline and fixed total price.

The corrected first-party count is **205 nonblank, noncomment, non-import lines** across all four guarded V2 project-authored contracts (10 + 59 + 53 + 83), as detailed in the frozen-source manifest below. The earlier 75-line figure covered only two files and omitted the vesting and reserve contracts; do not use it as the V2 scope count. The 205 count still excludes imported dependencies and generated code, so it is not the complete audit nSLOC. The auditor must count the agreed final scope before fixing price or calling the review complete.

## 3. Funding conditions

Any workable route must meet all of these conditions before an engagement starts:

- A named third-party payer pays the auditor **directly** for the entire agreed audit and required re-test.
- MOJ1/owner owes no application charge, participation fee, advance, reimbursement, deferred payment, success fee, token allocation, royalty, exclusivity, indemnity, or other financial liability.
- No token, wallet signature, private key, seed phrase, or customer funds are requested.
- Scope, public/private report policy, code-access method, confidentiality, schedule, payer, and full cost are written and reviewed before source access or work begins.
- The sponsor receives no control of MOJ1 contracts, allocations, beneficiaries, keys, or release decisions.

If a proposal misses any condition, mark it **not zero-cost** and do not accept it.

## 4. Current routes and status

| Route | Verified state | Next condition |
|---|---|---|
| Kann Audits grant | Kann's 2026-10-27 reply consolidates its position: it will accept a third party paying the USD 250 participation fee directly, does not identify or guarantee a sponsor, and says repeated requests do not change the terms. The referral alternative remains unavailable because its genuine conditions are not met. | Stop duplicate follow-ups. Reopen only if an eligible outside payer is secured; then obtain the full assessment and re-test scope, total cost, and terms in writing before any commitment. The USD 250 participation fee is not full-audit coverage. Batch 1 deadline shown as 2026-11-15. |
| Guardian Security Fund | Official page currently advertises grant coverage for a full Guardian audit with two competing teams and an exhaustive invariant suite; selected grantees only, not a cash award. A formal application was submitted on 2026-10-27 and the form confirmed receipt. TRON/TVM eligibility and whether the full scope includes the required remediation re-test without owner-side costs remain unconfirmed. No private repository access was granted. | This remains the strongest verified in-kind route on the current evidence. Await Guardian's review; require written TRON/TVM acceptance, complete scope and re-test coverage, and zero owner payment/liability before any private repo access or engagement. |
| TRON Builders League | Official materials allow approved funding to be used for audits, but awards are discretionary and milestone-based. The formal program terms include binding indemnity/arbitration exposure already assessed in issue #853. | **Do not submit or accept TBL terms** under the current zero-liability mandate. Only reconsider if TRON offers a separate written route with no owner liability, approved case by case. |
| Ecosystem sponsor prospects | Existing non-binding enquiries to HTX Ventures, HTX DAO Genesis, P2P.org, Kiln, JustLend Grants DAO and other leads are recorded in issue #853. No award or pledge is recorded. | Wait for substantive replies; do not re-send duplicate inquiries. |
| Free audit queue / security contests | May be slow, discretionary, require public disclosure, a sponsor-funded prize pool, or paid re-test; not equivalent to a private, comprehensive signed audit. The prior Callisto issue attempt was denied by GitHub API (403). | Do not bypass the access restriction or represent automated/community review as full independent assurance. |

## 5. Outreach log and no-duplicate rule

As of 2026-10-27, relevant outreach and replies are tracked in [issue #853](https://github.com/mojtabarozegar11-ship-it/Saeit/issues/853). Kann has replied that it will not source a sponsor and asked that repeated requests stop; no more messages should be sent there unless an outside payer is secured and a substantive new question remains. Guardian and multiple TRON ecosystem prospects have already been contacted; no award or positive eligibility confirmation is recorded. Two duplicate messages were sent in error on 2026-10-26; do not repeat that contact pattern. Check existing threads for replies before any new outreach.

A “sent” message is not a commitment, grant award, payment, quote acceptance, or audit engagement. Record each future inbound reply, verified offer, payer identity, and terms before deciding the next action.

## 6. Intake checklist before sending code to an auditor

- [ ] Confirm artifact 12406875421 and private archive hashes match the frozen intake baseline; retain one controlled copy.
- [ ] Produce a complete dependency and build manifest for the selected commit.
- [ ] Ask the auditor to calculate full-scope nSLOC and identify generated/factory-created code before fixing a quote.
- [ ] Map every deployed address to source, bytecode, constructor arguments, and receipt; explicitly mark Shasta vs Mainnet.
- [ ] Obtain named reviewer identities, qualifications, TRON/TVM experience, conflict statement, confidentiality terms, and secure read-only access plan.
- [ ] Obtain the full-cost written scope, payer, re-test terms, and report publication policy.
- [ ] Verify sponsor funds are paid directly to auditor with no owner reimbursement or contingent liability.
- [ ] Keep Mainnet, sales, liquidity, withdrawals, and rewards blocked until signed independent findings are resolved and every separate legal/custody gate is approved.

## 7. Decision

The engineering evidence and non-binding sponsor materials are assembled sufficiently to **request a scope discussion** without exposing keys or claiming a finished audit. The project is **not yet ready for a funded audit start** because there is no confirmed full-cost payer, no accepted auditor scope/quote, and the complete dependency-inclusive nSLOC/build map remains to be finalized.

A Guardian Security Fund application was submitted on 2026-10-27 using public project facts and owner-provided contact details. Guardian confirmed receipt and offered a grant review call; no appointment was booked because the owner's calendar was unavailable, and the form says Guardian will reach out on Telegram if no listed time is selected. The application is not an award or engagement. Kann's latest reply closes the repetitive inquiry path unless a third-party payer is independently found. No full-scope funding or TRON/TVM eligibility is confirmed. No private repository access, payment, contract, wallet signature, token distribution, Mainnet deployment, sale, pool, or live customer reward was authorized.
