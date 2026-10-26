# MOJ1 vs new token — executable liquidity feasibility decision (2026-10-26)

**Decision: continue MOJ1 V2. Do not deploy a second token.**
This file is a working internal analysis and does not authorize a token sale, Mainnet
transaction, wallet signature, payout, DEX listing or liquidity provision.
The immutable audit reference \`4411b28325be44c54d7917b4c67786348521b6a9\`
is not changed by this branch.

## Verified repository context and constraints

- Existing TRON/TRC-20 MOJ1 V2 implementation, Shasta pilot and test harnesses.
- Provisional fixed 100,000,000,000 token supply and six allocation buckets.
- The *proposed* liquidity reserve is 15% of supply, not USDT/TRX cash.
- V1 had HIGH F08 counterfeit vault/destination risk; V2 guarded candidate
  mitigates the observed path but has no completed independent audit clearance.
- Frozen V2 is not verified Mainnet code. Separate latest hardening branch
  is a development candidate, not a signed third-party audit.
- Current owner budget is zero. Prior PeckShield indication of USD 2,000
  covered only two initial contracts, not all token/reward/governance risks.
  That is not a current fixed quote or an approved purchase.

| Dimension | Continue MOJ1 V2 | New token from scratch |
|---|---|---|
| Reuse engineering / Shasta evidence | Yes, but independently reverify | No |
| New code/design and integration work | Lower incremental burden | Higher |
| Security audit | Independent V2 pre-Mainnet audit outstanding | Separate fresh audit needed |
| Deploy resource cost | Unknown variable TRX/Energy | Unknown variable TRX/Energy |
| Real two-sided liquidity | Requires quote asset capital | Requires quote asset capital |
| Verified buyers, market, redeemability | None established | None established |
| Compliance / issuer / reward rights | Pending | Pending again |
| Budget-zero Mainnet public market feasible? | **No** | **No** |

## What liquidity actually requires

SUN.io documentation describes depositing **both sides** of a trading pair,
setting the initial ratio/price and authorizing wallet signatures:
https://docs.sun.io/liquidity/how-to-create-liquidity/

Token allocations alone are not equivalent to cash, a verified bid, redemption,
or proceeds. If a founder deposits 10,000 USDT alongside MOJ1, this is
**10,000 USDT of founder-funded collateral at risk**, not 10,000 USDT of
revenue. Shallow pools can show a nonzero price while large sells produce
severe slippage. Never publish a claim of guaranteed liquidity or returns.

The V2 constant-product calculator is strictly offline and hypothetical:

\`\`\`sh
cd experiments/moj1-pilot
node tools/liquidity-scenario.mjs \
  --token-reserve 15000000000 \
  --quote-reserve 10000 \
  --sell-tokens 1000000 \
  --fee-bps 30
node --test tests/liquidity-scenario.test.mjs
\`\`\`

These are **illustrative invented reserves**, not a discovered existing DEX pool,
live token price, fund balance, funding plan, or intended allocation release.
The formula is a simple V2-style model with a configurable fee; SunSwap V3/V4
concentrated liquidity and routing have different economics. The script never
uses a wallet, network, secret, transaction or external pricing API.

## Authorized zero-spend execution plan

1. **Now:** reproduce the frozen-source commit, latest isolated hardening,
   Shasta V2 manifest/contract addresses and all relevant checks. Keep separate
   code versions distinguishable.
2. **Now:** use the offline calculator to stress-test future *hypothetical*
   trading depths; reject token-supply-only "valuation" claims.
3. **Now:** maintain an audit bundle, issue register and zero-cost sponsor
   enquiries. No claim of independent approval without a verified signed report.
4. **Before any financial action:** obtain a verifiable independent V2 audit,
   custody/multisig and beneficiary approvals, legal and sanctions review,
   and adequate external quote-asset capital from an authorized source.
5. **Before any Mainnet / sale / DEX activity:** require separate explicit
   owner approval for the exact network, wallet, contract hash, amount,
   counterparty, pool, worst-case loss and transaction(s). Do not obtain
   private keys or seed phrases.

Current production decisions: **NO NEW TOKEN, NO MAINNET DEPLOYMENT,
NO PUBLIC SALE, NO WITHDRAWABLE GAME REWARDS, NO LIQUIDITY TRANSFER.**
