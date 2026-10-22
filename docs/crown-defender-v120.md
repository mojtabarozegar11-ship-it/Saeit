# Crown Defender V120: Jet Dominion

V100 → V120 is a consolidated release of twenty concrete changes, not evidence of twenty independent evolutionary generations. Every difficulty retains the existing 100-life baseline; armor continues to add earned hull upgrades.

1. Original faceted vector jet renderer with intake, canopy and navigation light detail.
2. Eight original airframes: Falcon, Raptor, Manta, Spectre, Valkyrie, Tempest, Phoenix and Sovereign.
3. Three free jet unlocks, with credit debits that cannot repeat for an owned jet.
4. Five premium cosmetic SKU definitions, without combat advantages.
5. Animated full-screen fleet preview.
6. Rendered model selection cards and selected/owned indicators.
7. Three persistent livery palettes.
8. Three persistent engine trail palettes.
9. Single, twin and triple-engine animated exhaust.
10. Smoothed bank animation while steering.
11. Parallax orbital station architecture in high-detail mode.
12. Gamepad movement, firing and dash with disconnect cleanup.
13. Free per-run test flights of every premium model, without ownership grants.
14. Current-airframe HUD and quick hangar access.
15. Compatible local fleet storage that refuses premium grants from browser saves.
16. Account-scoped, uncached server ownership restoration endpoint.
17. Native order, payment intent, amount, currency and ledger consistency checks.
18. Refund/reversal/chargeback entitlement invalidation.
19. Duplicate-SKU checks, server catalogue prices and gated checkout navigation.
20. Store timeout, malformed response and offline fallback that preserves free play.

## Validation

`node tests/game/crown-v120.cjs` exercises combat rendering with finite draw arguments, 100 starting lives, free credit purchases, duplicate purchase protection, premium forgery rejection, trial isolation, verified account restore and offline revocation.

`DEBUG=True python -m pytest tests/test_crown_fleet.py -q` tests account isolation, ten incomplete/invalid settlement scenarios, duplicate catalogue entries, verified checkout gates and private cache headers. Browser QA covers the rendered showroom, model selection and test flight.

## Deployment scope

The existing GitHub → VPS relay → cPanel route deploys a single static game file plus a read-only Django fleet module and one appended URL route. Existing live URL configuration is preserved; backups remain private. No database migrations, payment flags, wallets or existing product records are changed. A failed public smoke test restores both the static game and API configuration.

## Commercial activation still required

This release must not be advertised as accepting real in-game payments. Paid jets remain `NOT ON SALE` until all of the following are verified:

- Register five `core.Product` rows of type `game_cosmetic`, with an unambiguous `crown_sku` in metadata. All must be USD and respect the site's existing minimum of $4.
- Verify that the live product checkout can sell a cosmetic entitlement and that its real settlement writes the native `core.Order`, `PaymentIntent` and `LedgerEntry` evidence consumed by this module. The separate `mpw_commerce` and guest checkout systems are not assumed compatible.
- Run a complete authorized test-network purchase, account restore on a second browser, refund/revocation and repeated-callback tests against the actual live checkout adapter. Unit fixtures do not count as network payment evidence.
- Only after that evidence, set `rights_cleared` and `crown_checkout_verified` to true on each approved product, and enable `CROWN_STORE_ENABLED` in runtime settings. A missing gate disables checkout.
- Premium purchases are one-time original cosmetic designs. No loot boxes, chance rewards, recurring charges or paid combat power are implemented. Local scores/credits are not a competitive or financial authority.

The native repository payment endpoints require staff approval and cannot be assumed to be the public checkout. No new wallet instructions or client-side payment confirmation are introduced.
