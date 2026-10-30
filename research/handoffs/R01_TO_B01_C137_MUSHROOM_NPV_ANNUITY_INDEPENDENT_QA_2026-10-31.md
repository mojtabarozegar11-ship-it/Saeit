# R-01 → B-01 C137 — Mushroom Volume II four-year cash-flow / annuity QA insert
Date: 2026-10-31 | Owner: R research handoff to B book owner | Stage: READY_FOR_REVIEW; not inserted or published
Based on B-01 R18 checkpoint: volume contains four-year NPV examples and a separate annuity illustration. The private book source was **not** accessible for a line-by-line comparison in this review. This is a ready-to-use independent calculation and disclosure appendix, **not** a claim that the book's existing numbers were verified.

## Explicitly hypothetical worked case (not field data)
Currency: illustrative units (IU), not CAD/IRR/USD. Initial outlay at t=0: 100,000 IU. End-of-year operating net cash flows t1=28,000; t2=32,000; t3=35,000; t4=36,000 IU. Additional salvage cash receipt at t4: 10,000 IU. Discount rate baseline 12% per year, annual compounding. No taxes, financing, inflation, working capital, replacement investment, grants or terminal liabilities included. The hypothetical example is **not** a commercial profitability forecast.

NPV(r) = −100000 + 28000/(1+r) + 32000/(1+r)^2 + 35000/(1+r)^3 + (36000+10000)/(1+r)^4.

| Annual discount rate | Base NPV (IU) | NPV with operating flows 10% lower (IU), salvage unchanged |
|---|---:|---:|
| 8% | 14956.27 | 4195.67 |
| 12% | 4656.34 | -5173.77 |
| 16% | -4252.45 | -13274.91 |

At 12% and four periods, the **capital recovery annuity** for a 100,000 IU principal is A=P×r/[1−(1+r)^−4] = **32923.44 IU/year**. This is a financing/capital-recovery equivalent, **not** the annual equivalent of the project NPV, and must not be added to NPV as an extra cost if initial outlay is already counted. Equivalent annual net worth (EAW) for the base NPV, if desired, equals NPV×r/[1−(1+r)^−4] = **1533.03 IU/year**; label this separately.

## Reviewer acceptance tests
- All cash flows must be at end of the declared periods; no mixing t0, t1 or monthly discounting.
- Specify nominal versus real rates and inflation convention; cash flow and discount rate must match.
- Separate gross sales, operating expense, taxes, financing, capital expenditure, working capital and salvage; avoid double counting depreciation as cash outflow.
- Show the formula, inputs, currency, sensitivity assumptions and reproducible outputs; report missing market quotations explicitly.
- A positive illustrative NPV **does not** prove an actual mushroom farm is profitable, financeable or safe.
- No empirical yield, biological loss rate, price, food-safety or legal compliance claims are supported by this hypothetical arithmetic.

**Handoff:** B-01 may compare this independent worked case to the actual private manuscript, correct any formula/units and retain the hypothetical label. Only B owner may merge or publish after qualified review and author approval. No B source file was edited.
