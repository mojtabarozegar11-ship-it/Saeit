# Saeit — cPanel / Python 3.11 deployment notes

This document describes the intended cPanel runtime. It does not perform deployment.

## Runtime
- Python: 3.11
- WSGI entrypoint: passenger_wsgi.py
- Django settings: config.settings
- Project entrypoint: manage.py
- Dependencies: requirements.txt
- Static output: staticfiles/

## Environment
Create a server-side .env file and never commit real secrets.
Required values include:
- SECRET_KEY
- DEBUG=False
- ALLOWED_HOSTS
- DATABASE_URL
- OPENAI_API_KEY (only when AI features are enabled)
- CSRF_TRUSTED_ORIGINS when the public HTTPS domain is known

## First server-side checks
1. Create/select the Python 3.11 application in cPanel.
2. Point the application to the Saeit repository working directory.
3. Configure the virtual environment.
4. Install requirements.txt.
5. Configure the WSGI entrypoint as passenger_wsgi.py.
6. Run migrations from the server environment.
7. Run collectstatic.
8. Check /api/health/.
9. Inspect application/error logs.

## Important
Do not place production secrets in GitHub.
Do not enable automatic production deployment until the application configuration and database are verified.
Do not run destructive migrations or data operations as part of an automated Git hook.
