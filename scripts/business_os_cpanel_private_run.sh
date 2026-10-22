#!/usr/bin/env bash
# Discover the already-installed Django interpreter without changing cPanel.
# No business observation or Python traceback is ever sent over SSH.
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
if [[ "$PWD" != /home/zomorod2/Saeit-staging/releases/business-os-* ]]; then
  echo 'BUSINESS_OS_PRIVATE_STAGE_PATH_UNEXPECTED'
  exit 1
fi
if [[ ! -f /home/zomorod2/Saeit/config/settings.py ]]; then
  echo 'BUSINESS_OS_PRODUCTION_DJANGO_PATH_UNAVAILABLE'
  exit 1
fi

for interpreter in \
  /home/zomorod2/Saeit/.venv/bin/python \
  /home/zomorod2/Saeit/venv/bin/python \
  /home/zomorod2/virtualenv/Saeit/3.11/bin/python \
  /home/zomorod2/virtualenv/Saeit/3.11/bin/python3 \
  /home/zomorod2/virtualenv/Saeit/3.10/bin/python \
  /home/zomorod2/virtualenv/Saeit/3.12/bin/python \
  /usr/local/bin/python3 \
  /usr/bin/python3; do
  if [[ ! -x "$interpreter" ]]; then
    continue
  fi
  if ! "$interpreter" -B -c 'import django' > /dev/null 2>&1; then
    continue
  fi
  if "$interpreter" -B scripts/business_os_cpanel_private_metrics.py > /dev/null 2>&1; then
    echo 'BUSINESS_OS_PRIVATE_REPORT_CREATED_ON_CPANEL'
    exit 0
  fi
  echo 'BUSINESS_OS_PRIVATE_DJANGO_READ_FAILED'
  exit 1
done
echo 'BUSINESS_OS_PRIVATE_DJANGO_RUNTIME_UNAVAILABLE'
exit 1
