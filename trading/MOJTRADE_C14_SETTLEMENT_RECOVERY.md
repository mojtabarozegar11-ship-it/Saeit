# MojTrade C14 — safe, idempotent DEMO settlement recovery

## Failure addressed

An order could receive a valid reservation and then the coordinator could
persist `/v1/commit` or `/v1/cancel`, but the HTTP acknowledgement could be
lost. Previously, a repeated settlement returned `409`, causing the adapter
to halt even though its first settlement had succeeded.

The coordinator now permits an **identical, authenticated replay** of the
same `request_id`, account and settled outcome. It does not insert another
reservation, overwrite a state or extend the original expiration time.
Changing `committed` to `cancelled`, or vice versa, is rejected with
`DENIED|settlement_conflict`. Unknown identities and requests that are still
unsettled after expiry remain denied.

Both cTrader DEMO-only adapters now try a settlement at most twice, using the
same receipt ID, same account and same result. A second call occurs only if
the first failed at the transport layer or returned HTTP 5xx. Auth failures,
conflicts, or unexpected HTTP 2xx content do not qualify for a retry.
If neither attempt confirms `SETTLED`, the adapter still halts new orders.

## Safety and deployment conditions

- Live account execution remains hard-blocked.
- Both coordinated-DEMO and Omega DEMO entry switches remain off by default.
- The coordinator systemd example still does not enable reservations.
- The server's `BEGIN IMMEDIATE` transaction serializes competing settlements.
- Idempotence does **not** prove that the order reached or was protected at the
  broker. Compare broker-side positions, protective SL/TP and full account
  history during supervised DEMO reconciliation before enabling anything.
- Retrying a `5xx` does not mean an arbitrary failed response was successful;
  success requires an explicit matching `SETTLED` acknowledgement.
- Only bind the Python server to loopback behind controlled HTTPS. Secrets
  must not appear in URLs, commits, logs or reports.

Verification: local Python tests cover duplicate commit and cancel, conflicting
outcomes, wrong account, expired reservation, HTTP acknowledgement replay, and
both client contract paths. A successful GitHub C# compile is separately
required; local Python tests are not a substitute for .NET/cTrader runtime.

No VPS release, broker order, public signal, real money or new cost was
authorized or executed in this cycle.
