#!/usr/bin/env bash
# Existing F41 moj_1ro_1 queue plus independent read-only Shasta finality sidecar.
set -euo pipefail
umask 077
base="$HOME/factory-runtime"
export SAEIT_ENV=production MOJ_FACTORY_LOCAL_MODE=1 DJANGO_SETTINGS_MODULE=config.settings
export MOJ_PAID_LLM_ENABLED=0 MOJ_LLM_DAILY_CALL_BUDGET=0 MOJ_LLM_MAX_COST_MINOR=0
cd "$base/django-app"
"$base/.venv/bin/python" manage.py factory_f41_enqueue --execute
# Runs only AFTER authentic AgentTask verification. No automatic customer delivery.
PYTHONPATH="$base/operations/f41-multiproduct" \
  "$base/.venv/bin/python" -B "$base/operations/f41-multiproduct/factory_f41_auto_finality_scan.py" --execute
