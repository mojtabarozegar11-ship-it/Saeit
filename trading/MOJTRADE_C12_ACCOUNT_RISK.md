# MojTrade C12 — account-wide realized P/L reconciliation guard

## Verified defect and correction

- `MojTradeDemoBot` previously derived `realized_today` only from its own
  strategy labels and the current chart's symbol. `MojTradeOmegaXDemoBot`
  included only MojTrade labels across the account. Both omitted other
  manual/cBot closed trades in the DEMO account.
- Both adapters now iterate the broker's entire `History` of closed trades,
  include every trade closing on the current UTC day, and sum `NetProfit` in
  account currency. Non-finite values, including overflow in the aggregate,
  fail closed. Both coordinator observation and reservation use that value.
- This makes the realized-P/L daily-loss gate account-wide; the equity gate,
  broker-side SL/TP checks, 3-position MojTrade cap, demo-only account check,
  remote reservation and disabled-by-default settings remain in place.

## Evidence and limits

- Local Python and source-contract suite: 62 tests passed (one new regression
  test). `bash -n scripts/mojtrade_build_cbots.sh` passed.
- Static tests do not prove successful cTrader compilation, complete broker
  history retrieval, cTrader runtime behavior or a real DEMO order.
- The preceding C11 source compiled in GitHub Actions run 42459299275, but
  **the changed C12 source requires its own successful compile result**.
- The bot must never take real-money orders. Do not enable reservations or
  trade-enabled cBot parameters before TLS, account enrollment, broker-history
  reconciliation and supervised cTrader DEMO runtime have been verified.

## Operational go/no-go checklist

1. Inspect C12 GitHub Actions output and verify both `.algo` build hashes.
2. Verify cTrader's actual broker `History` UTC-day NetProfit sum against the
   broker's daily realized account P/L, including another symbol and a manual
   closed trade. Do not seed a baseline from an unverified history snapshot.
3. Verify the exact DEMO account, funded demo balance, service TLS proxy,
   private secret storage, UTC baseline enrollment, and fail-closed recovery.
4. Run controlled DEMO observation and account-wide risk-stop checks; review
   broker positions and reconciliation after restarts/network failures.
5. No live-account execution, public signals, or trading activation from CI.

Primary reference: https://help.ctrader.com/ctrader-algo/references/Trading/History/History/
