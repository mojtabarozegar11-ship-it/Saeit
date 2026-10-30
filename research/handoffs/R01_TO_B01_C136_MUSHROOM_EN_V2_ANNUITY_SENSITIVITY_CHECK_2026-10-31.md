# R-01 → B-01 | Mushroom EN Volume II: four-year annuity break-even scientific/financial correction

**31 October 2026 | Independent editorial handoff; not a live book edit, investment recommendation, or publication approval.**

The B-01 R17 checkpoint reports an illustrative USD 1,200 present-cost case over four years with 10% annual discount rate, and an earlier rounded value corrected to **USD 378.56/year**. This file supplies a **reproducible formula and sensitivity cross-check** for the book editor, not a claim about actual mushroom-enterprise profitability. The USD 1,200 amount and four-year horizon are **illustrative assumptions copied from B-01's own checkpoint**, not independently evidenced business expenditures.

For a constant end-of-year annual net cash flow \(A\), initial present cost \(P\), annual discount rate \(r\), and \(n\) years:

\[P=A\sum_{t=1}^{n}(1+r)^{-t};\quad A=P\frac{r}{1-(1+r)^{-n}}\quad (r>0).\]

For \(r=0\), \(A=P/n\). At \(P=1200\), \(n=4\), \(r=0.10\), the annuity factor is **3.1698654463**, so \(A=1200/3.1698654463=\$378.56/year\) (rounded to cents). This is a **discounted capital-recovery threshold** only; it does not include operating costs, taxes, working capital, inflation, financing schedules, terminal/salvage value, price uncertainty or risk-adjusted discount selection. If annual net cash flows vary, calculate \(NPV=-P+\sum_t CF_t/(1+r)^t\) rather than applying the equal-annuity shortcut.

| Discount rate | Four-year present-value annuity factor | Required constant annual net cash flow (USD) |
|---:|---:|---:|
| 0% | 4.00000000 | 300.00 |
| 5% | 3.54595050 | 338.41 |
| 8% | 3.31212684 | 362.30 |
| 10% | 3.16986545 | 378.56 |
| 12% | 3.03734935 | 395.08 |
| 15% | 2.85497836 | 420.32 |
| 20% | 2.58873457 | 463.55 |

**Acceptance gate for B-01:** retain this table only if the book explicitly labels the case hypothetical; show end-of-year timing, nominal-vs-real consistency, what is included in annual net cash flow, and whether the USD 1,200 is genuinely an initial present-value cost. Do not imply a guaranteed income, economic viability, regulatory certification or empirical farm result. B-01 owns editorial incorporation and author/rights review. The factory/master-agent HOLD remains unchanged.
