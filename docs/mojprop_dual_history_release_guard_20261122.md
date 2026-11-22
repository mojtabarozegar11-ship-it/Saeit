# Moj Prop: dual migration-history safety gate (22 Nov 2026)

**Source-only draft. Do not execute production migrations, release invoices, or enable TRX payment on the strength of this PR.**

## Source reconciliation

The `prop_firm` app has two legitimate historical branches:

- 10 original migrations named `0001_initial` through `0010_reward_reserve_ledger`, preserved byte-for-byte from `source-sync/20261120/prop_firm/migrations/`. The legacy database tables remain in the **default** database and must never be dropped in this cutover.
- 6 separate simulation migrations, ending at `0006_unique_invoice_receivers`. The seven simulation models belong exclusively to the **mojprop** database.

The proposed `0011_state_only_bridge` joins these histories and removes 15 obsolete legacy model declarations from *future Django migration state only*, with `database_operations=[]`. Existing historical physical tables remain in `default`; no legacy rows are copied or erased.

**Never restore the archived `0011_simulation_isolation.py`**: it recreates models that already exist in the simulation branch.

## Critical migration 0003 router correction

The existing `0003_payment_table_router_alignment.py` uses an unhinted `RunPython`. The effective router allows an unhinted `RunPython` on `default` but rejects it on `mojprop`. During a replay of the newly restored graph this could create an isolated payment table on the wrong database.

This PR adds two controls: explicit `hints={"model_name":"propsimulationpayment"}` and immediate in-function `schema_editor.connection.alias != MOJPROP_DB_ALIAS` guards. The guards apply on forward **and reverse** operations.

**Review caveat:** 0003 has already been recorded as applied on the isolated database. Changing an applied migration's source is exceptional. It must be reviewed with the exact recorded history on both databases and must never be used to justify reverse migration across 0003.

## Evidence already verified without DDL

- 15 historical tables exist in `default`, zero in `mojprop`.
- Seven simulation tables exist in `mojprop`, zero in `default`.
- Historical migration records coexist with the new simulation records on `mojprop`; `default` holds historical records only.
- Django's in-memory full migration graph with 17 nodes has one leaf, `0011_state_only_bridge`.
- Both aliases passed `MigrationLoader.check_consistent_history` in memory using production history.
- With the guarded 0003, the hypothetical default plan routes out all 19 possible model/data operations; `mojprop` has only two `AlterField` operations from 0006.
- Django's in-memory `MigrationAutodetector` produced no extra migrations against the intended, unique-recipient model state.
- Fake editors + the actual Django router verified the new 0003 forward and reverse protections; no real SQL.
- A neutralized logical backup archive passed digest/source checks, **not** an independent restore.
- The live `mojprop` payment ledger was empty when inspected; this is not a substitute for backup and final preflight.

## HARD STOP before any production cutover

1. Review GitHub CI and all patch diffs. Do not merge merely because a subset of tests pass.
2. Identify all active DB writers and prevent a race during the intended schema cutover.
3. Verify independent **restore of both databases** in isolated targets, including data, constraints and character set; test recovery end-to-end.
4. Re-run production-read-only recipient duplication and migration provenance checks immediately before release.
5. Review the real MariaDB SQL generated for both aliases. No legacy `DROP`, unexpected `CREATE`, fake migration, or other unapproved DDL.
6. Take a verified current pre-change backup and record a rollback/forward-fix plan. Do not roll back through migration 0003 where reverse could drop payment tables.
7. Only after a separately authorized controlled release may the isolated schema be migrated. **Do not activate the 30 TRX invoice path** until seller eligibility, paid terms, reward reserve, real settlement rail, recovery, verification email, rate limiting and buyer protections are independently demonstrated.

This note documents a source-only repair. The migration safety PR is **not a production deployment** or evidence of new revenue.
