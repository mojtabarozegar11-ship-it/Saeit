# MojTrade OMEGA X — commercially accountable evidence gate (XAUUSD)

## Scope actually implemented

`trading/mojtrade_costed_oos.py` is a pure-Python *research* evaluator
for strictly chronological **broker bid/ask OHLC** of XAUUSD at M1, M5, or
M10. It evaluates 4 versioned candidates (EMA 8/21, EMA 13/34,
20-bar breakout, and 20-bar mean reversion), includes explicit per-ounce
commission and slippage, charges bid/ask spread through fill prices,
simulates conservative gap stops, and fills entries **only at the next bar
open**. One position at a time. Never sends an order.

The first 60% of the price history is the training region. After a
40-bar / maximum-hold embargo, the remaining bars are a **single
previously untouched temporal holdout**. A positive holdout is an
*unverified historical candidate*, not scientific proof of true alpha,
statistical significance, or commercial readiness. A proper repeated
walk-forward/CPCV protocol, multiple-testing corrections, verified
broker fills and forward demo are still required.

## Data input contract

Required CSV columns **in this exact order**, no substitutions:

```csv
timestamp_utc,bid_open,bid_high,bid_low,bid_close,ask_open,ask_high,ask_low,ask_close
```

- Timestamps are complete UTC ISO 8601 dates/times with timezone.
- Each entry is one complete, consecutive bar at exactly the chosen
  timeframe (M1/M5/M10); even one missing or duplicated interval
  refuses the input. Do not fill gaps with fictional prices.
- OHLC prices are USD **per troy ounce**, bid/ask from the **same broker**
  and instrument. Repeated mid prices, unrelated crypto prices,
  USD/USDT substitution or generic aggregate candle data are invalid
  research inputs.
- Need actual historical bid/ask (ideally tick-derived from that broker)
  because midpoint OHLC alone cannot establish executable spread.
- Source SHA-256 is recorded, but a file hash only identifies bytes;
  it does **not** authenticate the data to LiteFinance or the broker.
- No uploaded personal credentials, keys or account passwords belong
  in the CSV or repository.

Official cTrader Open API offers historical tick data and bars through
`ProtoOAGetTickDataReq` and `ProtoOAGetTrendbarsReq`. Historical tick
queries are limited to a maximum seven-day range per call, so a fully
verified collection must page by approved periods and request correct
bid/ask quote types. The API can trade, but the evaluator does not use
those operations. The exact gold symbol, digits and trading conditions
must come from the connected broker/account.

## Required model settings

Pass a second JSON file containing exactly these keys:

```json
{
  "timeframe_minutes": 1,
  "initial_equity_usd": "ACCOUNT_EQUITY_TO_VERIFY",
  "commission_usd_per_ounce_per_side": "BROKER_RATE_TO_VERIFY",
  "slippage_usd_per_ounce_per_side": "BROKER_EXECUTION_DISTRIBUTION_TO_VERIFY",
  "quantity_step_ounces": "BROKER_VOLUME_STEP_TO_VERIFY",
  "max_notional_to_equity": "APPROVED_MARGIN_AND_LEVERAGE_TO_VERIFY",
  "risk_fraction": "RESEARCH_RISK_FRACTION_TO_VERIFY",
  "stop_atr_multiple": "RESEARCH_STOP_DISTANCE_TO_VERIFY",
  "reward_to_risk": "RESEARCH_REWARD_RISK_TO_VERIFY",
  "max_hold_bars": 12
}
```

The placeholders are intentionally not valid numerical settings; replace
**only** with evidence from an actual account and its contract specs.
No default assumptions about a LiteFinance gold lot or account balance
are fabricated. Never treat a failed or incomplete dataset as a zero P&L
backtest. All values are read-only inputs; no funded account is touched.

Run, only after approved files are available:

```bash
python3 trading/mojtrade_costed_oos.py \
  --bid-ask-csv /private/reconciled-xauusd-bidask-m1.csv \
  --settings-json /private/verified-costs.json
```

The result explicitly includes `commercial_ready=false`,
`market_order_placement_enabled=false`, `live_trades=0`,
`realized_profit_verified=false`, and the number of strategies tried.
A selection may be absent. Unlike marketing materials, an absent
profitable model is a **legitimate result**.

## Acceptance path to actual income

1. Prove real market-data provenance, each spread/commission, full cost
   schedule and account details, with no executable access given to
   research code.
2. Perform at least multiple **purged, embargoed walk-forward** windows,
   register all trials, account for multiple-testing bias and perform
   realistic Monte Carlo stress and severe spread/wide-market shocks.
3. Run the exact strategy through a separate **cTrader/LiteFinance demo**
   order adapter with broker order IDs, partial fills, error recovery,
   margin and stop checks, and independent broker reconciliation.
4. Calculate net results in the actual account currency after spread,
   commission, slippage and financing; record max equity drawdown and
   tail loss, not just winning percentage.
5. Only with independently verified positive *forward* net performance
   and owner-authorized transaction scope should a separately audited
   live adapter be considered. The current branch has **none**.

The source has no automatic promotion or false 100%-profit guarantees.
The exact same risk controls make commercial deployment more robust;
they are not restrictions on research, markets, strategy innovation or
the legitimate ambition to earn income.
