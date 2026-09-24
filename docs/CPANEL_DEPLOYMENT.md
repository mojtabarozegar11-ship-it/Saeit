# Saeit — cPanel / Passenger deployment runbook

This runbook is a non-destructive deployment sequence. It does not authorize destructive database or filesystem operations.

## 1. Application root

Expected production project root:

`/home/zomorodm/repositories/Saeit`

Passenger startup file:

`passenger_wsgi.py`

Django settings:

`config.settings`

## 2. Python / virtual environment

Use a dedicated cPanel Python application and virtual environment.

The repository CI targets Python 3.11. Verify that the cPanel application itself uses a compatible Python version; the shell's default Python version is not sufficient evidence.

Install dependencies with the application's interpreter:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 3. Production environment

Create a server-only `.env` from `.env.example`.

Required production configuration:

- `SECRET_KEY`: unique random secret
- `DEBUG=False`
- `ALLOWED_HOSTS`: real hostname(s)
- `CSRF_TRUSTED_ORIGINS`: real HTTPS origin(s)
- `DATABASE_URL`: intended PostgreSQL database
- `SECURE_SSL_REDIRECT=True`
- `SESSION_COOKIE_SECURE=True`
- `CSRF_COOKIE_SECURE=True`

Optional AI configuration:

- `OPENAI_API_KEY`
- `OPENAI_CHAT_MODEL`

Never commit `.env` or real credentials.

## 4. Database preflight

Before migration, verify the database target and connectivity.

Then run:

```bash
python manage.py migrate --noinput
```

Do not use `flush`, database reset, destructive SQL, or database recreation as part of deployment.

## 5. Static files

Run:

```bash
python manage.py collectstatic --noinput
```

Then verify that the web server serves `/static/` correctly.

## 6. Production gate

Run all of:

```bash
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py production_gate
```

A failed production gate blocks release.

## 7. Passenger runtime

Verify:

- Passenger loads `passenger_wsgi.py`
- no import/startup exception occurs
- Django settings load successfully
- application logs contain no startup traceback

## 8. Runtime verification

Verify:

- `/api/health/`
- `/api/`
- authentication
- owner scoping
- approval decision flow
- task claim / heartbeat / complete / fail
- stale-task recovery
- audit records

## 9. Recovery scheduler

Only after the application and database are verified, configure a bounded cPanel cron using the exact production virtualenv interpreter:

```bash
python manage.py recover_stale_tasks --limit 50 --stale-after 900
```

Do not configure the cron against an unverified environment.

## 10. Release / rollback boundary

Before changing production code:

1. Record the current deployed commit SHA.
2. Preserve a known-good application release.
3. Confirm database backup/restore procedures independently.
4. Deploy the new release.
5. Run the production gate and runtime checks.

Application rollback must not automatically reset or delete production data.

## 11. Final acceptance

The deployment is accepted only when:

1. Passenger starts successfully.
2. Production Gate is green.
3. Health endpoint responds.
4. Authentication/authorization behave correctly.
5. Master Agent approval controls behave correctly.
6. Task execution/recovery behaves correctly.
7. Audit records are created.
8. No new startup/runtime errors appear in application/web-server logs.

Record the exact deployed Git commit SHA with the acceptance result.
