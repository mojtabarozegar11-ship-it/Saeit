# MOJ1 V2 — independent audit handoff and Energy verification (22 October 2026)

**This is an engineering evidence packet, not an independent audit or legal sign-off. Mainnet, public sale, prizes, exchange and real payments remain blocked.**

## Engineering evidence to date

1. The original immutable Shasta V1 remains fully in escrow and matches public creation/runtime bytecode (prior keyless run).
2. V1's external vault policy-getter impersonation issue (F08, HIGH) was reproduced in disposable local TVM. It can release 35bn to a fake rewards vault even when token supply remains exactly 100bn; it still requires an authorized governance call.
3. V2 creates six known vault implementations internally, accepts only six beneficiary addresses, and holds exact fixed allocation amounts. This fixes the V1 *untrusted destination implementation* flaw in the candidate source; it does not guarantee beneficiary integrity or audit completion.
4. The test suite adds actual V2 2-of-3 governance distribution, unauthorized-signature/replay rejects, precise beneficiary and six-vault fund conservation, plus local transaction Energy-use capture. GitHub Actions must pass before claiming these checks ran successfully.
5. The independent-auditor input is produced from a strict source/compiled-artifact allowlist with SHA-256 checksums, source commit, Solidity 0.8.25 build output and local TVM Energy receipts. No owner, auditor or lawyer signature is fabricated.

## Cost/energy evidence boundaries

- Local TVM receipts (if reported) measure a **disposable TVM execution**, not a Shasta/Mainnet price.
- The keyless Shasta script asks only wallet/triggerconstantcontract to simulate V2 deployment. It never signs or broadcasts. If the node does not support deployment simulation, it records UNAVAILABLE rather than a made-up number.
- Official TRON documentation: https://developers.tron.network/docs/set-feelimit . Real fee_limit depends on current Energy price, chain parameters, deployment-caller resources and dynamic energy factors; no fixed Mainnet TRX quote is claimed from a local test.
- Deploying V2 itself creates the genesis escrow and 100bn supply **on that specific chain**, even with distribution disabled. A new Shasta V2 deployment would duplicate the pilot asset and require explicit address/identity disclaimers, controlled testnet resource budgets and additional permission before broadcast.
- Atomic six-vault distribution consumes more Energy than token creation; measure/rehearse its upper bound separately before authorizing *any* such network transaction.

## Remaining independent gates (cannot be self-certified by an agent)

| Gate | Required independent proof | State |
|---|---|---|
| Smart contract security | Independent auditor report tied to exact source commit, artifact hashes, exploited V1 finding, V2 fix and open risks | PENDING |
| Shasta deployment and fees | Keyless estimate followed by owner-authorized controlled testnet deployment, exact bytecode attestation and rollback/fee receipts | PENDING |
| Governance / custody | Verified owner signers, threshold and recovery, wallet inventory, incident response drills without disclosing keys | PENDING |
| Beneficiaries / release | Actual six addresses, signed release timetable, program rewards rules, anti-abuse, caps and reserve approvals | PENDING |
| Legal / commercial | Issuer identity, local rules for token/rewards/gambling/markets/consumer claims, disclosures and applicable licenses | PENDING |
| Mainnet and sales | Separate explicit owner approval after all prior reports and real payment integration tests | BLOCKED |

Do not distribute the deployed V1 Shasta escrow or assume that successful local TVM tests grant any external approval. Do not store seed phrases/private keys in GitHub, AI conversations, CI artifacts or logs.
