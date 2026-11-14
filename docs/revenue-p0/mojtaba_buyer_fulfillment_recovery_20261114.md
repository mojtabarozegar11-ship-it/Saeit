# mojtaba.bot.ai — order-to-delivery recovery and safe preflight, 2026-11-14

Status: **Draft, unmerged, undeployed, no buyer contact, no payment or download.**

## Source audit finding
The canonical `core.Order`, `core.OrderItem`, `core.Product`, `core.PaymentIntent` and Crown entitlement models exist in this branch. The deployed / mounted `mpw_commerce` customer fulfillment package and its private deliverables do **not** exist as files in this specific GitHub branch. Their presence or absence on cPanel/VPS is unverified. No source-only process may claim fulfilled real purchases.

The existing `core/crown_fleet.py:owned_skus` dereferenced `order.payment_intent` for every `paid` order. A paid order missing the OneToOne PaymentIntent could raise `RelatedObjectDoesNotExist` and break the game fleet route instead of gracefully denying a non-verifiable entitlement. A product with malformed nonobject `metadata` could likewise raise `AttributeError`. Both source paths are now hardened. Existing genuine walletless and legacy internal entitlement tests remain in scoped CI.

## 20 distinct implemented checks and remedies
1. Fail closed on a paid Crown order without a PaymentIntent instead of HTTP 500.
2. Fail closed on a Crown product whose metadata is not a mapping.
3. Reject nonauthenticated users for Crown ownership lookup.
4. Bind order preflight to an existing genuine Order instance, without returning its ID.
5. Require an order paid state, never treating pending as delivered.
6. Require a finite positive order amount.
7. Require an active buyer, not an inactive user.
8. Reject staff/superuser accounts from ordinary buyer delivery preflight.
9. Require a bounded plausible buyer email, rejecting placeholders (still not ownership proof).
10. Require a single order item for a single digital entitlement; no bundle guessing.
11. Require exactly one paid unit, not unsupported quantity >1.
12. Require item currency and unit price to match the order exactly.
13. Require an active product with an actual title.
14. Require an active designated superuser owner for the product.
15. Require structured Product.metadata (never URL/HTML trust).
16. Require explicit `rights_cleared`, `independent_qc_reviewed`, `buyer_terms_approved` flags.
17. Restrict deliverable formats to `pdf`, `epub`, `zip`, `license_key`, `in_game_cosmetic`.
18. Require distinct canonical SHA-256 asset and manifest claims (not physical file proof).
19. Require a canonical semantic version, license code and opaque private asset reference, rejecting URLs and filesystem paths.
20. Reuse revenue evidence reconciler to identify payment/ledger/chargeback blockers. Do **not** issue tokens, emails, refunds or claim customer delivery without independently attested settlement and actual artifact receipt.

## Operational surfaces; no new bot
- `core/fulfillment_preflight.py`: anonymized read-only `inspect_fulfillment_order` and `fulfillment_preflight_snapshot`.
- `core/crown_fleet.py`: avoid 500 and false grants for corrupted/missing intent.
- `command_center/fulfillment_preflight.py`: owner-only noncacheable GET `/staff/command-center/api/bot/fulfillment-preflight/`.
- `core/management/commands/mojtaba_fulfillment_preflight_readonly.py`: server command for safe diagnosis.
- `core/economic_master_agent.py`: same snapshot available through the one `EconomicMasterAgent`.
- `core/tests/test_mojtaba_fulfillment_preflight_20261114.py`: **55 isolated real Django test-DB cases**.
- CI also runs previous Crown account restoration, walletless TRX receipts and revenue reconciliation tests.

## Definitions not to misrepresent
A plausible email is NOT a verified buyer mailbox. A SHA-256 value stored in metadata is NOT evidence the real file exists. A test case that passes is NOT an external provider settlement or proof of download. A company internal `paid` status and a processed payment webhook are NOT the same as independently settled funds.

Even when all source preflight checks pass, the result is `source_preflight_passed_unverified` with `delivery_allowed=false`, `delivery_verified=false`, `private_file_bytes_verified=false`, `independent_settlement_verified=false`. There is no automatic release. Full commercial readiness requires live host source provenance, private artifact verification, buyer email ownership, authorized checkout, provider/chain settlement and a customer delivery acknowledgment.

No migrations, external mail, real purchase, deployment, token transfer, broker order, host change, secret or deletion in this Draft.
