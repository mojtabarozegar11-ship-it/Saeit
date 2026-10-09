# Zomorod Factory — cPanel Real-Staging Transfer Pack

This directory is the owner handoff contract for Gate 97. Preparing this pack does **not** pass Gate 97.

## Target
- Hostname: `staging.zomorodmelal.ir`
- Python: 3.11
- Application root: isolated from Production, recommended `/home/zomorod2/Saeit-staging`
- Existing staging DB: `zomorod2_saeit_stg`
- Production application/database/secrets must never be reused.

## Owner transfer sequence
1. Upload the repository snapshot from the verified branch/SHA into the isolated staging application root. Never overwrite `/home/zomorod2/Saeit` or `public_html`.
2. In cPanel create a **separate PostgreSQL user** and attach it only to `zomorod2_saeit_stg`.
3. Create/point `staging.zomorodmelal.ir` to the isolated staging application.
4. Create `.env` from `deploy/staging/.env.staging.example` and insert secrets locally. Never commit or paste secrets into chat.
5. Activate a Python 3.11 virtualenv, install `requirements.txt`, then run `bash deploy/staging/setup_staging.sh`.
6. Run `bash deploy/staging/preflight.sh`. Do not continue unless it returns PASS.
7. Configure the REAL-STAGING-SAFE research provider credential locally.
8. Run the Goal-only acceptance command documented below.
9. Preserve JSON reports and audit logs. Do not publish/deploy to Production.

## Acceptance
```bash
python manage.py staging_autonomy_acceptance --goal "Research, validate, build, independently verify, localize and prepare one small evidence-backed digital product as an inactive launch candidate."
```

A candidate PASS is not by itself full Gate 97: the command reports the operational drills still required (scheduler, restart/resume, stale recovery, transient retry, bounded re-research and idempotent replay).

## Rollback
Staging rollback means stop the staging Passenger app/cron, preserve reports/logs, restore the previous staging snapshot, and keep the staging DB isolated. Never use Production as a rollback target.

## Production boundary
Staging must keep publication, real payments, treasury and crypto execution disabled. Owner approval remains required for Production and governed high-risk actions.


## cPanel scheduler
After preflight passes, configure a staging-only cron (for example every 10 minutes) that activates the staging Python 3.11 virtualenv and runs:

```bash
PATH=/home/zomorod2/virtualenv/Saeit-staging/bin:$PATH SAEIT_STAGING_ROOT=/home/zomorod2/Saeit-staging /bin/sh /home/zomorod2/Saeit-staging/deploy/staging/staging_tick.sh
```

The cron explicitly prepends the staging virtualenv to PATH and must point only at the staging root/database. Do not alter the existing Production cron.

## Secrets required locally
Generate `SECRET_KEY` and `SAEIT_BRIDGE_SECRET` on the staging host. Configure the dedicated staging PostgreSQL user's password and a staging-only `STAGING_RESEARCH_API_KEY`. None of these belong in GitHub or chat.

## Current external blocker
The repository now contains a real network-backed staging adapter, but real acceptance still requires an actual staging-only provider credential and a live network call. Evidence quality/coverage is intentionally fail-closed: if real sources do not support the required commercial factors, the Master must re-research or block rather than invent evidence.
