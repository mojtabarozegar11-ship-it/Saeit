# MOJ PROP staging preflight

This gate is configuration-only. It does not connect to MariaDB, run a
migration, reload Passenger, expose the English route, or enable payment.

## Required evidence before staging

1. DATABASES["mojprop"] exists and is physically distinct from default.
2. config.mojprop_db_router.MojPropDatabaseRouter is listed in
   DATABASE_ROUTERS.
3. MPW_MOJPROP_IDENTITY_DIGEST_SECRET is supplied through the staging secret
   store, never committed to Git.
4. MPW_MOJPROP_RECONCILIATION_SOURCE_ALIAS is explicit and is not mojprop.
5. All MOJ PROP public route/invoice flags remain false.
6. A migration administrator separately proves permission to run migration
   0011_simulation_isolation.
7. A runtime database user separately proves only the required runtime DML
   privileges.

The preflight intentionally fails closed when any item is missing. Successful
preflight is necessary but not sufficient: the migration still requires a
separate owner-authorized staging action, followed by read-only schema
verification and an English-only canary.
