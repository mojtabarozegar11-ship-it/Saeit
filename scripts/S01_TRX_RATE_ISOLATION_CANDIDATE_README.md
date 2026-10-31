# S-01 — TRX rate isolation candidate (2026-10-31)

**Status: CODE / NOT_DELIVERED.** This is not the live MojPlayWin checkout, not a production installation, and not a paid-transaction test.

Observed pinned run [41170450170](https://github.com/mojtabarozegar11-ship-it/Saeit/actions/runs/41170450170) fails when a stale ETH market observation aborts a TRX quote. The candidate fetches the TRX-only CoinGecko observation and validates TRX's own USD price and timestamp. It rejects stale (>300s), future (>45s), malformed, nonfinite, zero, untrusted-origin, oversized and transport-failed responses. A fresh TRX observation does not depend on ETH freshness.

Files and independently read-back SHA-256 (UTF-8):
- `scripts/s01_trx_rate_isolation_candidate.py`: `92bab83c33fdc31301fe409d5f8a66e06037b7785405bb8dac2a21754dedc138`
- `scripts/test_s01_trx_rate_isolation_candidate.py`: `fcf474299990a7fe8f10e79474ced7d5a3452e4b06b28dda926650044e598114`

The equivalent isolated local candidate passed 14/14 synthetic tests; **exact GitHub branch CI and staging integration have not yet been independently run**. Re-run the exact branch tests using `python -m unittest scripts.test_s01_trx_rate_isolation_candidate` before approval.

**Integration is blocked** until S-01 retrieves exact current live source SHA and effective Passenger DB configuration through the existing pinned GitHub Actions → VPS relay → cPanel read-only path, and proves a full encrypted off-host MojPlayWin site + effective DB backup with isolated restore and rollback. Inspect current `mpw_commerce/buyer_wallets.py`, `scripts/mojplaywin_direct_wallet_rates.py`, and `services/mpw_trx_commercial_web.py` to preserve quote units, rounding, expiry and existing CSP; do not replace blindly. Then stage the rate adapter and run invoice/Trust Wallet/receipt/entitlement/email/download acceptance without real payment. Release requires separate safety approval. No factory/master-agent write or restart; F-01 HOLD unchanged.

The private Library ZIP upload failed because the container session was unavailable. The two text source files on this existing S-owned branch are the persistent recoverable candidate, **not a customer deliverable**.
