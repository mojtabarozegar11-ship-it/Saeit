#!/bin/sh
set -eu
[ "${SAEIT_ENV:-}" = "staging" ] || { echo "BLOCKED: SAEIT_ENV must be staging"; exit 2; }
[ "${DEBUG:-}" = "False" ] || { echo "BLOCKED: DEBUG must be False"; exit 2; }
for v in DATABASE_URL STAGING_DB_IDENTITY PRODUCTION_DB_IDENTITY SAEIT_BRIDGE_SECRET FACTORY_RESEARCH_PROVIDER FACTORY_RESEARCH_PROVIDER_TIER; do
  eval "value=\${$v:-}"
  [ -n "$value" ] || { echo "BLOCKED: missing $v"; exit 2; }
done
[ "$STAGING_DB_IDENTITY" != "$PRODUCTION_DB_IDENTITY" ] || { echo "BLOCKED: staging DB identity equals Production"; exit 2; }
[ "$FACTORY_RESEARCH_PROVIDER_TIER" = "staging" ] || { echo "BLOCKED: provider tier must be staging"; exit 2; }
python -m pip install -r requirements.txt
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py staging_preflight
