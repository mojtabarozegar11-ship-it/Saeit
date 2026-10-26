# MOJ1 V2 — independent-audit sponsorship brief (non-binding)
**Prepared:** 2026-10-26 | **Status:** zero-cash sponsor research only | **Mainnet: NO-GO**

This is a public, non-binding factual project summary for prospective qualified
security auditors, ecosystem-grant administrators and sponsors. **It is not a
grant application, offer, acceptance, investment solicitation or authorization
to deploy, sell, distribute or create an exchange pool.** No funding is secured.

## Project and immutable review target

- Project: **MOJ1** — TRON/TRC-20 Solidity token candidate with a proposed
  total of **100,000,000,000 MOJ1**, split into six provisional allocation
  buckets. Allocations are not sale proceeds or redeemable cash.
- Frozen audit-source commit:
  [4411b28325be44c54d7917b4c67786348521b6a9](https://github.com/mojtabarozegar11-ship-it/Saeit/commit/4411b28325be44c54d7917b4c67786348521b6a9).
- V2 Shasta **testnet** token: `TA8dcG3b9GByaY9vZ1LVjsFohZrZ4CveAY`;
  factory/escrow: `TCBNLE1ZgEcAWXRZ6jjYPSyUH7WiHpLyBm`.
  Existing Shasta V1 token is separate and has a known HIGH destination
  impersonation finding (F08). **Do not invoke V1 distribution.**
- V2 Shasta supply is held in the factory escrow with no public release.
  Test evidence: [Shasta public attestation run 39738660931](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/39738660931).
  This **does not** establish independent security, legal, custody or Mainnet clearance.
- Auditor input archive `moj1-v2-unsigned-auditor-input-39734674912`,
  GitHub Actions artifact **12406875421**, SHA-256
  `280b7964221dd989707f8e5f788b821c5465f8a68167e2a99e9fa840c1aa9169`.
  GitHub retention ends **2026-11-05**; a hash-verified private preservation
  has been recorded in issue #853. Never circulate unreviewed private contents.

## Request to sponsor or qualified independent auditor

Provide **direct sponsor-to-auditor funding** or an explicit no-fee,
non-contingent professional assessment of the V2 security scope, ideally
including associated treasury, six-vault/vesting, governance/reward paths,
contract dependencies and exact deployed bytecode. Please clarify all scope
boundaries rather than describing a partial two-contract examination as
a complete production security audit.

The independent deliverable should identify named reviewers, conflicts of
interest, TVM/TRON expertise, methodology, V1 F08 reproduction, V2 mitigation,
severity-ranked findings, commit + artifact/bytecode hashes, Energy/`fee_limit`
risks, retest of fixes, and a dated verifiable signed report.

**Funding reality:** Owner cash budget for this activity is **USD 0**.
One non-binding PeckShield indication was roughly **USD 2,000 for 2.5 days**
for an initial **two-contract** report; that price is neither a complete
multi-component audit budget nor a current accepted offer. A full scoped quote
is still required. No quote has been accepted and no reviewer retained.

## Independent gates and milestones

1. Review source/evidence, document complete risk surface, verify technical
   competence and conflicts, specify excluded components.
2. Propose a **non-binding** scope, signed-report format, remediation retest
   window, fixed total price and clearly named direct payer.
3. Sponsor and owner separately approve any terms when identified. There is
   currently **no authorization** to incur fees, repayment, deferred charges,
   token-based compensation, exclusivity or royalty obligations.
4. Auditor performs independent manual and tool-assisted assessment, provides
   hash-bound findings; engineering remediates and independent reviewer retests.
5. Only then consider distinct beneficial ownership, production multisig,
   legal/sanctions, customer disclosures, external funding and an owner-specific
   Mainnet decision. **No automatic release** follows an audit alone.

## Zero-cost research path (not an application)

The official [TRON Builders League program](https://trondao.org/tron-builders-league)
lists **security audits and smart-contract deployment** as permitted uses
of *approved* milestone-based funding, subject to eligibility, forum
participation and sponsor discretion. No award or eligibility determination
for MOJ1 has been obtained. The program's terms may bind an applicant;
do not submit an application or accept any terms on the owner's behalf
without separate review and case-specific approval.

Alternative: a genuinely independent qualified auditor may elect a pro-bono
engagement with a full named scope, defined deliverables and no hidden fee.
Automated or self-authored checks are helpful preparation **but are not**
a substitute for the required independent examination.

## Permanent release restriction

No Mainnet deployment, sale, withdrawal, liquidity funding, real game token
rewards, public market-price claims or live checkout linkage is authorized.
The technical release issue remains
[#853](https://github.com/mojtabarozegar11-ship-it/Saeit/issues/853),
and the offline comparison/guard work remains
[PR #1270](https://github.com/mojtabarozegar11-ship-it/Saeit/pull/1270)
against an isolated MOJ1 development branch. No private keys, seed phrases,
wallet signatures, payments or transactions are needed for this brief.
