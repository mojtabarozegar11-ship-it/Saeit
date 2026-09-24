# SAEIT — AI-Native Deep Research Platform

Production-oriented Django foundation for the research, knowledge, data, agent orchestration, approval, audit, and revenue platform defined in the master architecture.

Repository scope: this project only.

## Runtime safety

The execution path is governed by capability, risk, owner-approval, execution-identity, retry-budget, and audit controls. Production-changing or other sensitive actions must pass the approval gate before execution.

## Production checks

Run the read-only readiness gate before deployment:

```bash
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py production_gate
```

The production gate fails closed when required production settings, database connectivity, migrations, or runtime health checks are not satisfied.

## Stale-task recovery

A bounded recovery pass is available for a host scheduler/cron:

```bash
python manage.py recover_stale_tasks --limit 50 --stale-after 900
```

The command only considers running tasks older than the configured threshold and delegates the state transition to the controlled task runtime.

For cPanel deployment, configure this command as a periodic cron job **after** the application environment/virtualenv is verified. Do not run it against an unverified production database.

## CI

The repository includes automated Django checks, migration consistency checks, tests, and a production-readiness gate. A green CI result is required before production deployment.

## Deployment boundary

GitHub is the development/source-of-truth stage. cPanel/Passenger deployment is a separate production stage and must be validated independently; historical deployment commits are not treated as proof of current server health.
