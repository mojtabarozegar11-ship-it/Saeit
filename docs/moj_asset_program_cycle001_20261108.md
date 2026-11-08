# Moj asset program — Cycle 001 (source candidate, not a launch)

Date: 2026-11-08. Owner: Mojtaba Rozegar.

## Immutable owner requirements

| Family | Count | Network requirement | Whole-token supply |
| --- | ---: | --- | ---: |
| Mojoner | 1 | Bitcoin, protocol to be confirmed | 24,567,856 exactly |
| Moj1–Moj50 | 50 | Other blockchains, final networks not selected | Each between 100,000,000,000 and 10,000,000,000,000 |

The offline catalog implementation is `scripts/moj_asset_registry.py`. It
enumerates 51 unique names/tickers. The Bitcoin protocol *candidate* is Runes,
using zero divisibility and a premine-only etching model whose proposed supply
equation is `24,567,856 + 0 × 0 = 24,567,856` units. The rune name's availability,
eligibility and actual issuance have **not** been checked or proven.

For Moj1–Moj50, exact individual supplies are only **revisable proposals**:
`(100 + floor(9,900 × (index - 1) / 49)) billion` for indices 1..50. Thus
Moj1 = 100 billion and Moj50 = 10 trillion, with 50 different supply values.
The selected production networks, token standards, decimals, treasury owners,
allocations and commercial terms remain undecided. The generator refuses to
label these tokens deployed or sale-ready.

## Reusable offline production input

Running the script with `--out NEW_DIRECTORY` creates an audited, checksummed
bundle, without keys, RPC access or paid chain transactions:

- one complete manifest for all 51 assets;
- fifty individual Shasta-only TRC-20 candidate specs compatible with the
  existing `scripts/factory_f41_token_builder_v2.py`;
- one SHA-256 inventory for those 51 inputs.

Shasta is **only** a source-generation/validation target, not the selection of
TRON Mainnet for any of the fifty assets. Mojoner is never fed into the TRC-20
builder. This line is distinct from the on-chain MOJ1 legacy guarded project;
no legacy contract is deployed, replaced or modified by this cycle.

## Mandatory release gates

1. Confirm the final selected Bitcoin fungible-asset protocol, name availability
   and the exact minting/etching configuration with independent review.
2. Choose the network, standard, decimals and definitive whole-token supply
   for each Moj1–Moj50; secure the relevant chain infrastructure.
3. Provide token utility, distribution, treasury controls, vesting, account
   recovery, holder-risk notices and legal review for every jurisdiction served.
4. Obtain independent contract and runtime audits, deployment cost estimates
   and signed owner approvals for each paid or irreversible action.
5. Prove any game integration using a server-authoritative fulfillment ledger;
   internal game achievements must not be represented as withdrawable tokens.
6. Only after launch, verify explorer addresses, real fills, slippage, liquidity,
   payment receipts and revenue independently. No buyers or income are assumed.

## Technical references checked

- Bitcoin Runes protocol: https://docs.ordinals.com/runes/specification.html
- Runes units, divisibility and premine: https://docs.ordinals.com/runes.html
- TRON TRC-20 standard: https://developers.tron.network/docs/trc20
- TRON deploy costs/energy: https://developers.tron.network/docs/set-feelimit
- OpenZeppelin ERC-20 supply: https://docs.openzeppelin.com/contracts/5.x/erc20-supply

**State:** source/spec generator produced; no token deployed, minted or sold;
no wallet accessed; zero verifiable on-chain revenue for this cycle.
