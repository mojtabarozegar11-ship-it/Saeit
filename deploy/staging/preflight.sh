#!/bin/sh
set -eu
[ "${SAEIT_ENV:-}" = "staging" ] || { echo '{"result":"BLOCKED","reason":"SAEIT_ENV"}'; exit 2; }
python manage.py staging_preflight
