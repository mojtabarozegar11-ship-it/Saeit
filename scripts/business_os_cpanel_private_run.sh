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
  else
    code=$?
    case "$code" in
      71) echo 'BUSINESS_OS_PRIVATE_PATH_CHECK_FAILED';;
      72) echo 'BUSINESS_OS_PRIVATE_DJANGO_IMPORT_FAILED';;
      73) echo 'BUSINESS_OS_PRIVATE_DJANGO_SETUP_FAILED';;
      74) echo 'BUSINESS_OS_PRIVATE_MODEL_IMPORT_FAILED';;
      75) echo 'BUSINESS_OS_PRIVATE_REVIEW_LOAD_FAILED';;
      76) echo 'BUSINESS_OS_PRIVATE_QUERY_FAILED';;
      77) echo 'BUSINESS_OS_PRIVATE_REVIEW_FAILED';;
      78) echo 'BUSINESS_OS_PRIVATE_REPORT_WRITE_FAILED';;
      80) echo 'BUSINESS_OS_PRIVATE_DATABASE_CONNECTION_FAILED';;
      81) echo 'BUSINESS_OS_PRIVATE_TASK_QUERY_FAILED';;
      82) echo 'BUSINESS_OS_PRIVATE_BLOCKED_TASK_QUERY_FAILED';;
      83) echo 'BUSINESS_OS_PRIVATE_PRODUCT_QUERY_FAILED';;
      84) echo 'BUSINESS_OS_PRIVATE_ORDER_QUERY_FAILED';;
      85) echo 'BUSINESS_OS_PRIVATE_APPROVAL_QUERY_FAILED';;
      *) echo 'BUSINESS_OS_PRIVATE_UNCLASSIFIED_FAILURE';;
    esac
    exit 1
  fi
done
echo 'BUSINESS_OS_PRIVATE_DJANGO_RUNTIME_UNAVAILABLE'
exit 1
