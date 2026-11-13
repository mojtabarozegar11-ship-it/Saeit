# Farm Investment Decision Workbook: Cash Flow, Risk and Decision Rules
**Original educational case | English | 13 November 2026 | NOT a customer-specific appraisal**

## Scope and buyer use
This self-contained learning unit teaches an agricultural entrepreneur to evaluate a proposed irrigation upgrade. It is a reusable instructional workbook, not a claim about a particular farm. All figures are **hypothetical**, denominated in USD at constant purchasing power; the numbers are not observations, quotations, or investment advice. A real engagement requires signed source records, local tax and water-rights checks, and documented assumptions.

### Decision being evaluated
A farm considers a five-year irrigation equipment investment. Initial cash outlay at time zero is $24,000. Expected incremental annual farm-gate sales are $15,000. Incremental variable expenses (power, labor, repairs, and consumables) are $6,500 per year. The project also incurs $1,000 annually for incremental maintenance and administration. At the end of year five, net salvage proceeds are $3,000, assuming lawful disposal and no additional taxes. The real discount rate is 10% annually. No subsidy, debt financing, tax shield, or working-capital release is assumed. The comparison is **incremental**: with the upgrade minus without the upgrade.

| Input | Symbol | Hypothetical value | Unit |
|---|---|---:|---|
| Initial outlay | I₀ | 24,000 | USD at t=0 |
| Additional annual sales | R | 15,000 | USD/year |
| Additional annual variable costs | V | 6,500 | USD/year |
| Additional annual fixed costs | F | 1,000 | USD/year |
| Net terminal salvage | S | 3,000 | USD in year 5 |
| Analysis horizon | n | 5 | years |
| Real discount rate | r | 0.10 | per year |

## 1. Incremental operating cash flow
Annual operating contribution is R − V − F = 15,000 − 6,500 − 1,000 = **$7,500**. This is not accounting profit: depreciation and income tax have deliberately been excluded. If those are material, prepare a separate after-tax schedule rather than mixing pre-tax cash flow with an after-tax discount rate.

| Year | Incremental operating cash flow | Salvage | Total cash flow |
|---:|---:|---:|---:|
| 0 | 0 | 0 | −24,000 |
| 1 | 7,500 | 0 | 7,500 |
| 2 | 7,500 | 0 | 7,500 |
| 3 | 7,500 | 0 | 7,500 |
| 4 | 7,500 | 0 | 7,500 |
| 5 | 7,500 | 3,000 | 10,500 |

## 2. Discounted-cash-flow decision
For end-of-year receipts:
```
NPV = -I0 + sum(CF_t / (1+r)^t for t=1..5)
PV_annuity_factor = (1-(1+r)^(-5))/r
NPV = -24000 + 7500*PV_annuity_factor + 3000/(1.10)^5
```
The five-year annuity factor at 10% is approximately **3.790787**. Hence PV of operations is **$28,430.90**, PV of salvage **$1,862.76**, and **NPV ≈ +$6,293.66** (rounding to cents). The benefit–cost comparison must use the same time basis and distinguish gross revenue from net benefits. The NPV rule says accept only if the assumptions are credible, the investment is legally feasible, and the farm can bear the downside. A positive NPV is not a liquidity guarantee.

Simple payback ignoring discounting and salvage is 24,000 / 7,500 = **3.20 years**. This measure omits the time value of money and post-payback cash flows; it is not a substitute for NPV.

## 3. Break-even operating contribution
The minimum constant annual operating cash flow that yields NPV=0 is:
```
CF_break_even = (I0 - S/(1+r)^n) / PV_annuity_factor
```
Numerically this is approximately **$5,839.60 per year**. At the stated $7,500 expected contribution, the project has roughly **$1,660 per year** of contribution headroom before NPV turns negative, assuming unchanged salvage and discount rate.

## 4. Stress scenarios: independent changes, not probability forecasts
Keep the same horizon, discount rate, initial outlay, and salvage unless a row explicitly varies them.

| Scenario | Annual operating cash flow | Approximate NPV | Interpretation |
|---|---:|---:|---|
| Base case | $7,500 | +$6,294 | Conditional economic surplus |
| Revenue shortfall of $2,000/year | $5,500 | −$1,288 | Do not proceed on this scenario alone |
| Extra energy and labor cost of $1,000/year | $6,500 | +$2,503 | Reduced but positive surplus |
| Both adverse changes together | $4,500 | −$5,079 | Material downside |
| Annual contribution +$1,500 | $9,000 | +$11,980 | Upside contingent on realized gains |

These are deterministic sensitivities, **not** confidence intervals. A field appraisal should document yield, water allocation, electricity tariffs, crop prices, machine availability, and whether adverse factors are correlated. Do not attach invented probabilities to the rows.

## 5. Liquidity and financing are separate tests
Even a positive NPV project can fail if the farm cannot fund $24,000 at t=0 or cover seasonal cash gaps. Before approval, produce a monthly cash budget showing crop receipts, planting and harvest costs, irrigation power bills, debt service, taxes, and a liquidity reserve. If debt is introduced, calculate debt-service coverage using actual repayment dates; do not count borrowed principal as revenue or double-count interest when discounting project cash flows.

## 6. Field data intake for a commissioned report
The analyst should request: (a) field area and crop calendar; (b) dated production and sales invoices; (c) water rights and metered consumption; (d) equipment supplier quotation and warranty; (e) labor and energy tariffs; (f) installation and downtime estimate; (g) tax treatment; (h) salvage assumptions; (i) real or nominal discount-rate basis; (j) management's worst acceptable cash shortfall. Each input must carry a source, date, unit, and confidence rating. If documents are unavailable, mark the item **unknown**, not zero.

## 7. Reproducible reference calculation
Python 3 standard library only:
```python
def npv(initial, annual, salvage, years, rate):
    if years <= 0 or rate <= -1:
        raise ValueError("Invalid horizon or discount rate")
    return -initial + sum(annual / (1 + rate) ** t for t in range(1, years + 1)) + salvage / (1 + rate) ** years

cases = {"base": 7500, "revenue_down": 5500, "cost_up": 6500,
         "combined": 4500, "upside": 9000}
for name, annual in cases.items():
    print(name, round(npv(24000, annual, 3000, 5, 0.10), 2))
assert npv(24000, 7500, 3000, 5, 0.10) > 0
assert npv(24000, 4500, 3000, 5, 0.10) < 0
```
All calculations are transparent and may be independently recomputed. Rounding differences below $2 arise from displayed factors. A future paid report must include an actual client data annex, evidence trail, and a reviewed decision memo.

## 8. Rights, limitations and delivery
This instructional text and its worked example were newly authored for the project; it does not reproduce a third-party book. Its publication or sale remains subject to the owner's explicit authorization and final editorial review. No assertion is made that any specific equipment will save water, raise yields, or generate the stated cash flows.

### Further reading and methodological anchors
- FAO, *Farm Management Extension Guide* series: farm budgeting, record keeping, and enterprise analysis (consult the specific edition before a client citation).
- USDA Economic Research Service, farm income and costs documentation: https://www.ers.usda.gov/ (methodological context; not the source of this fictional example).
- World Bank, *Economic Analysis of Investment Operations*: discounted cash flow and sensitivity analysis (verify edition and project-specific applicability before publication).
