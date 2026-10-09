# Real Staging Readiness (Gate 97 preparation)

This document prepares an isolated staging environment. It does not authorize or perform deployment.

## Required isolated environment

Use a host/runtime and PostgreSQL database dedicated to staging. It must not share the Production database, Production credentials, payment/treasury/crypto execution credentials, or Production publication channels.

Required environment variable names:

`SAEIT_ENV`, `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`,
`DATABASE_URL`, `STAGING_DB_IDENTITY`, `PRODUCTION_DB_IDENTITY`,
`SAEIT_BRIDGE_SECRET`, `FACTORY_RESEARCH_PROVIDER`, `FACTORY_RESEARCH_PROVIDER_TIER`,
`PRODUCTION_PUBLICATION_ENABLED`, `REAL_PAYMENTS_ENABLED`,
`TREASURY_EXECUTION_ENABLED`, `CRYPTO_EXECUTION_ENABLED`.

For real staging acceptance set `SAEIT_ENV=staging`, `DEBUG=False`, provider tier `staging`, and all four production/execution switches to `False`.

## Provider classification

- REAL-STAGING-SAFE: real external provider approved/configured for staging; required for Gate 97 research.
- SANDBOX: external sandbox; useful for integration checks but does not substitute for a required real staging-safe research provider.
- FIXTURE/CI-ONLY: deterministic test providers; prohibited from Gate 97 evidence.
- PRODUCTION-ONLY: credentials/channels intended for Production; prohibited in staging.

If no REAL-STAGING-SAFE research provider is available, Gate 97 is BLOCKED.

## Required services

Python/Django runtime from this repository, isolated PostgreSQL, the configured REAL-STAGING-SAFE research provider, durable filesystem/storage required by the existing builder, and the existing Master/Worker/audit database runtime.

## Owner-authorized deployment sequence

After creating the isolated environment and injecting secrets outside GitHub:

```
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py staging_preflight
```

The last command emits JSON and must return `result: PASS` before acceptance is attempted.

Then run exactly one bounded Goal-only acceptance:

```
python manage.py staging_autonomy_acceptance --goal "<OWNER GOAL>" --run-id "<DURABLE STAGING RUN ID>" --max-steps 30
```

Expected critical PASS values: environment=staging, fixture_provider_count=0,
human_task_creation_count=0, manual_stage_advancement_count=0,
external_intermediate_artifact_count=0, lineage_verification=true,
published=false, deployed=false, production_action_successes=0, result=PASS.

Launch Candidate is the terminal boundary. Do not publish or deploy it automatically.

## Cleanup / rollback

Stop the staging worker/process, preserve the JSON acceptance report and audit records, revoke/remove staging-only provider credentials from the staging secret store, and destroy or archive the isolated staging database according to owner policy. Do not run cleanup against Production identifiers. If preflight or acceptance is BLOCKED, preserve evidence and remediate the isolated staging environment before retrying.
