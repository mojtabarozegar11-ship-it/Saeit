# Position sizing and drawdown: a practical simulated-trading guide

> **Moj Prop educational resource** · Simulated trading examples only. This is not investment advice, a guarantee of profit, a challenge pass, or a reward.

A trading simulation is useful when it measures decisions rather than rewards a lucky outcome. Start by fixing a risk budget before choosing quantity, and record both planned and realized losses. A virtual balance is not customer money or a real brokerage account.

## Calculate the planned risk
Suppose the practice balance is $1,000 and an exercise uses a 3% per-trade risk ceiling. That is $30 of planned risk. If a hypothetical instrument has a $2 difference between entry and stop per unit, the maximum theoretical position is 15 units before costs. A more conservative quantity leaves room for estimated fees and adverse price movement. A stop is not a guarantee of execution at the chosen price, even in models that approximate real markets.

Use three separate budgets rather than treating each order in isolation:
- Individual position: planned loss at invalidation.
- Aggregate open positions: sum of planned losses, paying attention to overlapping exposure.
- Daily loss: track the account value and remaining daily capacity using the applicable evaluation definition.

With a $1,000 example, a 4% aggregate ceiling represents $40, so a second trade with another $30 of planned risk would exceed that ceiling while the first is open. A 6% daily ceiling would represent $60 if the relevant reference balance is $1,000. Always use the actual current rules for thresholds, reference balances and timing; this numerical illustration does not establish how a challenge engine calculates them.

## Keep a risk journal
Record the instrument, entry assumption, stop, quantity, planned maximum loss, fees, exit and reason for closing. Include the time and the remaining risk budget. Never upload passwords or wallet recovery phrases to a journal.

## Review the experiment
Compare planned and realized risk. Note correlated positions and slippage assumptions. A disciplined decision to skip a trade can be more informative than an unusually large gain. Simulated outcomes do not establish future real performance.

Further reading: [Moj Prop rules](https://mojprop.top/moj-prop/rules/?utm_source=github&utm_medium=organic_referral&utm_campaign=risk_education), [free practice journal and Starter 30 information](https://mojprop.top/moj-prop/starter-30-trx/?utm_source=github&utm_medium=organic_referral&utm_campaign=risk_education). Review current eligibility and checkout conditions before deciding. No profit or pass is promised.

---

[All Moj Prop educational guides](./README.md) · [Moj Prop main site](https://mojprop.top/moj-prop/?utm_source=github&utm_medium=organic_referral&utm_campaign=education_library)
