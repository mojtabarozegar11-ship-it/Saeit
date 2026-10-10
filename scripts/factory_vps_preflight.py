#!/usr/bin/env python3
"""Read-only factory runtime preflight: no database writes or services."""
import os
import pathlib
import sys

root = pathlib.Path.home() / 'factory-runtime'
paths = {
    'django_manage': root / 'django-app/manage.py',
    'django_settings': root / 'django-app/config/settings.py',
    'factory_models': root / 'django-app/core/models.py',
    'python_venv': root / '.venv/bin/python',
    'private_snapshot': pathlib.Path.home() / 'factory-transfer-incoming/private-db/factory-migration-snapshot.sqlite3',
}
for name, path in paths.items():
    print(f'{name}: {"OK" if path.is_file() else "MISSING"}')
if not all(path.is_file() for path in paths.values()):
    sys.exit(1)
print('Read-only preflight complete; no cutover performed.')
