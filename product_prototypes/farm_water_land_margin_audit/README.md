# Farm Water & Land Margin Audit — third independent Astra V2 prototype

**Status:** private quantitative R&D reference, not a certified agronomic or financial advisory product. All crop inputs in `example_synthetic.json` are fictional test values, not measured yields, quotes, crop requirements or market prices.

This tool is different from **Orchard Investment Decision Audit** (multiyear time-value investment) and **Farm Input Procurement Quote Audit** (supplier acquisition costs). It implements a third specialized mathematical task: optimal continuous allocation of agricultural land and irrigation water across 2–5 user-defined crops with crop-specific maximum hectares and user-entered gross margins.

## Run offline (Python 3.8+, no dependencies)

```bash
python3 self_test.py
python3 water_margin_audit.py --input example_synthetic.json --output /tmp/water-margin-private.json
python3 render_report.py --report /tmp/water-margin-private.json --html /tmp/water-margin-private.html
```

Open the HTML on your own computer/mobile, where you transferred it privately, and choose Print → PDF if needed. Input files and private reports never leave the machine. New outputs are chmod 0600; the tool refuses to overwrite files.

## Mathematical scope, objective and exactness

For activities `i`, select fractional hectares `x_i >= 0`. Optimize the operator-supplied total gross margin `sum((revenue_i - variable_cost_i)*x_i)` subject to:

- `x_i <= maximum_hectares_i`
- `sum(x_i) <= land_hectares`
- `sum(water_per_hectare_i*x_i) <= water_m3_available`

The reference engine enumerates all feasible extreme-point candidates with at most **two non-bound crop variables** (because there are two pooled resource constraints); it uses exact Python Decimal input arithmetic, not third-party LP solvers, untrusted LLM guesses or fabricated commodity information. Positive gross margin is **not** complete profit. Real crops require rotations, permits, aquifer withdrawals, yield-response functions, soil, climate, equipment, labor, ecological and farm-specific constraints. These are not modeled.

Second scenario uses the explicitly supplied `drought_water_fraction`, e.g. 0.65 = 65% of baseline availability. No rainfall or shortage is predicted. Each output shows planted hectares, computed crop gross-margin contribution, water used, unused land/water, candidate vertices checked, warnings and reproducible input SHA-256. The report cannot prove actual agriculture performance.

**Limitations:** maximum 5 crops, independent fractional areas, no minimum contract acreage, no transport/storage constraints, no nonlinear yields or crop rotations. A professional should check all field constraints before farm decisions. The presence of a mathematically optimal solution **under this simplified model** does NOT mean a physically or legally admissible field plan.

## Water-allowance sensitivity frontier (new)

The audit now resolves the exact same LP at **0%, 25%, 50%, 75% and 100%** of the operator-supplied baseline water budget. The printable HTML report includes a five-row decision table with optimal gross margins and the **average incremental gross-margin gain per additional cubic metre of *allowed* water** between adjacent rows:

`interval_gain_per_m3 = (optimal_margin_at_more_water - optimal_margin_at_less_water) / (more_allowed_m3 - less_allowed_m3)`.

This is a **finite-interval sensitivity calculation**, **not** an infinitesimal dual shadow price, quoted market water tariff, verified marginal crop yield or proof that extra water can be legally or physically supplied. If total baseline water equals zero, the interval value is `null` (undefined), not a manufactured zero-value quote. Currency follows the user-entered currency; no external exchange rate is inferred.

All five optimizations use the original unrounded Decimal input and each has its own feasible land/water allocation. The reported sensitivity is rounded to six decimal places only for display; the stored mathematical optimum is calculated before that rounding. The existing explicit drought scenario remains a separate sixth analysis when its percentage does not coincide with a frontier point. The output still has `quality_score=null`, `sale_ready=false` and zero payment/publication authority.

**Research-method precedent, not evidence of product novelty:** FAO describes linear programming of cropping plans to maximize gross margin under water constraints: https://www.fao.org/4/w4367e/w4367e06.htm . FAO also distinguishes economic marginal value and physical irrigation efficiency: https://www.fao.org/4/y5582e/y5582e06.htm . Existing university alternatives remain direct competitors. No user-level demand validation is implied by these references.

## Proven methods and real competition

- FAO's *Economic valuation of water resources in agriculture* presents resource-allocation efficiency as one consideration alongside environmental/equity limits: https://www.fao.org/4/y5582e/y5582e06.htm
- University of California Davis already provides a free Water-Land-Crop Allocation Optimization Planning Tool with crop-rotation/SGMA scenario work: https://agwater.ucdavis.edu/tools
- Kansas State University offers its Crop Water Allocator: https://milab.ksu.edu/crop-water-allocator

Therefore it is FALSE to assert a novel overall problem category, unmet demand, superiority to free alternatives or any justified retail price. This implementation is an independently written simple transparent benchmark; software copyright and independent quality review must be addressed before distribution.

**Commercial release blockers:** independent agronomic and farm-economics review, field input provenance, verified source rights/licensing, independent user study, competitor advantage, accessibility review, product support and legitimate willingness-to-pay evidence. Quality score deliberately `null`, public listing false, sales false.

The template data are fictional. Publishing sample numbers as live agricultural research or market quotes is prohibited.
