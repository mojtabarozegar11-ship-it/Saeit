# MOJ1 V2 — Token-denominated audit payment decision

**Prepared:** 2026-10-27  
**Purpose:** non-binding payment-model discussion and audit readiness  
**Review target:** `4411b28325be44c54d7917b4c67786348521b6a9`  
**Status:** no quote accepted, no payment authorized, no audit booked

## What changed

On 2026-10-27, 23 non-binding quote/eligibility emails were sent to prior audit-firm contacts asking whether they would consider a full-scope fee paid in up to **200,000,000 MOJ1**, or a partial MOJ1 component plus any minimum liquid-currency amount. These messages explicitly state that the figure is not a USD equivalent; MOJ1 has no verified Mainnet issuance, market price, or liquidity; no work, token allocation, payment, or other obligation is authorized.

OpenZeppelin returned an automated receipt only and directed audit inquiries to its request form. This is not a quote, eligibility confirmation, or acceptance of MOJ1.

## Payment paths ranked by feasibility

| Path | What it would mean | Assessment |
|---|---|---|
| Independent grant pays auditor directly | Sponsor pays the audit provider in a liquid currency or covers the work in kind; MOJ1 owner owes nothing | **Best path.** Guardian's official grant page currently says it covers a full Guardian audit and selects grantees. MOJ1 application was submitted 2026-10-27; receipt is confirmed, award and TRON/TVM eligibility are not. |
| Fixed fee in MOJ1 | A named auditor first gives a written full-scope quote; after separate legal and owner approvals, a fixed amount of MOJ1 is paid under a signed agreement | **Worth price-discovery only.** No accepted quote or verified token value yet. Do not imply the token is cash-equivalent. |
| MOJ1 plus a liquid-currency top-up | Auditor states its minimum liquid amount; a third party or later approved owner funds that amount, with any token portion separately priced | **Possible only if a real payer is identified.** No liquid-currency budget is currently approved. |
| Sponsor-fronted audit, repaid from future revenue | A third-party sponsor pays the auditor now; MOJ1 later repays the sponsor only from a defined share of actually received project revenue, up to a written cap and end date | **Most practical percentage-based structure to explore.** It keeps the auditor on a fixed, independent fee. Still, no sponsor or revenue stream is secured, and the repayment is a contingent financial obligation that needs owner approval and legal review before any offer or signature. |
| Auditor paid a percentage of future revenue | Auditor receives an agreed share of future cash revenue, perhaps until a written cap | **Weak fallback.** There is no validated revenue stream or start date, so this does not pay an audit now. A success-linked fee can also create a perceived conflict; any such arrangement needs independent legal review and must never depend on a favorable audit result. |
| TRON Builders League revenue-share route | TBL's official page says security-audit funding is an allowed use and long-term collaborations may separately propose revenue sharing. Standard terms still include owner indemnity and Hong Kong arbitration exposure. A no-project-materials pre-application terms question was sent to `support@trondao.org` on 2026-10-27 (Gmail `1a17c4c9318f332f`) asking whether direct auditor payment plus capped revenue share can be documented without owner liability. | **New terms inquiry only.** No application or acceptance. Await a written answer on whether the standard liability clauses can be excluded; otherwise stop this route. |
| Public bug bounty / audit contest | Researchers compete for a prize pool; awards may be tokens if the platform and researchers accept them | **Supplement only.** A bounty or contest can find issues but is not automatically a full, signed, independent audit. With no liquid market for MOJ1, a token prize may not attract reviewers. |

## Recommended execution sequence

1. Wait for replies to the 23 payment-model inquiries, Guardian's submitted grant application, and the new TBL pre-application terms inquiry. Do not send duplicate follow-ups in the meantime.
2. For each positive reply, obtain written confirmation of (a) actual TRON/TVM experience, (b) full four-contract/dependency-inclusive scope, (c) signed hash-bound report, (d) critical/high remediation retest, (e) exact payment asset and amount, (f) independence/conflicts, and (g) all exclusions and publication terms.
3. Compare all proposals on the same frozen commit. Keep the 200,000,000 MOJ1 figure as a **non-binding inquiry ceiling only**, not a valuation or payment instruction.
4. Prefer a grant or sponsor that pays the auditor directly. If no sponsor is approved and an auditor accepts MOJ1, obtain a written token-denominated quote and separate legal review before deciding whether to authorize any allocation. Nothing in this memo approves a transfer.
5. If a sponsor proposes to front the audit and recover from future income, define a percentage of cash revenue actually received, repayment cap, start trigger, term/sunset, accounting/audit rights, and no claim on token supply, governance, or a favorable audit result. This would still be a contingent liability; do not accept or sign without separate owner approval and legal review.
6. If an auditor itself insists on future-revenue participation, apply the same safeguards and decline any fee tied to audit findings, severity ratings, or a “pass” result.
7. Keep Mainnet deployment, sale, liquidity, real rewards, and live checkout disabled until the independent report, fix retest, custody, legal, and owner-release gates are separately complete.

## Verified external references

- Guardian Security Fund: https://guardian.security/grants/ — advertises $1,000,000 in audit-grant coverage for a full Guardian audit; applicants are selected. It is in-kind audit coverage, not an award or guaranteed eligibility.
- Guardian audit scope: https://www.guardian.security/audits/ — describes design review, invariant suite, and manual audit.
- TRON Builders League: https://trondao.org/tron-builders-league — official materials allow audit funding and say long-term collaborations may separately propose revenue sharing. Standard terms include indemnity and Hong Kong arbitration; a pre-application terms question was sent on 2026-10-27. No application or acceptance has occurred.
- Code4rena audit process: https://docs.code4rena.com/competitions — sponsors establish prize pools and auditors compete; this does not by itself replace a scoped independent audit engagement.
- OpenZeppelin audit request: https://openzeppelin.com/request/ — OpenZeppelin's automated email response directed audit inquiries here; no manual response or token-payment acceptance has been received.

## Decision

The project now has a frozen-source intake pack and a separate non-binding token-payment inquiry track. **The audit is not funded or complete.** No auditor has accepted MOJ1, no full-price quote is confirmed, and the Guardian application has not been awarded. No transfer, contract, or launch action is authorized by this document.
