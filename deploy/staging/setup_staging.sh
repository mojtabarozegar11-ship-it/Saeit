#!/bin/sh
set -eu
test -f .env || { echo "BLOCKED: create .env from deploy/staging/.env.staging.example first"; exit 2; }
python -m pip install -r requirements.txt
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py seed_factory_agents
python manage.py staging_preflight
