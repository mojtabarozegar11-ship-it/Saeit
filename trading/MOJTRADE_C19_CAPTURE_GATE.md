# MojTrade C19 — Offline cTrader coverage preflight

The command `mojtrade_ctrader_capture_gate.py` is **read-only** and checks a
local operator-produced manifest for three CLI exports: `positions`,
`orders-history`, and `deals`. It does **not** sign into a broker, authenticate
the exporter, validate the CLI JSON schema, place orders, or approve trading.
It also refuses future-dated capture timestamps beyond a bounded 60-second
clock-skew allowance relative to the running machine's UTC clock. This is a
local plausibility check, **not** an independent or trusted time attestation;
an incorrect local clock can affect the result.

Official CLI semantics: positions are currently open; orders-history includes
finished orders; deals includes closed deals and realised P&L. All dates are
UTC. History windows can be truncated: orders-history returns at most 500
records and exposes `available`/`returned`, while deals returns at most 200
and a 200-row result is ambiguous. See
https://help.ctrader.com/ctrader-cli/use-commands/ .

## Capture procedure (authorized local operator only)

1. On an approved device with cTrader CLI installed, select the specific
   **DEMO** account from `accounts`. Never assume the guest web view belongs
   to this account.
2. Authenticate using `--pwd-file` stored privately; do not pass passwords on
   the command line or paste them into public issues, Actions or logs.
3. Capture `positions`, `orders-history --from=<UTC-day> --to=<UTC-day>`, and
   `deals --from=<UTC-day> --to=<UTC-day>`, each with the exact demo account and
   `-q`. Never run order, close, cancel, or start commands during evidence
   collection. Capture after 00:00 UTC the following day for a full-day audit.
4. Locally verify each capture's account, date scope, actual returned row
   counts and orders-history `available`/`returned` before entering their
   values in a manifest. If deals returns 200, this gate deliberately refuses
   to call it complete; use an authenticated alternative that supports full
   pagination before relying on the result.
5. Generate SHA-256 for each untouched local output. Keep manifest and the
   three files in one private folder; do not commit real trading data.

## Manifest schema (illustrative values only)

```json
{
  "account": "1234567",
  "day": "2026-11-08",
  "source": "ctrader-cli",
  "captures": {
    "positions": {
      "file": "positions.json",
      "sha256": "<64 lowercase hexadecimal characters>",
      "captured_utc": "2026-11-09T00:01:00Z",
      "count": 0
    },
    "orders_history": {
      "file": "orders.json",
      "sha256": "<64 lowercase hexadecimal characters>",
      "captured_utc": "2026-11-09T00:01:00Z",
      "count": 0,
      "from_utc_day": "2026-11-08",
      "to_utc_day": "2026-11-08",
      "available": 0,
      "returned": 0
    },
    "deals": {
      "file": "deals.json",
      "sha256": "<64 lowercase hexadecimal characters>",
      "captured_utc": "2026-11-09T00:01:00Z",
      "count": 0,
      "from_utc_day": "2026-11-08",
      "to_utc_day": "2026-11-08"
    }
  }
}
```

Run `python3 trading/mojtrade_ctrader_capture_gate.py --manifest /private/path/manifest.json`.
Exit `0` means the **declared** coverage passed the narrow offline checks;
exit `1` means a detected gap; exit `2` means an invalid manifest/file.
Even on exit `0`, `broker_source_authenticated=false` and
`commercial_readiness=false`. The manifest is operator-provided, not a secure
attestation. It cannot prove actual broker records, account status, or a trade.
