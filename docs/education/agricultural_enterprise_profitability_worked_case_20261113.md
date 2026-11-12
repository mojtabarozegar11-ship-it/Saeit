# Agricultural Enterprise Profitability: A Reproducible Decision Case

**Original teaching case | English | 13 November 2026 | NOT a farm survey or a customer quotation**

## Decision and assumptions

A manager is considering a one-hectare seasonal crop. All numbers below are *synthetic assumptions* in USD for teaching purposes; they do not describe any actual farm, observed market, or forecast. The crop is assumed to be sold entirely in one season, with no inventory change, VAT, borrowing, subsidy, or tax. Revenue is calculated from marketable (not harvested) yield.

| Input | Symbol | Base case | Unit |
|---|---|---:|---|
| Harvested yield | H | 12,000 | kg/ha |
| Marketable share | m | 0.90 | proportion |
| Farm-gate price | P | 0.65 | USD/kg |
| Seed and planting | C1 | 800 | USD/ha |
| Fertilizer and crop protection | C2 | 1,100 | USD/ha |
| Irrigation and energy | C3 | 650 | USD/ha |
| Hired labour | C4 | 1,400 | USD/ha |
| Harvest and packing | C5 | 900 | USD/ha |
| Land rent | F1 | 1,000 | USD/ha |
| Depreciation | F2 | 450 | USD/ha |
| Allocated overhead | F3 | 300 | USD/ha |

Variable costs are C1+C2+C3+C4+C5 = **4,850 USD/ha**. Fixed costs are F1+F2+F3 = **1,750 USD/ha**. Total economic accounting cost is **6,600 USD/ha**. Marketable yield is H × m = **10,800 kg/ha**. Gross revenue is H × m × P = **7,020 USD/ha**. Contribution margin is 7,020 − 4,850 = **2,170 USD/ha**. Operating profit after the specified fixed costs is **420 USD/ha**, equivalent to a **5.98%** operating margin on sales. These values exclude financing, tax and the opportunity cost of the owner's management unless already embedded in the stated cost items.

## Break-even and sensitivity

At the assumed marketable share and price, break-even harvested yield is total cost / (m × P) = 6,600 / (0.90 × 0.65) = **11,282.05 kg/ha**. At the assumed harvested yield, break-even farm-gate price is 6,600 / (12,000 × 0.90) = **0.6111 USD/kg**. Both results assume costs do not change with yield or price within the examined range, an assumption that must be relaxed for operational decisions.

| Scenario | Harvested kg/ha | Marketable share | Price USD/kg | Revenue USD/ha | Profit USD/ha |
|---|---:|---:|---:|---:|---:|
| Low price | 12,000 | 0.90 | 0.55 | 5,940 | −660 |
| Base | 12,000 | 0.90 | 0.65 | 7,020 | 420 |
| High price | 12,000 | 0.90 | 0.75 | 8,100 | 1,500 |
| Lower marketable yield | 12,000 | 0.80 | 0.65 | 6,240 | −360 |
| Lower harvest | 10,000 | 0.90 | 0.65 | 5,850 | −750 |
| Higher harvest | 14,000 | 0.90 | 0.65 | 8,190 | 1,590 |

For the price scenarios, each 0.10 USD/kg change in price changes profit by 1,080 USD/ha. A 10-percentage-point change in marketable share changes revenue by 780 USD/ha at the base yield and price. This highlights the importance of grading losses, quality assurance and the marketing channel, not merely agronomic yield.

## Capital, cash flow and decision limits

Depreciation (450 USD) is a non-cash accounting charge, while capital expenditure and loan principal are cash movements not represented in the table. Therefore the 420 USD profit is **not** free cash flow. A bankable cash-flow estimate must separately schedule working capital, receivables, inventory, capital spending, debt service and taxes. If the farm is owner-operated, unpaid family labour and land opportunity cost must be valued explicitly to calculate economic profit.

The base-case surplus is thin: a 6.0% price decline from 0.65 to about 0.611 USD/kg eliminates the stated profit, holding everything else constant. A manager should not approve investment on the base case alone. Obtain signed local input quotations, actual grade-out records, reliable yield distributions, sales terms, water availability, insurance terms and a multi-season stochastic analysis. For a project with upfront investment, calculate discounted net present value using time-indexed incremental cash flows and a defensible risk-adjusted discount rate; the one-season operating-profit calculation is not a substitute.

## Quality-control equations and reproducibility

The following pure Python assertions reproduce the case without third-party packages:

```python
h, m, p = 12000, 0.90, 0.65
variable = sum([800, 1100, 650, 1400, 900])
fixed = sum([1000, 450, 300])
cost = variable + fixed
revenue = h * m * p
profit = revenue - cost
assert variable == 4850 and fixed == 1750 and cost == 6600
assert abs(revenue - 7020) < 1e-9 and abs(profit - 420) < 1e-9
assert abs(cost / (m*p) - 11282.051282051281) < 1e-6
assert abs(cost / (h*m) - 0.6111111111111112) < 1e-9
for hh, mm, pp, expected in [
    (12000, .90, .55, -660), (12000, .90, .65, 420),
    (12000, .90, .75, 1500), (12000, .80, .65, -360),
    (10000, .90, .65, -750), (14000, .90, .65, 1590),
]:
    assert abs(hh*mm*pp - cost - expected) < 1e-8
```

## Suggested scholarly foundations (bibliographic references, not data sources)

- Kay, R. D., Edwards, W. M., and Duffy, P. A. *Farm Management*, 8th ed., McGraw-Hill, 2015. Farm enterprise budgets, managerial decisions and financial analysis.
- Gittinger, J. P. *Economic Analysis of Agricultural Projects*, 2nd ed., Johns Hopkins University Press for the World Bank, 1982. Incremental project costs and benefits, shadow pricing and project appraisal.
- FAO, *Farm Management Extension Guide* series. Farm planning and enterprise budgeting methods. Consult the relevant FAO publication for the target region before application.

**Rights and release:** This original worked example may be reviewed for inclusion in an owner-approved teaching product. It is not a completed paid SKU, proof of rights for third-party materials, a published web page, or evidence of a received payment.
