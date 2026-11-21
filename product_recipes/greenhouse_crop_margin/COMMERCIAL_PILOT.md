# F28 — Greenhouse Margin & Break-even Lab (private pilot)

## Actual deliverable

- \`greenhouse_margin_lab_pilot.html\`: one-file, responsive, accessible, **offline** interactive calculator; no backend or runtime installation needed
- Fields: production area (m²), kg/m² yield, price/kg, variable cost/m², total fixed cost, rejected harvest %, explicit currency label
- Outputs: gross and saleable kilograms, revenue, total costs, margin, margin per m², break-even selling price; undefined when there is no saleable yield
- Sensitivity: 3 yield multipliers × 3 price multipliers = 9 stress scenarios, holding costs constant
- CSV download, printing, phone-friendly layout, no remote APIs, no telemetry, no checkout

## Source and model scope

The algebra mirrors the existing standard-library \`calculator.py\` in this product recipe. Illustrative starting values are synthetic and not market data. Model equations:

\`\`\`
gross_kg = area_m2 * yield_kg_m2
saleable_kg = gross_kg * (1 - rejected_percent / 100)
revenue = saleable_kg * unit_price
cost = area_m2 * variable_cost_m2 + fixed_cost
margin = revenue - cost
break_even_price_per_kg = cost / saleable_kg  [only when saleable_kg > 0]
\`\`\`

Stress-test revenues adjust saleable kilograms by -20%, 0%, +20% and realized price by -10%, 0%, +10%; costs remain fixed. This does **not** model crop yield risk, market demand, financing, depreciation, tax, transport, seasonal variability, constraints on greenhouse management, or unentered labor/energy costs.

## Verification

Technical validation: \`python -m unittest -v tests.test_greenhouse_margin_lab_pilot\` (from repository root). Mathematical acceptance fixture: area=100, yield=10, price=3, variable cost=5, fixed cost=500, rejection=10 -> gross 1,000 kg; saleable 900 kg; revenue 2,700; total cost 1,000; margin 1,700; break-even 1.111... per kg. Negative cases: zero area, negative price, rejection >100%, nonnumeric/nonfinite values, and no-saleable-yield case. Unit tests are not proof of browser usability, agronomic validity, accessibility conformance, commercial viability or independent expert review.

## Commercial release gates — **all closed unless independently evidenced**

1. Real independent technical and user-experience browser tests on Android, iOS and desktop (including CSV).
2. Human expert review of accounting correctness, disclaimers, interpretation and product usefulness.
3. Item-by-item rights and provenance record for source, design, dependencies and any packaged assets; owner-specific written approval for licensing. Do not infer legal clearance from Git commit history or a self-declaration.
4. Proposed price, what buyers receive, support, version/update commitment, refund/tax policy and final SKU approved by owner.
5. Isolated staging checkout and authenticated payment-provider receipt verification for each destination; exact settlement beneficiary identity verified; entitlement and re-download tested. Bank Shahr and crypto settlement are **not interchangeable**.
6. Nonzero backup/restore evidence, product hash readback, checksum-validated buyer download, security checks and public-site smoke test.

**State:** PRIVATE PRODUCT CANDIDATE / NOT FOR LIVE SALE. Do not deploy to \`zomorodmelal.ir\` or \`mojplaywin.com\`, activate payment, or represent this product as commercially approved until all six gates have evidence and the owner approves publication. This pilot does not modify existing products, old pages, infrastructure secrets or site data.

## Next production candidates

- F04: specialist agricultural research report whose citations and scientific review can be traced
- F14: browser game with measured actual playability, mobile input QA and original asset licensing
- F28: after this pilot, irrigation-economic planner with crop/season-specific limitations and exportable models

Production selection prioritizes **usable outputs + repeatable QA**, not workflow or agent counts.
