#!/bin/sh
set -eu
test -f .env || { echo '{"result":"BLOCKED","reason":"missing .env"}'; exit 2; }
python manage.py staging_preflight
