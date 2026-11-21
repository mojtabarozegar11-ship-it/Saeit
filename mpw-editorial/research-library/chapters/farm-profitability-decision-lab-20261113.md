# Farm Profitability Decision Laboratory: Enterprise Budgets, Liquidity, and Risk
**Original teaching chapter — 13 November 2026.** Language: English. Status: editorial draft, not published, not a financial recommendation. All numbers are hypothetical and in USD.

## Learning outcomes
A doctoral student completing this chapter should be able to distinguish economic profit from cash surplus; build a reproducible enterprise budget; evaluate an irrigation investment under a binding cash constraint; test the robustness of the result to price and yield shocks; and explain why an apparently profitable enterprise may still fail to meet debt service.

## 1. Define the decision unit before computing returns
An enterprise budget describes one production activity over a stated area and period. The analyst must specify the crop, hectares, marketing unit, production season, ownership of land, accounting treatment of family labor, and whether the decision is marginal or a full-farm redesign. Mixing a one-hectare yield with whole-farm machinery costs produces a meaningless margin. Economic analysis values owner-supplied resources at their opportunity costs; a cash-flow analysis instead records actual payments and receipts. Both are necessary, but they answer different questions.

For an annual one-hectare crop enterprise, let `Q` be marketable tonnes, `P` the farm-gate price per tonne, `V` cash variable costs, `F_c` cash fixed costs, and `F_n` noncash opportunity costs. Gross revenue is `R = P × Q`. Gross margin is `GM = R − V`. Operating cash surplus before financing is `C = R − V − F_c`. Economic profit is `π = C − F_n`. Debt principal repayments are cash obligations but not accounting production costs; interest is a financing expense and should be treated consistently with the chosen valuation framework.

## 2. Reproducible worked example
Assume marketable output of 8.0 tonnes per hectare and a farm-gate price of $450 per tonne. Cash variable costs are seed $240, fertilizer $380, water and energy $310, hired labor $520, packaging $280, and transport $190. Annual cash fixed overhead is $350. The opportunity cost of owned land is $500 and of family labor $400.

| Item | USD per hectare |
|---|---:|
| Revenue: 8.0 × 450 | 3,600 |
| Seed | 240 |
| Fertilizer | 380 |
| Water and energy | 310 |
| Hired labor | 520 |
| Packaging | 280 |
| Transport | 190 |
| **Total variable cash cost** | **1,920** |
| **Gross margin** | **1,680** |
| Fixed cash overhead | 350 |
| **Operating cash surplus** | **1,330** |
| Land opportunity cost | 500 |
| Family labor opportunity cost | 400 |
| **Economic profit** | **430** |

Reproduction: `240+380+310+520+280+190 = 1,920`; `3,600−1,920 = 1,680`; `1,680−350 = 1,330`; `1,330−500−400 = 430`. The cash break-even price is `(1,920+350)/8 = $283.75/t`; the economic break-even price is `(1,920+350+900)/8 = $396.25/t`. These prices assume fixed costs and output remain unchanged; neither is a forecast.

## 3. Sensitivity and correlated shocks
Holding the cost budget fixed, at 7.0 tonnes and $400/t, revenue is $2,800 and economic profit is `2,800−3,170 = −$370`. At 9.0 tonnes and $500/t, revenue is $4,500 and economic profit is $1,330. The $3,170 economic-cost total includes both paid and imputed costs. A simplistic independent price/yield sensitivity grid can understate risk: regional bumper harvests may simultaneously raise yields and depress farm-gate prices. A defensible scenario design specifies joint price–yield outcomes, probabilities only where supported by data, and the source and date of every observation. Do not invent probabilities and present them as measured.

## 4. Irrigation investment under a liquidity constraint
Suppose a proposed irrigation upgrade costs $1,800 now, has a three-year service life, no residual value, and increases *annual net operating cash flow* by $760 after incremental maintenance, energy, and labor. At an assumed annual discount rate of 10%, the net present value is:
`NPV = −1800 + 760/(1.10) + 760/(1.10)^2 + 760/(1.10)^3`.
The three discount factors are approximately 0.90909, 0.82645, and 0.75131. Therefore `NPV ≈ −1800 + 760 × 2.48685 = +$90.01`. This is a marginal result, not a guarantee: a modest reduction in benefit or an increase in the discount rate can reverse the decision. The simple payback is `1800/760 ≈ 2.37 years`, but payback ignores the time value of money and benefits beyond the cutoff.

A positive NPV does not demonstrate affordability. If only $600 is available at planting and no legally available financing exists, the $1,800 outlay cannot be made merely because discounted benefits exceed cost. A financing model must separately test minimum monthly cash balance, timing of harvest receipts, interest, collateral, debt-service coverage, and a downside case. An analyst should never describe unavailable financing as secured.

## 5. Enterprise selection as a constrained optimization problem
With multiple crops, maximize `Σ_i π_i x_i` subject to `Σ_i a_i x_i ≤ A` (land), `Σ_i w_i x_i ≤ W` (water), `Σ_i l_i x_i ≤ L` (labor), and `Σ_i k_i x_i ≤ K` (peak working capital), with `x_i ≥ 0`. A positive margin per hectare is not enough to rank crops when water or liquidity binds. The dual value of a resource constraint measures the local improvement in the objective from one additional unit of that resource, provided the active constraint set and assumptions remain valid. For indivisible facilities, crop rotation, and fixed startup costs, use a mixed-integer model rather than forcing a continuous solution.

## 6. Data provenance and reporting protocol
Label every input as observed, contractually fixed, expert-estimated, or hypothetical. Record currency, base year, farm-gate versus retail pricing, unit conversions, missing observations, and the source of opportunity-cost assumptions. Report cash surplus, economic profit, liquidity stress, and risk separately. Do not infer a farm's true profitability from a single demonstration budget. Before client delivery, replace the hypothetical inputs with authorized farm records and independently verify the calculations.

## 7. Exercises with checkable answers
**Exercise A.** Keeping the base cost structure, find the marketable output required for zero economic profit at $450/t. **Answer:** `3,170/450 = 7.0444… tonnes`.

**Exercise B.** The irrigation upgrade yields only $680 net annually. Recompute NPV at 10%. **Answer:** `−1800 + 680×2.48685 ≈ −$108.94`; reject under the stated NPV criterion.

**Exercise C.** A buyer offers $480/t but requires $220 additional packaging and testing expense. At 8 tonnes, determine the incremental economic profit. **Answer:** additional revenue `8×30 = $240`; net change `+$20`. This excludes potential quality rejection and delayed-payment risk.

**Exercise D.** Explain why a $430 economic profit cannot be used to pay $1,500 in loan principal at harvest. **Answer:** principal requires cash; operating cash surplus is only $1,330 before debt service, and its timing may not coincide with repayment.

## References for independent study
- Food and Agriculture Organization of the United Nations (FAO), *Farm Management: A Systems Approach* (FAO Farm Systems Management Series). https://www.fao.org/
- United States Department of Agriculture, Economic Research Service, *Farm Income and Wealth Statistics*. https://www.ers.usda.gov/
- World Bank, *Agriculture and Food* sector data and methodological resources. https://www.worldbank.org/en/topic/agriculture

These are background reference portals, not claimed sources for the hypothetical figures. The example, analysis, and exercises are original educational material. Rights clearance and independent academic review remain required before commercial publication.
