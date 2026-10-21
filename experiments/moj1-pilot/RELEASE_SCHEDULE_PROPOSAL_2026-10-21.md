# MOJ1 — Draft Token Release Schedule v0.1 (design only)

**Date:** 2026-10-21  
**Status:** PROPOSED / NOT OWNER-APPROVED / NO REAL TOKENS OR WALLETS  
**Branch:** `moj1/shasta-pilot-20261021`  
**Scope:** Release timing and controls only. The six allocation percentages (35/20/15/10/15/5) are already owner-approved. Nothing here approves recipients, prices, liquidity provision, treasury operation, deployment, a live sale or a Mainnet transfer.

## Starting conditions

- `T0` is a future, separately approved, UTC timestamp for full funding of all six on-chain vaults; never assume `T0 = 2026-10-21` or backdate.
- The entire 100,000,000,000 MOJ1 fixed supply remains under escrow until all distribution checks pass. **Vesting means eligible for release to a beneficiary; it does not equal circulation, rewards paid to players, market liquidity or sales.**
- One owner-approved timetable, verified beneficiary addresses, independently reviewed multisig and audited contracts must be in place before any live activity.
- Existing Solidity durations count literal `days` (86,400 seconds) rather than variable-length calendar months. A 365-day cliff releases **zero at the exact cliff boundary**; linear release begins immediately afterward.

## Six-bucket proposal

| Bucket | Approved share and maximum amount | Proposed unlock mechanism | Annualized limit and controls |
| --- | --- | --- | --- |
| Player rewards / ecosystem | 35% / 35bn | 1,825-day linear vesting from T0 into a **program escrow**, then separate, verified rewards claims | 7bn per 365 days maximum eligibility; publish claim root, prevent duplicate claims, set anti-Sybil / rewards rules; unclaimed balance stays in custody |
| Product development / security | 20% / 20bn | 1,460-day linear vesting from T0 | 5bn per 365 days maximum eligibility; milestone invoices and multisig spending approval; vesting alone cannot enforce use-of-proceeds |
| Future liquidity | 15% / 15bn | **No automatic release.** Independent approval of market/liquidity use; at least 30-day public timelock | **Proposed new vault:** at most 1bn in any 90-day tranche, separated by >=90 days; 15 tranches minimum, no catch-up of unused windows |
| Team / contributors | 10% / 10bn | 365-day hard cliff, then 1,095-day linear vesting; no lump sum at cliff | 0 in first 365 days; at most ~3.33bn per following 365 days; pre-approved individual allocations and documented agreements |
| Partners / creators | 15% / 15bn | 1,460-day linear vesting from T0 to contract-controlled distribution | 3.75bn per 365 days maximum eligibility; verified deliverables and specific beneficiary approval before onward transfers |
| Contingency / audit | 5% / 5bn | **No automatic release.** Itemized, auditable security/incident budget and at least 30-day timelock | **Proposed new vault:** at most 0.25bn in any 90-day tranche, separated by >=90 days; 20 tranches minimum; unused funds remain locked |

**The liquidity and contingency tranches are suggestions, not existing behavior.** The current `MojApprovalReserve.sol` allows a full-balance transfer to a single immutable beneficiary as soon as a one-time governance authorization and 30-day delay are satisfied. It **must be redesigned, audited and tested** to enforce the proposed per-tranche limits before any production use. Current `MojGenesisDistributor.sol` fixes the four linear schedules at 1,825/1,460/(365 + 1,095)/1,460 days and checks the reserve type, not tranche caps.

## Maxima of the four linearly vesting vaults (not circulating supply)

At `T0 + N * 365 days`, excluding both conditional reserves and disregarding any unclaimed/unspent balances:

| Elapsed years | Rewards | Development | Team | Partners | Total eligible by then |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 | 0bn | 0bn | 0bn | 0bn | 0bn |
| 1 | 7bn | 5bn | 0bn | 3.75bn | **15.75bn** |
| 2 | 14bn | 10bn | 3.33bn | 7.5bn | **34.83bn** |
| 3 | 21bn | 15bn | 6.67bn | 11.25bn | **53.92bn** |
| 4 | 28bn | 20bn | 10bn | 15bn | **73bn** |
| 5 | 35bn | 20bn | 10bn | 15bn | **80bn** |

The remaining **20bn** in the liquidity and contingency reserves has no fixed automatic release date; even when authorized, actual deployment may be restricted by law, demand, contract policy and treasury approval. This table is **not** a forecast of trading volume, token price, liquidity or wealth.

## Engineering acceptance criteria before proposing owner sign-off

1. Specify governance authority (multisig threshold, member identity review, signer rotation and disaster recovery). Never store keys or seed phrases in GitHub.
2. Implement an on-chain **capped, multi-tranche reserve** with per-tranche nonce, fixed amount ceiling, >=90-day spacing, >=30-day timelock, cancel path, reentrancy resistance and event logs. A plain 30-day delayed full release is **NO-GO**.
3. For program distributions, specify claim proof verification, double-claim defense, claim-expiration handling, reward-policy changes, anti-abuse rate limits, full-funding conservation and independent audit.
4. Add local TVM tests for `T0`, each cliff boundary, first wei of vesting, end of vesting, zero/future timestamps, premature release, unauthorized releases, replay, over-cap tranche, cancel, delayed execution, token failure and exact supply conservation.
5. Do not merge release-policy changes into live deployment until owner independently approves the **specific schedule, final beneficiary addresses and security architecture**, plus external legal/security reviews. Require a further explicit signature before Shasta deployment or any Mainnet transaction.

## References (design research)

- [OpenZeppelin finance: vesting and cliffs](https://docs.openzeppelin.com/contracts/5.x/api/finance)
- [OpenZeppelin governance: timelock scheduling, execution and cancellation](https://docs.openzeppelin.com/contracts/5.x/api/governance)
- [TRON testnet versus Mainnet glossary](https://developers.tron.network/docs/glossary)
- [TRON smart-contract deployment and invocation](https://developers.tron.network/docs/smart-contract-deployment-and-invocation)

**Approval gate:** `tokenomics.json.ownerApproval.releaseScheduleApproved` stays `false`. Do not infer approval from creation or merging of this design document.
