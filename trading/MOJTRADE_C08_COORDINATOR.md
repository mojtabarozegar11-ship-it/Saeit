# MojTrade C08 — DEMO-only central risk coordinator

**Status:** source implementation and local invariant checks; not deployed,
compiled in cTrader, connected to an account, or commercially released.

## Architecture

- Both cBots remain `AccessRights.None`, refuse live accounts, and refuse demo
  orders unless the new coordinated-demo switch, HTTPS URL, and long bearer
  token are configured.
- Immediately before each potential demo order, each cBot POSTs a reservation
  request with its cTrader account number, UTC day, current equity, realized
  history and count of all recognized MojTrade-labelled broker positions.
- A single loopback Python service on the VPS uses SQLite `BEGIN IMMEDIATE`
  and WAL to serialize reservations across bot instances. A 90-second hold
  covers in-flight and recently filled orders. A failed order cancels its
  reservation; a successful order commits it temporarily.
- The service persists an operator-enrolled UTC-day equity baseline, a sticky
  account-wide daily-loss halt (2% maximum), and idempotency IDs. New-day
  rollover is automatic only when a trustworthy *recent local observation*
  from the final 120 seconds of the prior day exists and the first new-day
  request arrives within 120 seconds. Otherwise the service fails closed.
- No coordinator response, invalid/expired reservation, wrong token, or
  failed settlement -> no more new entries by the adapter.

## Security and deployment gates

1. Run this service from a local Python environment (no third-party packages
   required). Create a dedicated system user and persistent DB directory,
   protected against non-owner writes. The service binds to 127.0.0.1 only.
2. Operator must supply the DB path and a strong `MOJTRADE_RISK_TOKEN` through
   environment configuration **outside source control**. Example placeholders:

   ```bash
   python trading/mojtrade_risk_coordinator.py --db /var/lib/mojtrade-risk/state.sqlite \
     --seed-account ACCOUNT_NUMBER --seed-day YYYY-MM-DD --seed-equity EQUITY
   ```

3. A reverse proxy with HTTPS and authentication/rate limiting is mandatory
   before giving cTrader clients a public URL. Never expose port 8765 directly.
4. Service execution is disabled for reservations by default; explicit
   `--enable-demo-reservations` and cBot opt-in are required after review.
5. This HTTP integration **does not work in cTrader Cloud**: official cTrader
   documentation reports HTTP requests as unsupported there. Use a supported
   desktop/CLI setup, with independent runtime ownership, not GitHub Actions.
6. Run `python -m unittest discover -s tests -p 'test_mojtrade_risk_coordinator.py'`
   and independently compile both C# cBots in the exact cTrader version.
7. Verify all error paths in a controlled demo account before any activation.
   No live trading or public signal publication is authorized by this work.

## Remaining limitations — do not call this production-ready

- The coordinator does not communicate directly with the broker. It trusts
  reported equity and position counts from authenticated *demo adapters*.
  An old adapter or unrelated bot can bypass reservations. Broker-reconciled
  account-wide control is required for a strong production guarantee.
- The bot must successfully observe account equity near the UTC midnight
  boundary for automatic rollover; otherwise a manual baseline enrollment is
  required. A first start mid-day cannot reconstruct the true opening equity.
- A successful broker order cannot be rolled back just because the subsequent
  network settlement fails. The bot stops, and the coordinator retains a short
  safety hold; an emergency control-room review would be necessary.
- An in-flight order can outlive the 90-second reservation on severe API
  latency. With no authoritative broker acknowledgement, exactly-once trading
  is not yet proven. The broker itself must remain the final source of truth.
- Access token rotation, reverse-proxy TLS, VPS recovery from disk corruption,
  cTrader compilation, and account-specific broker integration remain
  release gates. Keep all real-money paths locked.
