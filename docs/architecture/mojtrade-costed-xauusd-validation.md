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

## Expanding walk-forward / three execution-cost scenarios

The new `trading/mojtrade_walk_forward.py` runs repeated chronological,
past-only training/selection. The default study uses **three separate
100-bar future windows**. Each fold is separated from its training cut-off
by an embargo of `max(40, max_hold_bars)` bars. Later folds may train on
earlier historical periods, including observations from earlier test
windows **only after those prices existed in time**. A selected model is
never selected on its own future test performance.

In each test window, use the **same past-only signal model** under three
hypothetical executable cost conditions:

| Scenario | Observed spread | Slippage | Commission |
|---|---:|---:|---:|
| supplied broker assumptions | 1× | 1× | 1× |
| wider market | 1.5× | 1.5× | 1.5× |
| severe cost shock | 3× | 3× | 2× |

The observed bid/ask levels come from the supplied CSV; in stress cases
the bid quote is preserved and the ask quote is widened relative to
its original bid. The underlying price history and signal inputs stay
unchanged. Neither the broker origin of the CSV nor future market
liquidity, funding costs or order-book depth can be proven by a
backtest.

**Read-only command:**

```bash
python3 -m trading.mojtrade_walk_forward \
  --bid-ask-csv /private/reconciled-xauusd-bidask-m1.csv \
  --settings-json /private/verified-costs.json \
  --folds 3 \
  --test-bars 100
```

The tool refuses insufficient history, an invalid fingerprint,
unsupported fold counts, and too-short test ranges rather than
filling missing evidence with profits. The minimum for the default
three-fold design and the current research parameters is 720
**observed** source bars, with every intervening closure covered by an
exact broker-specific closure record. This is a research minimum, not enough
to claim statistically reliable profitability.

**Market-session evidence path implemented:** `parse_bars` now accepts
market closure ranges only when supplied in a separate explicit
LiteFinance XAUUSD session manifest; each closure must match exactly
one gap between adjacent real source bars, without creating prices.
Missing bars during claimed open sessions are rejected. No supplied
claim, even an exactly matched one, proves the broker actually closed:
**independent broker/calendar provenance remains an external blocker**.

A session manifest has this strict schema (illustrative placeholder,
not evidence of any real broker closure):

```json
{
  "schema_version": 1,
  "broker": "LiteFinance",
  "symbol": "XAUUSD",
  "timeframe_minutes": 1,
  "closures": [
    {
      "start_utc": "2026-11-07T00:00:00+00:00",
      "end_utc": "2026-11-08T23:00:00+00:00",
      "reason": "scheduled_weekend",
      "evidence_ref": "REPLACE_WITH_ACTUAL_BROKER_SESSION_RECEIPT"
    }
  ]
}
```

The above timestamps are **illustrative only** and MUST NOT be taken as
LiteFinance market hours. The actual gap must match these times
exactly or the parser will reject them. The only accepted reasons are
`scheduled_weekend` (up to 72 hours), `session_break` (up to 6 hours)
and `broker_holiday` (up to 120 hours). Each interval must be aligned
to the selected M1/M5/M10 timeframe, unique, time-ordered, with a
nonblank evidence reference. An unused or fabricated closure is rejected.

Supply the file in either read-only command above with:

```bash
--session-closures-json /private/litefinance-xauusd-closure-claims.json
```

The resulting JSON includes a SHA-256 of the closure manifest, number
of exactly reconciled gaps, and explicitly
`market_closure_broker_origin_verified=false`.

Per official cTrader documentation, `Symbol.MarketHours` exposes
`Sessions` and the current open/close status:
https://help.ctrader.com/ctrader-algo/references/MarketData/Symbols/MarketHours/
Historical bars can be requested using `ProtoOAGetTrendbarsReq`:
https://help.ctrader.com/open-api/symbol-data/

**Independent official source check (2026-11-12):**
LiteFinance's public XAUUSD instrument-details page currently displays
Monday 01:06–23:59, Tuesday–Friday 01:02–23:59 and no weekend trading.
These are **terminal/server schedule times, NOT UTC**. The 2023
LiteFinance session notice listed Monday opening 01:05; the updated
instrument page differs by a minute. Never extrapolate either
schedule into UTC dates without the actual terminal's UTC offset,
daylight-saving policy and holiday exceptions.

Official public instrument details:
https://my.litefinance.org/de/trading/info?symbol=XAUUSD

Public XAUUSD contract page reports **100 troy ounces per standard lot**
and current instrument listing a **0.01-lot minimum and volume step**,
equivalent to a nominal **1-ounce minimum and step**. This does not
prove the account's leverage, slippage, margin or order permissions.
The research settings loader now **rejects** any XAUUSD
`quantity_step_ounces` other than 1.0. It does not simulate
untradeable micro-ounce positions. The public listing does not verify
the particular account's contract configuration: this must be
reconciled before brokerage execution, and a genuine broker change
requires reviewing this research contract rather than silently
using an invalid lot conversion.

Official contract specifications:
https://www.litefinance.org/trading/trading-instruments/commodities/
Official historical notice:
https://www.litefinance.org/company/detail/news/103358/

**Remaining blocker:** Obtain and reconcile the exact LiteFinance
server offset, XAUUSD symbol-specific schedule, holidays, timestamps,
actual contract/account lot and step, and historical bid/ask quotes from
the authorized account before accepting any claimed calendar as real
evidence. Do not fabricate closed-market prices or discard losing
intervals to make a strategy profitable. A signal issued just before
an accepted market closure is discarded at the next reopening rather
than optimistically filled as an immediate next-bar order. Open
positions remain exposed to potential gap loss; overnight financing
is still not modeled or verified.

The output keeps each fold's all-candidate training scores, selected
strategy (or none), embargo and untouched future-test results, plus
the three cost-sensitivity outcomes. A historical robustness
candidate is not `commercial_ready`; the latter remains false.
There is no claimed demo fill, received income, brokerage account
connection, or permission to place a trade.

The GitHub CI exercises chronological boundaries, anti-lookahead,
invalid input, low-quality strategy rejection and synthetic
spread-shock behavior. These fixtures prove only that source code
behaves as specified; they are **not actual market experiments**.
