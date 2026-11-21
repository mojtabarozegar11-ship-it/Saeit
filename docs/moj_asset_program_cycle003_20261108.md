# Moj asset program — Cycle 003: candidate ERC-20 type identity

## Corrected technical blocker

The 50 offline ERC-20 source candidates formerly declared a shared Solidity
contract name `MojFixedSupply`. While source paths were distinct, consuming
the whole package in one build/deployment tool could create ambiguous
contract-factory and artifact references.

The generator now emits `Moj1FixedSupply` through `Moj50FixedSupply` as 50
different Solidity declarations. Names/symbols/supply and the single
constructor `_mint` remain unchanged. Each candidate still:

- allocates the exact proposed whole-token supply multiplied by 10^18 to a
  nonzero constructor-provided holder;
- exposes no owner, extra mint function, upgrade or tax surface;
- is an uncompiled, unaudited **candidate**, without a production network,
  wallet, verified market demand, liquidity or deployment authority.

## Evidence

- 32 of 32 local asset-program tests passed, including combined-build
  declaration uniqueness and a mint/admin-surface check.
- Reproducible offline bundle remains 103 files for 51 asset proposals.
- Mojoner remains one Bitcoin Runes premine-only fixed supply proposal for
  24,567,856 indivisible units; nothing was etched or broadcast.
- Moj1–Moj50 still target **100 billion–10 trillion each** as deterministic,
  revisable *candidate* supplies; no on-chain issued supply is claimed.

**Commercial gating:** select the non-Bitcoin chain(s), compile and audit
contracts, validate denomination/name availability, check law and marketing,
obtain owner-specific approval for all fees, then independently verify
issuance/distribution/liquidity/revenue. Zero paid transactions here.
