# MojTrade: reconcile actual cTrader DEMO fills with Mojtaba.bot.ai

## Operational objective

This work separates **hypothetical backtest profits** from **actual broker
demo trade fills** while retaining one canonical task owner:
`mojtaba-bot-ai`.

**This is not commercial readiness or real net income.** A cTrader demo
account can show cost-inclusive P&L without any withdrawable funds.
A local log/CSV copied from cTrader may be edited and is not remotely
broker-authenticated. Neither the bot nor the importer claims to have
connected to an actual LiteFinance account in this draft branch.

## Native broker-history collector

`trading/MojTradeDemoHistoryAuditBot.cs` uses the official cTrader
Algo API `History.FindAll(label, symbol)`, with the exact existing
MojTrade Omega X demo execution label
`MojTrade-OMEGA-X-DEMO`. It reads closing deal IDs rather than
assuming one position equals one closing fill; this handles partial
closes without merging distinct broker deals.

For every historical closing deal it logs:

- closing deal ID, position ID and UTC closing timestamp;
- symbol, direction and closed lot quantity;
- broker-native GrossProfit, Commissions, Swap and NetProfit;
- the broker-reported account balance after the deal.

**NetProfit is already inclusive of commissions/swaps**, so never
subtract those again in the importer. The native auditor is explicitly
blocked on `Account.IsLive`, uses `AccessRights.None`,
issues zero orders, and has no external network/file-writes.
It is a one-shot robot that stops after printing its results.

The default cap is 2,000 complete closing-deal rows, configurable
up to 20,000. When the number of retrieved deals exceeds that cap,
the bot outputs `BLOCKED` instead of a truncated profit total.

The parser requires one full START, zero or more DEALs, and one
complete END; mismatched counts, duplicate closing deal IDs, wrong
account mode, stale/invalid timestamps, missing totals, unexpected
fields or modified amounts all fail closed.

This is an *export format created by this bot*, not a claim that raw
cTrader UI CSV files use the same schema.

## Local, read-only workflow (after approved deployment)

1. Open the cTrader **demo** account associated with LiteFinance in
   your own cTrader environment. Attach
   `MojTradeDemoHistoryAuditBot` to the relevant chart (e.g. XAUUSD),
   set a non-sensitive demo alias and run once. It performs **no trades**.
2. Confirm the cTrader log contains one complete
   `MOJTRADE_AUDIT_V1|START ... END` cycle. Preserve every
   `MOJTRADE_AUDIT_V1` record in a local private UTF-8 log file;
   logs with incomplete history are rejected.
3. Place that file at
   `MOJTRADE_PRIVATE_DIR/demo-audit.log`, with a private directory
   (`0700`) and private file (`0600`), never inside a public
   web directory. Do not place any login password, token, personal
   account number or wallet key inside it.
4. Once the canonical bot code is independently deployed, run:

```bash
python manage.py mojtrade_demo_audit_cycle
```

The command produces an idempotent, audited `AgentTask` on
`mojtaba-bot-ai` with the source SHA-256. It never creates a
second autonomous MojTrade executor, never publishes signals,
never connects to a broker and never places an order.

To reconcile the same file **without writing to Django**, the
local parser may be used as follows:

```bash
python -m trading.mojtrade_demo_receipt_reconcile \
  --private-log /private/mojtrade/demo-audit.log
```

Output fields include the gross demo P&L, commissions, swaps,
broker-native net demo P&L, win/loss counts, profit factor,
and **deal-cumulative closed-P&L drawdown**. That drawdown is
**not** a replacement for the broker's full floating equity drawdown.
An empty history produces zero deals, not a success claim.

Repeated imports of the same source hash return the same task.
Different source files can overlap the same historical deals;
therefore their net totals **MUST NOT** be summed as if they were
independent revenues. No closed-deal identity is replaced or
discarded on ingestion.

## External evidence still required

- Compilation and successful execution against the user's actual
  cTrader **demo** environment (not covered by Python CI).
- LiteFinance account broker identity, official account statement
  and matching complete closing-deal identifiers and amounts.
- Cross-check cashflows including deposits, withdrawals,
  rebates, financing and currency conversion; partial and pending
  trades must be considered.
- Independently authenticated quote/spread history, verified
  strategy quality out of sample, and realistic demo-forward
  net-of-cost performance.
- A separate risk-authorized live-order execution system and
  case-specific owner approval before real money is exposed.

Current output deliberately includes
`source_log_is_independently_authenticated=false`,
`broker_statement_reconciled=false`,
`real_account_revenue_verified=false`, and
`broker_order_placement_enabled=false`.

Official cTrader references:

- https://help.ctrader.com/ctrader-algo/references/Trading/History/History/FindAll/
- https://help.ctrader.com/ctrader-algo/references/Trading/History/HistoricalTrade/
- https://help.ctrader.com/ctrader/trading/history/
