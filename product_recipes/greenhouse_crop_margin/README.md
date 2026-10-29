# Greenhouse Crop Margin and Break-even Planner

## English standalone application — Greenhouse Economics Studio v3

For immediate offline use, download **greenhouse_economics_studio.html** and open it in a modern browser. This is a complete single-file English interface; no server, Python installation, network connection or account is required. Its independently testable calculation source is **greenhouse_engine.js**, embedded into the distributed HTML. The standalone UI includes explicit crop-cycle resource costs, multi-year investment cash flows (NPV, ROI, payback), conservative break-even thresholds, 9 stress cases, optional seeded uncertainty, CSV/JSON exports, local JSON import, printing/PDF, and session-only comparisons.

See **GREENHOUSE_ECONOMICS_STUDIO.md** for operator instructions, model exclusions and quality scope. No live pricing or yield data is fetched; sample values are synthetic and should always be replaced with independently verified local values. Passing technical tests does not establish specialist scientific quality or commercial release clearance.

A small offline calculator for comparing user-entered greenhouse growing scenarios. It estimates gross and saleable yield, sales revenue, variable and fixed costs, net margin, margin per square metre, the minimum break-even selling price, and the minimum gross yield per square metre required to cover entered costs.

## Run

Use Python 3.8 or newer:

    python calculator.py example_inputs.json
    python calculator.py example_inputs.json --json-output results.json
    python -m unittest -v test_calculator.py

All numeric assumptions must come from the user. The tool makes no price, yield, or production guarantees. It excludes taxes, financing, depreciation, seasonality, and any labor or input costs not entered in the cost fields. The result is a planning estimate, not financial or agronomic advice.

## Conservative break-even thresholds

The displayed `break_even_price_per_kg` is rounded **up** to the next 0.01 currency unit, never down to a potentially loss-making price. The new `minimum_gross_yield_kg_per_m2_to_break_even` is rounded **up** to the next 0.001 kg/m²; it assumes the entered selling price, rejection rate, area, and cost inputs remain unchanged. The related `minimum_gross_yield_reachable` flag is false and the threshold is `null` if positive costs cannot be covered because the sale price is zero or all harvest is rejected. If entered total cost is zero, the required yield is zero even with no sales. These are arithmetic thresholds, not crop-yield predictions, and neither accounts for omitted expenses.

## Input fields

area_m2, expected_yield_kg_per_m2, price_per_kg, variable_cost_per_m2, and fixed_cost_total are required. rejection_rate_percent defaults to zero. currency is a display label such as USD; no exchange rate is fetched.

## Version 2: explicit crop-season resource inputs

For a granular scenario, specify **all** of: `crop`, `season`, `water_liters_per_m2`, `water_cost_per_liter`, `energy_kwh_per_m2`, `energy_cost_per_kwh`, `labor_hours_per_m2`, `labor_cost_per_hour`, `climate_control_kwh_per_m2`, `climate_control_cost_per_kwh`, and `other_variable_cost_per_m2`. Costs are calculated separately for water, operating energy, labor, climate control, and other consumables. Do **not** include the legacy `variable_cost_per_m2` when using the explicit model; mixing them would double-count costs. Crop and season are descriptive labels and do not automatically determine yield.

You may optionally add `uncertainty` with `yield_min_kg_per_m2`, `yield_max_kg_per_m2`, `price_min_per_kg`, `price_max_per_kg`, and bounded integer `seed`. The provided baseline expected yield and price are the modes of two independent triangular distributions. The engine runs 2,000 reproducible Monte Carlo draws and reports a model-only downside frequency and 5th/50th/95th percentile net margins. These are **not** validated forecasts or market probabilities; independence and distribution assumptions must be tested against observed data by qualified specialists before commercial reliance.

Old aggregate-cost examples still run in explicit legacy mode without silently claiming that resource costs have been itemized. The calculator never claims scientific peer review, rights clearance, verified market data, owner approval, or permission for publication.
