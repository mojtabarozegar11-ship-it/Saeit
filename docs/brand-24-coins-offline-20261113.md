# 24 independent brand coin identities — OFFLINE registration only

Date: 2026-11-13. Owner brands: Zomorod Melal and MojPlayWin.

## What this change actually establishes

- 12 named brand groups × 2 unique coin candidates each = **24 source-registry records**.
- All 24 are **offline proposed names and source specifications**, NOT tokens issued on any blockchain.
- The registry cannot contain real contract addresses, transaction IDs, payments, liquidity, revenue, or mainnet activation.
- Mainnet choice, legal/tokenomics assessment, fee approval and name clearance are all pending.
- Proposed fixed supplies: 1,000,000,000 (service/education) and 100,000,000 (game/community), **not finalized economic distributions**.
- Prototyping standard: TRC-20, `shasta` source-only; existing F41 builder never broadcasts.

## Identity roster

| Brand | Service / learning coin | Symbol | Game / community coin | Symbol |
|---|---|---|---|---|
| سمن (saman) | Saman Study Coin | `ZMSMST` | Saman Play Coin | `ZMSMPL` |
| زهرا (zahra) | Zahra Insight Coin | `ZMZHIN` | Zahra Bloom Coin | `ZMZHBL` |
| ژیلا (zhila) | Zhila Logic Coin | `ZMZLLO` | Zhila Nova Coin | `ZMZLNV` |
| مرضیه (marzieh) | Marzieh Terra Coin | `ZMMZTR` | Marzieh Spark Coin | `ZMMZSP` |
| مریم (maryam) | Maryam Atlas Coin | `ZMMYAT` | Maryam Muse Coin | `ZMMYMU` |
| مرجان (marjan) | Marjan Pearl Coin | `ZMMJPE` | Marjan Tide Coin | `ZMMJTI` |
| محمد (mohammad) | Mohammad Build Coin | `ZMMHBU` | Mohammad Forge Coin | `ZMMHFO` |
| مصطفی (mostafa) | Mostafa Nexus Coin | `ZMMSNE` | Mostafa Pulse Coin | `ZMMSPU` |
| فرناز (farnaz) | Farnaz Art Coin | `ZMFNAR` | Farnaz Bloom Coin | `ZMFNBL` |
| فریماه (faremah) | Faremah Care Coin | `ZMFMCA` | Faremah Glow Coin | `ZMFMGL` |
| تانیا (taniya) | Taniya Cake Coin | `ZMTNCA` | Taniya Quest Coin | `ZMTNQU` |
| رهام (raham) | Raham Jungle Coin | `ZMRHJU` | Raham Runner Coin | `ZMRHRU` |

## Reproducible private source preparation

```bash
python3 -B scripts/brand_24_coin_specs.py
python3 -B -m unittest tests.test_brand_24_coin_specs
mkdir -p private-brand-coin-work
python3 -B scripts/brand_24_coin_specs.py --out private-brand-coin-work/specs
python3 -B scripts/brand_24_coin_specs.py --verify private-brand-coin-work/specs
python3 -B scripts/factory_f41_token_builder_v2.py --spec private-brand-coin-work/specs/saman-service_learning.json --out private-brand-coin-work/saman-private-kit
python3 -B scripts/factory_f41_token_builder_v2.py --spec private-brand-coin-work/specs/saman-service_learning.json --out private-brand-coin-work/saman-private-kit --verify
```

Keep generated private artifacts out of Git; these commands never deploy or transmit transactions. No tokens have been minted by this PR.

## Hard gates before public issuance

1. Document intended utility, rights, fundraising classification, sanctions and jurisdictional legal/tax review.
2. Independently verify name/ticker trademark availability and warn that symbols are not globally reserved.
3. Choose final network and finalize supply, vesting, treasury, vesting contracts, and anti-abuse controls.
4. Independent security audit and reproducible toolchain compilation with trusted dependencies.
5. Verify signed wallet ownership, deployment gas/energy estimate, fee and funding source; request **separate owner approval for each spend**.
6. Non-financial testnet review only with explicit permission, then separate explicit mainnet issuance approval.
7. Verify chain transaction, contract explorer, ownership and provenance; do not claim listings, liquidity, ROI or income without evidence.

**No deploy, mainnet transaction, fee, wallet use, public sale, or user-data change was authorized or performed by this change.**
