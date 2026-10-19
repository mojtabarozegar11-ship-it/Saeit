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
