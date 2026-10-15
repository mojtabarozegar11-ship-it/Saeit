# Farm Input Procurement Quote Audit — Astra 2.0 private reference tool

This is the **second genuinely distinct source product**, separate from the orchard NPV/time-value-of-money investment audit. It compares user-supplied **procurement quotes**, full delivered costs, verified-by-operator gross-to-net units, deadlines, supplier capacity, order minimums and two arithmetic cost stress cases. It never executes purchase orders, reads a bank account, estimates a farm commodity price, recommends a verified supplier or claims buyers will pay for it.

## Zero-dependency usage (Python 3.8+)

From this folder:

```bash
python3 self_test.py
python3 procurement_audit.py --input example_synthetic.json --output /tmp/farm-procurement-private.json
python3 render_report.py --report /tmp/farm-procurement-private.json --html /tmp/farm-procurement-private.html
```

Open `/tmp/farm-procurement-private.html` locally in a browser and print to PDF if needed. The report is self-contained HTML with output text escaped, no JavaScript/CDN or web data request. Outputs use file mode 0600, refuse overwriting other files and do not upload buyer/supplier quotes. Keep user-supplied supplier information out of public GitHub.

**WARNING:** all prices, providers, dates and quotes in `example_synthetic.json` are explicitly **fictional**, suitable only for reproducible tests. Do not present them as research, customer quotes or commercial validation.

## Calculation policy

- `net_units_required` denotes the amount of usable material needed, in one uniform unit (kg, tonne, litre, piece or bag).
- `gross_order_units = max(net_units_required / (1 - waste_pct/100), minimum_order_units)`, if waste is below 100%.
- A quotation is **ineligible for arithmetic comparison** if its disclosed lead days exceed the buyer's deadline, disclosed available units are less than calculated gross requirement, waste would be >=100%, or supplier/source reference is blank.
- `material = gross_order_units × unit_price × scenario.price_multiplier`.
- `discounted_material = material × (1 - discount_pct / 100)`.
- `tax = (discounted_material + setup_flat) × tax_pct / 100`; freight is assumed untaxed. THIS IS AN EXPLICIT MODEL CONVENTION, NOT LEGAL TAX ADVICE.
- `landed_cost = discounted_material + setup_flat + tax + freight_flat × scenario.freight_multiplier`.
- `effective_cost_per_net_required_unit = landed_cost / net_units_required`.
- Base scenario is 1× price, 1× freight and 0 additional waste percentage points. Adverse scenario inputs are explicitly supplied by the buyer and **have no claimed probability**.
- If no offer meets disclosed deadline/capacity/traceability constraints, the result is `all_offers_ineligible=true` with no cheapest eligible supplier.
- The minimum cost supplier is a **calculation under provisional inputs**, NOT an independently verified recommendation. Source and quote labels remain self-reported.
- Does NOT model supplier financial reliability, licenses, actual delivered quality, freight insurance, currency conversion, fluctuating duties, staggered deliveries, partial shipments, after-sale support, lot-level safety certification or ownership.

## Independent verification before any commercial publication

At least one subject expert must verify the procurement formulas and business assumptions against actual transactions; at least three users need to demonstrate the tool solves a real pain point that free spreadsheet alternatives do not already solve. Demand, licensing, customer support, accessibility and public security require separate signoff. No commercial quality score is claimed; rights and owner release remain blocked. A functioning CLI and printable report alone do NOT establish sellable quality.

**Safety contract:** this is private, offline, synthetic-first. No network calls, financial transactions, invoices, API tokens, cPanel or storefront deployment.


## Extended private R&D: whole-pack quote normalization

Farm suppliers often price one 20 kg sack, while another prices one kilogram.
Comparing the two price numbers without conversion is wrong. The audit now
supports an optional *whole pack* quote without changing any existing input:
add both the following fields to exactly one offer:

    "pricing_basis": "per_pack",
    "pack_size_base_units": "20"

In a whole-pack quote, existing field unit_price means **price per indivisible
pack**. The pack contains pack_size_base_units of the report's top-level unit.
Both fields are mandatory together; leaving them out preserves the historical
price-per-base-unit quotation formula. Inventory and minimum orders remain in
the top-level base unit.

Using exact decimal arithmetic, the engine:
1. Computes gross-needed base units after disclosed waste and minimum-order
   constraints.
2. Rounds the gross requirement **up to a whole number of packs**, never a
   fractional pack.
3. Checks the supplier's declared capacity against the **actually purchased
   units after rounding**, not against the smaller pre-rounded requirement.
4. Bills material using the number of packs multiplied by price per pack.
   The disclosed discount, setup, freight and tax conventions still apply.
5. Displays normalized indicative price per base unit, pack count, base units
   purchased, usable units and surplus usable units. Surplus is not deemed
   returnable, resellable or a financial credit.
6. Reports the arithmetic landed-cost gap to the next eligible offer as
   **not realized savings** or independent supplier verification.

### Reproducible synthetic scenario

A buyer needs 100 kg usable input, assumes 5% waste and receives a fictional
quote of USD 90 per 20 kg sack, 5% material discount, no tax or setup and USD 45
freight. Pre-pack gross requirement is about 105.26 kg. Purchasing 6 whole
sacks yields 120 kg gross, 114 kg usable and 14 kg surplus. Landed estimate is
6 x 90 x 0.95 + 45 = **USD 558.00**. Dividing 90 by 20 gives an indicative
USD 4.50/kg quote price but does not establish the final effective procurement
cost. Tests compare the final totals and reject inadequate capacity.

These are fictional test inputs. The engine still does not independently
verify quote authenticity, quality equivalence, supply reliability, user demand,
tax jurisdictions, packaging returns or full contractual landed costs. No
automatic purchase, fabricated quality score, artificial original price or
commercial-release authorization is added.
