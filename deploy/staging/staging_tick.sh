#!/bin/sh
set -eu
cd "${SAEIT_STAGING_ROOT:-$HOME/Saeit-staging}"
test -f .env || exit 2
# Idempotently refresh time-bounded specialist grants and recover abandoned tasks.
python manage.py seed_factory_agents
python manage.py recover_stale_tasks --limit 50 --stale-after 900
