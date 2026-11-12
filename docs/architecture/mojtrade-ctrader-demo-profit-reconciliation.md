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

## Exact second-source matching — added in this cycle

A new guarded command compares the complete cTrader demo audit log with
a **separately obtained and explicitly normalized cTrader account
statement extract**. A cTrader native statement may be saved through
the platform's History → Statement workflow. **The field names in the
raw exported file vary by platform/version; it cannot be passed directly
unless independently normalized and audited.** Never invent missing
columns or economic values.

The normalized UTF-8 CSV has **exactly** these columns in order:

```csv
deal_id,position_id,closed_utc,symbol,label,side,lots,gross,commission,swap,net,balance_after,currency
```

All amounts are in the account currency, not assumed to be USD. The
closing timestamp must be UTC ISO-8601, including timezone, and each
deal must correspond to a **closing** deal, not a pending order or an
opening fill. Use the original `ClosingDealId`; never substitute
`PositionId` or `OrderId` for it.

The importer requires a third private metadata file
`ctrader-statement-manifest.json` with this exact schema:

```json
{
  "schema_version": 1,
  "broker": "LiteFinance",
  "account_mode": "demo",
  "account_alias": "LITE_DEMO_1",
  "account_currency": "USD",
  "symbol": "XAUUSD",
  "source": "ctrader_history_statement_export",
  "full_label_history": true,
  "statement_sha256": "REPLACE_WITH_SHA256_OF_EXACT_NORMALIZED_CSV_BYTES",
  "exported_at_utc": "REPLACE_WITH_REAL_UTC_EXPORT_TIMESTAMP"
}
```

Those values are an **illustrative template only**, not evidence of an
actual connected account. `full_label_history` asserts that the
export includes **every** deal for the selected label/symbol and
relevant history period. If this cannot be verified, the scope
claim is not supportable. A file hash detects edits and wrong-file
mixups but **does not authenticate** a statement to a broker.

Place these three files in the configured private directory:

```text
MOJTRADE_PRIVATE_DIR/
  demo-audit.log
  ctrader-statement-normalized.csv
  ctrader-statement-manifest.json
```

Use `0700` on the containing directory and `0600` on every file.
Never place account secrets or passwords in these files.

**Offline cross-check, no Django changes or broker requests:**

```bash
python -m trading.mojtrade_broker_statement_check \
  --demo-log /private/mojtrade/demo-audit.log \
  --normalized-statement /private/mojtrade/ctrader-statement-normalized.csv \
  --statement-manifest /private/mojtrade/ctrader-statement-manifest.json
```

**Record a canonical private receipt, only after the new code is
independently deployed and the validated files actually exist:**

```bash
python manage.py mojtrade_statement_crosscheck_cycle
```

The canonical task `mojtrade_demo_audit_ingest` is idempotent on a
composite SHA-256 of all three source files, and it records whether
all closing deal IDs and each position, time, direction, quantity,
gross, fees, swap, broker-native net and closing balance match.
It explicitly **rejects** missing or extra closing deals, missing
manifest evidence, a live account, wrong currency, mismatched label
or malformed numeric values. The account must be verified to be a
demo account using an additional direct broker/account check.

The 0.01 account-currency per-deal tolerance exists solely for
statement *rounding*; the all-deals net total must also match
within 0.01. Do not add multiple overlapping full-history snapshots:
they refer to the same historical deal set.

**Limits of the verified work:** This cross-check operates on two
copies of data potentially originating from the **same cTrader
environment**. It proves internal agreement between extracts, not
independent broker statement authenticity, source completeness,
account-level deposit/withdrawal reconciliation or withdrawable
profit. These remain *false* in the output until a separately
authenticated source and official funding/transaction ledger are
verified.

Official references:
- https://help.ctrader.com/ctrader/trading/history/
- https://help.ctrader.com/ctrader-algo/references/Trading/History/HistoricalTrade/
