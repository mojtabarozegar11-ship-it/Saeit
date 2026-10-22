# MOJ1 F08: Genesis vault impersonation — internal finding (2026-10-22)

**Decision: NO-GO for Mainnet, public sale, real rewards, and all V1 genesis distribution.** This is an internal technical finding, not an independent audit, legal opinion, or permission to sign transactions.

## Finding F08 (HIGH): V1 trusts getters, not destination code

The immutable Shasta V1 implementation (MojGenesisDistributor.sol) accepts six externally predeployed vault addresses. It checks token, allocation, beneficiary, vesting start/cliff/duration, release counters or reserve caps by calling methods on each purported vault. A malicious lookalike can return the expected getter values without enforcing the schedules. The local test clock-override reserve harness also inherits matching getters and could masquerade as a production reserve. The original governance still needs to approve distribution; the finding is a **dangerous authorized-destination substitution risk**, not an arbitrary outsider bypass of governance.

The local Tron TVM proof in tests/tronbox/genesis-guarded.integration.js does the following:

1. Deploys unmodified V1 with disposable local test accounts.
2. Gives bucket 0 (35 billion) to contracts/test/MojVestingLookalike.sol, a fixture implementing matching getters with an unrestricted drain method.
3. Shows V1 accepts this lookalike, distributes all 100 billion and lets a third party drain bucket 0 immediately, before vesting.
4. Confirms fixed total supply is maintained — supply conservation does not prove distribution security.

Treat this as a demonstrated exploit **only after the isolated GitHub TVM run passes**.

## V2 engineering candidate: factory-produced vaults

The separately named MojCoinGuarded.sol creates MojGenesisFactoryGuarded.sol and mints the 100 billion fixed supply to its own factory. Its distribution method takes six **beneficiary addresses**, not arbitrary vault implementation addresses. Following governance authorization and checks for fully funded escrow, future start time, unique nonzero beneficiaries and one-shot distribution, the factory itself deploys four MojVestingVault implementations and two MojApprovalReserve implementations. It uses the same approved percentages (35/20/15/10/15/5), existing proposed schedules and reserve caps, transfers exact amounts, and emits creation records. Test-only clock harnesses cannot become factory-created vaults.

Caveats:
- A malicious **approved beneficiary** can still misuse legally unlocked funds; beneficiary identity and custody must be separately approved.
- Creating six contracts atomically can be energy-expensive on TRON; TVM and Shasta gas/energy costs, fee-limit and rollback behavior need measurement.
- New code is a **local TVM research candidate**, not deployed on Shasta/Mainnet and not externally audited. Approval of allocation percentages is not approval of the V2 vesting schedule or recipients.
- Deployed Shasta V1 is immutable. Do not rewrite its source in place (this would invalidate attestation) and **do not call V1 distribute**. The existing escrowed supply remains isolated on Shasta until an independently approved migration or replacement pilot.

## Independent audit and operational handoff

A qualified independent reviewer must scrutinize exact repository commit, compiled bytecode, factory creation paths, reentrancy and TRON energy behavior, vesting/timelock edge cases, token and NFT access control, beneficiary validation, 2-of-3 custody/recovery, fraud prevention, key operations, and negative testing. The issuer must separately document owner-approved timing, recipients, market-specific legal/sanctions/gaming/payment review, white-paper disclosures, and custody practices. Reproducible tests and internal claims are **not** external sign-offs.

Safe commands: npm test; npm run compile; npm run preflight; npm run test:onchain:local (requires disposable localhost TRON VM). No key, live web-server, payment gateway, Mainnet, or public-sale operation is in scope.
