# AGRI200 — evidence-calibrated base-price policy (2026-10-24)

**Commercial mandate:** 100 English drafts in USD at MojPlayWin, 100 Persian drafts in IRR at Zomorod Melal; base list price determined by ChatGPT from market comparables, and **all discounts, coupons, sales and temporary promotions reserved for the owner**.

These 200 entries are currently **private, unpublished, unapproved drafts**. Product prices are conditional *list-price proposals*, not offers to buyers. Pricing does not change owner-rejected QC evidence, cannot grant QC1000, and does not make checkout functional.

## Price bands (for completed, genuinely original deliverables)

| Intended value | MojPlayWin, USD | Zomorod Melal, IRR | Iranian toman for human reference only |
| --- | ---: | ---: | ---: |
| Starter: focused practical guide or functional planner | $4.99 | 390,000 ریال | 39,000 تومان |
| Practical: complete applied guide and worksheets | $7.99 | 690,000 ریال | 69,000 تومان |
| Specialist: expert analysis, worked calculations or usable operational tool | $11.99 | 990,000 ریال | 99,000 تومان |

**All Iranian store prices are denominated in rials (IRR), not tomans.** No USD/IRR conversion rate is assumed; prices were set against each local market independently. USD prices are decimal dollars; IRR are integer rials. Neither is a gateway-specific minor-units amount. Checkout gateways must convert and validate their own amount representation.

Editorial tier assignments are explicit by AGRI ID in `scripts/agri200_fair_pricing_owner_only_20261024.py`. Every one of the 200 rows receives a concrete currency-appropriate amount. A content specialist must later review that each actual file offers the expected value; if not, the file remains blocked instead of being falsely sold as premium.

## Comparables consulted

- Etsy homesteading printables and farm management worksheets: examples from roughly $3–$12 for focused digital planners; larger collections higher. https://www.etsy.com/market/homesteading_printable and https://www.etsy.com/market/homestead_management_planner
- ZeraatYar greenhouse management PDF: 100 pages advertised at 69,000 toman (690,000 IRR); hydroponic PDF: 150 pages advertised at 69,000 toman. https://zeraatyar.com/pdf/کتاب-آموزش-گلخانه-داری and https://zeraatyar.com/pdf/کتاب-pdf-آموزش-کاشت-هیدروپونیک

**Limitations:** Third-party displayed prices are seller listings (may change, may be promotional); not audited transaction data. No claim is made that AGRI200 drafts yet match these competitors' completeness. Final suitability must be inspected after a finished downloadable file exists. Review periodically with actual sales, returns, support burden, and customer satisfaction, without autonomously applying promotions.

## Owner-exclusive discounts (strict)

1. Normal list price and current checkout price are identical; default discount is 0%.
2. Neither ChatGPT, the factory, agents, scheduled workflows, nor automatic marketing tools may approve/activate a coupon, crossed-out reference price, flash sale, or discount.
3. Any owner-selected promotion must be created in a **separate authenticated admin flow** with a durable approval record: owner identity, product IDs, original prices, percentage or fixed amount, exact start/end dates, reason, and audit timestamp.
4. The current price generator rejects any nonzero discount in `quote_list_price`; it cannot create or fake owner authorization. **Both live shops' future checkout/promotion code must independently enforce this permission** before production discounts can be supported. No purported owner approval should be inferred from a plain unauthenticated API parameter.
5. Zero discount by default remains true even when a completed product is eventually activated. Future marketing or a payment gateway must never silently create promotional codes.

## Production and storefront gates

A product remains PRIVATE until each independent condition has evidence:

- Full factual unique guide/tool file, source bibliography, correct locale, usable download.
- Rights verified; actual scientific review and content/nonduplication QC1000 genuinely passed.
- Owner's pre-existing 184-product rejection rework formally cleared for any affected row.
- Correct live shop currency, actual authorized payment, post-payment access and emailed receipt all tested.
- Correct list price shown to customer; zero discount unless there is a separately authenticated owner promotion.

Run `python3 scripts/agri200_fair_pricing_owner_only_20261024.py` from any directory to emit all 200 priced private drafts. Validate with `python3 -m unittest discover -s tests -p test_agri200_fair_price_policy_20261024.py -v`.
