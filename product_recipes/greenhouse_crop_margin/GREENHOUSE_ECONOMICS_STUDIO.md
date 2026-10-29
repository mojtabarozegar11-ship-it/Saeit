# F28 — Greenhouse Economics Studio v3.0 (English)

A self-contained offline, English-language greenhouse economic planning application.
The customer-facing file is greenhouse_economics_studio.html. Download it,
keep the .html extension and open it locally in Chrome, Edge, Firefox,
Safari or another modern browser. No Python, account, server, network access
or additional JS file is required. The separately testable engine
(greenhouse_engine.js) is embedded verbatim into the single-file HTML package.

## Economic features

- Crop, season, local region, area, yield, price and reject rate.
- Separate water, operating energy, climate energy, labor, crop inputs,
  packaging and transport costs per cycle, plus annual fixed cash overhead.
- Gross versus saleable harvest, revenue, contribution, cycle and per-square-meter
  net margins; break-even price and minimum gross yield (display rounded up).
- Initial investment, full cycles per year, planning horizon, discount rate,
  independent annual cost and revenue changes, cash flows, NPV, ROI and payback.
- Nine price/yield shock scenarios; optional 2,000 seeded triangular simulation
  using user-defined limits. The modeled loss rate is NOT a measured probability.
- Export/import JSON scenarios, a detailed CSV report (assumptions, resource costs,
  financial results and model limitations), and a separate CSV with up to 20
  locally compared scenarios. Clear the comparison without reloading. Print/save PDF.
  Invalid input clears prior financial figures to prevent stale output.
  No remote requests or trackers.
- Mobile-responsive English interface with input labels and keyboard controls.

## Technical verification

Run from repository root, with Node.js 20+ and Python 3.8+:

    node --test product_recipes/greenhouse_crop_margin/test_greenhouse_engine.js
    python -m unittest discover -s product_recipes/greenhouse_crop_margin -p 'test_calculator.py' -v

The JavaScript suite checks the same engine embedded in the self-contained
browser file, fixed economic benchmarks, 128 metamorphic scenario variants,
edge cases, input validation and model-only uncertainty consistency.

## Scope and exclusions

All shipped starting figures are illustrative; replace them with independently
verified local inputs. Crop and region labels do NOT determine agronomic yield
or market prices. No live feed or independent field validation is included.

Projection assumes identical production cycles per year and user-entered revenue
and cost escalation rates. It excludes taxes, depreciation, debt servicing,
working capital, terminal asset values, exchange-rate changes, water rights,
crop rotation, agronomic feasibility and costs not entered by the user.
This is an operational scenario calculator, not a certified forecast.

This software is usable offline for user-entered scenario analysis, but no
independent professional review, demonstrated real-customer suitability,
rights clearance, quality-1000 approval or live commerce readiness has been
established by these technical tests. Do not turn on a paid SKU or change live
payment/site systems until the separate commercial release gates have passed.

Copyright (c) 2026 Mojtaba Roozegar. All rights reserved.
