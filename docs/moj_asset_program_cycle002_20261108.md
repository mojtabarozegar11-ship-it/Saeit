# Moj assets — Cycle 002: two immutable source paths, still no issuance

Date: 2026-11-08. This complements the prior cycle's 51-asset owner catalog.

## Changes

1. **Bitcoin / Mojoner:** the Runes proposal now explicitly omits open-mint
   terms (`terms: null` in the planning manifest). It proposes one premine
   allocation of precisely 24,567,856 indivisible units and a fixed total
   supply of 24,567,856. A standalone `ord` batch *etching fragment* is
   generated, but is not executable as a wallet transaction by itself.
2. **Other chains / Moj1–Moj50:** fifty candidate OpenZeppelin ERC-20 Solidity
   source files are generated with distinct symbols and whole-token supplies
   across the owner's range. They each mint exactly once in the constructor
   to the supplied nonzero initial holder. There is no owner role, transfer
   tax, upgrade function or later mint entry point.
3. **Existing TRON line:** fifty F41 Shasta-only private TRC-20 specifications
   remain available, without selecting TRON Mainnet as the final network.
4. **Provenance:** a new offline bundle contains 102 source/specification
   files plus one SHA-256 inventory. The verifier independently regenerates
   every expected byte, rejects additions and altered files, and never invokes
   a wallet, key, RPC, deployment or paid transaction.

These are *candidate inputs*, not independently audited or compiled production
contracts. They must not be advertised as issued, liquid, tradable or income-
generating. The earlier 100-billion-to-10-trillion mapping remains a revisable
proposal until the owner confirms each exact token supply.

## Direct commands (offline only)

```sh
python scripts/moj_asset_registry.py --out NEW_DIRECTORY
python -m unittest discover -s tests -p 'test_moj_asset_registry.py'
```

First command refuses to replace an existing destination. Second verifies
invariants and tamper protections using standard Python only. This cycle
locally observed 30 passing dedicated tests and 103 generated files.

## Owner/production gates still closed

- Rune name availability, `ord`-version compatibility, fees, receiving wallet,
  treasury custody and Bitcoin commit/reveal transaction details.
- Final non-Bitcoin chains, independent Solidity/TRC-20 audit, compiled-bytecode
  reproducibility, real gas/energy estimates and deployment permissions.
- Legal/revenue disclosures, game-entitlement integration, liquidity and
  truthful marketplace listings.

Official references:

- https://docs.ordinals.com/guides/batch-inscribing.html
- https://docs.ordinals.com/runes/specification.html
- https://docs.openzeppelin.com/contracts/5.x/erc20-supply
- https://developers.tron.network/docs/trc20

No production deploy, sale, payment, on-chain transfer or commercial revenue
occurred in this cycle.
