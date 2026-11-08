# MojTrade C15 — broker-reported position receipts, not broker verification

## Operational gap

The previous coordinator retained only whether an adapter claimed that its
market order filled. There was no broker position identifier available to
compare the admission ticket with cTrader's position history after a restart
or a lost acknowledgement.

## C15 changes

1. A successful `POST /v1/commit` now **requires** a positive decimal
   `broker_position_id`. Both DEMO-only cBots send `result.Position.Id` when
   the broker reports a successful fill. Missing or malformed IDs fail closed.
2. The coordinator keeps that ID with the original request, account, UTC
   day, state and reservation times. It rejects a conflicting replay and
   a second reservation claiming the same broker ID for the same account.
3. A cancellation cannot claim a broker position ID.
4. Existing SQLite databases are migrated in place with a nullable field,
   leaving existing reservation rows intact. Historic committed rows without
   broker IDs remain unverified legacy evidence and cannot be upgraded by a
   replay.
5. Authorized operators can read `GET /v1/receipts?account=...&day=...`
   over the approved HTTPS proxy with the same Bearer header. The response
   includes at most 100 newest receipts and a `truncated` flag. It uses a
   read-only SQLite connection and does not modify reservations.

`broker_verified` is always `false`: a position ID sent by a cBot is an
**assertion**, not proof from an independent broker API. An operator must
compare the ledger entries with cTrader's actual positions and account history.
No automatic trading admission depends on the report.

## Deployment gates

- Coordinate the Python service upgrade with both C15 cBots; C14 clients
  cannot commit fills to a C15 coordinator without the new field.
- Make an SQLite online backup before migration; do not copy only the main
  database file while WAL writes are active.
- Verify the HTTPS reverse proxy, credentials, owner-only receipt access,
  restoration behavior, and broker account identity on the intended VPS.
- Check at least one *supervised and approved DEMO* broker result end to end:
  reservation ID, broker position ID, protection, settlement, and reconciliation
  with cTrader history. No such order is submitted by this code change.
- Ensure all demo-enable switches remain false until these checks are passed.

Live accounts remain permanently disabled. No external signal, VPS change,
cost, funds transfer, or commercial activity is authorized by this document.
