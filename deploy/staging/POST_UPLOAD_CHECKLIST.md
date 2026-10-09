# Post-upload verification

Before any acceptance run:

- Confirm the application root is the isolated staging path, not the Production path.
- Confirm Python reports 3.11.x.
- Confirm `SAEIT_ENV=staging` and `DEBUG=False`.
- Confirm DB name is exactly the intended staging database and differs from Production.
- Confirm the staging DB user is dedicated to staging.
- Confirm no Production DB/password/API secret was copied into staging.
- Confirm publication, real payments, treasury and crypto execution are false.
- Confirm HTTPS works for `staging.zomorodmelal.ir`.
- Confirm `python manage.py staging_preflight` returns PASS.
- Confirm the research provider is network-backed, real-research capable and classified staging-safe.
- Run one Goal-only acceptance; preserve its JSON report/run ID.
- Exercise the operational drills reported by the acceptance command before claiming Gate 97.
- Keep the launch candidate inactive. Do not merge PR #32 or deploy to Production as part of this procedure.

If any isolation check is uncertain, stop. Do not substitute Production credentials or Production paths.
