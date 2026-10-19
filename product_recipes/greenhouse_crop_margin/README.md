# Greenhouse Crop Margin and Break-even Planner

A small offline calculator for comparing user-entered greenhouse growing scenarios. It estimates gross and saleable yield, sales revenue, variable and fixed costs, net margin, margin per square metre, and the break-even selling price.

## Run

Use Python 3.8 or newer:

    python calculator.py example_inputs.json
    python calculator.py example_inputs.json --json-output results.json
    python -m unittest -v test_calculator.py

All numeric assumptions must come from the user. The tool makes no price, yield, or production guarantees. It excludes taxes, financing, depreciation, seasonality, and any labor or input costs not entered in the cost fields. The result is a planning estimate, not financial or agronomic advice.

## Input fields

area_m2, expected_yield_kg_per_m2, price_per_kg, variable_cost_per_m2, and fixed_cost_total are required. rejection_rate_percent defaults to zero. currency is a display label such as USD; no exchange rate is fetched.
