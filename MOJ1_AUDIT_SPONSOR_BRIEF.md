# MOJ1 V2 — Independent Security Audit Sponsorship

**Funding target: USD 400 paid directly to the independent auditor.**  
**Current status: Shasta testnet only; Mainnet remains NO-GO.**

## The request

MOJ1 is seeking one sponsor, ecosystem fund, or audit-grant provider to cover an independent security review of the project's V2 smart contracts. The project owner has no available audit cash budget and cannot provide an FX account, advance, reimbursement, debt, guarantee, or contingent payment obligation.

A written BlockHat proposal dated 27 October 2026 quotes a fixed **USD 400** for the defined four-contract scope, including a remediation re-audit. The quote is stated to remain valid through **26 November 2026**. This is a proposal, not an accepted engagement. Before work begins, the quote, auditor identity, payment details, scope and three-party payment arrangement must be independently verified and documented.

**Sponsor payment must go directly to the auditor. No funds should be sent to the project owner, a personal wallet, or an intermediary.**

## What the sponsor would fund

- Manual review of **MojCoinGuarded.sol**, **MojGenesisFactoryGuarded.sol**, **MojVestingVault.sol**, and **MojApprovalReserve.sol**.
- Review against frozen source commit: **4411b28325be44c54d7917b4c67786348521b6a9**.
- TRON/TVM-specific checks, including Energy, bandwidth and fee_limit, plus consideration of the known V1 F08 destination-impersonation issue and its V2 mitigation.
- Source/bytecode identity checks and a signed, severity-ranked report.
- One re-audit of remediated findings within the quoted scope.

The sponsor should confirm all deliverables and exclusions directly with the auditor before paying. Legal/regulatory advice, custody/key-management verification and other excluded work are not represented as part of this quote.

## Why fund this review

The review is a concrete security gate before any Mainnet deployment, token sale, game reward or live payment activity. It provides an independent evidence trail tied to a fixed commit and a defined contract scope. It does **not** guarantee that the contracts are vulnerability-free.

## Conditions that protect sponsor and auditor independence

1. The sponsor pays the auditor directly under written terms; the project owner has no payment, reimbursement, guarantee or contingent liability.
2. The sponsor does not buy a favorable result, control findings, or receive a promise of Mainnet launch.
3. No MOJ1 tokens, equity, revenue rights, future liquidity or investment returns are offered in exchange for sponsorship.
4. No audit begins until the sponsor and auditor are verified, the engagement terms are signed, and payment is confirmed.
5. Mainnet remains blocked until the independent audit and the separate security, legal, custody and release gates are satisfied.
6. Sponsor acknowledgement may be published only with the sponsor's consent and must not be presented as an endorsement of the token or the audit outcome.

## Alternatives welcomed

- Full audit-grant coverage from a qualified security provider.
- A fully funded, direct-pay sponsorship of the quoted USD 400 review.
- Qualified pro-bono independent audit capacity covering the same or a clearly stated equivalent scope.

Guardian Security Fund currently advertises audit-grant coverage for selected projects: https://www.guardian.security/grants/. Kann Audits accepts free grant applications until 15 November 2026, but approved projects must pay a USD 250 participation fee, so that route still requires a sponsor for the contribution: https://kannaudits.com/audit-grants.

## How to respond

Please use the public funding request at [GitHub issue #1395](https://github.com/mojtabarozegar11-ship-it/Saeit/issues/1395), or propose a qualified grant programme or auditor. A response should identify the sponsoring person or organization, public website, scope/amount covered, and direct-pay mechanism. No funds or sensitive credentials should be posted in public comments.

Related release gate: [GitHub issue #853](https://github.com/mojtabarozegar11-ship-it/Saeit/issues/853).
