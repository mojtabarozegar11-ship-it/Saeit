#!/usr/bin/env bash
set -euo pipefail
umask 077
base="$HOME/factory-runtime"
export SAEIT_ENV=production MOJ_FACTORY_LOCAL_MODE=1 DJANGO_SETTINGS_MODULE=config.settings
export MOJ_PAID_LLM_ENABLED=0 MOJ_LLM_DAILY_CALL_BUDGET=0 MOJ_LLM_MAX_COST_MINOR=0
cd "$base/django-app"
"$base/.venv/bin/python" manage.py factory_f41_enqueue --execute
