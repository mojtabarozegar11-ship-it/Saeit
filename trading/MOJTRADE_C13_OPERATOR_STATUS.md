# MojTrade C13 — protected operator risk-state visibility

## Operational problem resolved

Previously `/health` returned `SERVICE_UP` whenever the Python process was
alive, even if the account was not enrolled, risk had latched a stop, or the
last broker observation had gone stale. Treating that as trading readiness
would have been unsafe.

The coordinator retains `/health` as **liveness only** and adds an explicitly
authenticated, **read-only** `GET /v1/status?account=ACCOUNT&day=YYYY-MM-DD`.
Supply the same bearer token in the **Authorization header**, never in a URL.
The URL contains no secret but the response contains account-level financial
telemetry, so only reach it through the approved HTTPS proxy with access
controls; the Python process stays bound to loopback.

Response fields:

| Field | Meaning |
|---|---|
| `baseline`, `last_equity` | Persisted server-side UTC-day risk equity |
| `halted` | Sticky daily loss stop for the specified day |
| `last_risk_update_age_seconds` | Signed age of latest successful risk update; negative means server time is earlier than that update |
| `telemetry_fresh` | Same UTC day and age from 0 through 120 s; a future-dated update is never considered fresh |
| `active_reservations` | Non-expired reserved or committed short-lived slots |
| `demo_reservations_enabled` | The service's explicit demo enable flag |

Neither `telemetry_fresh` nor `demo_reservations_enabled` asserts that an actual
broker/cTrader session, TLS connection, sufficient free margin, or profitable
strategy is ready. The status call opens SQLite in `mode=ro` with
`query_only=ON`. It neither creates a missing database nor seeds an account
or changes a reservation, baseline, halt latch or equity observation.
The write-side observation/reservation handler also refuses a backwards server
clock (`clock_rollback`) until the clock reaches the persisted update time.

## Go / no-go

1. On approved VPS, verify service startup, isolated user, protected secrets,
   private database path, TLS reverse proxy and upstream rate limits.
2. Compare the status baseline/equity with the exact broker DEMO account and
   its UTC daily history, including closed manual and cross-symbol positions.
3. Verify `halted=false`, `telemetry_fresh=true`, and zero or explained
   `active_reservations`. An unenrolled account returns HTTP 409.
4. Check 401 for missing bearer token, 409 for invalid query and 503 for
   storage failure. Never interpret `/health` as trading permission.
5. Keep `--enable-demo-reservations` absent from the service and cBot demo
   parameters off until explicit supervised DEMO activation, reviewed runtime
   recovery and adequate virtual balance.

No live trading, market signal publication, VPS deployment, broker order,
financial transaction, or new fee is performed by this change.
