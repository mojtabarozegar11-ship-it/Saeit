#!/usr/bin/env python3
"""Read-only cPanel UAPI capability probe: never disclose database identities."""
import json
import os
import shutil
import subprocess


def check():
    exe = shutil.which('uapi')
    allowed = exe and os.path.realpath(exe).startswith('/usr/local/cpanel/')
    result = {
        'probe': 'MPW_CPANEL_UAPI_READONLY',
        'uapi_available': bool(allowed),
        'mysql_list_databases_allowed': False,
        'mysql_list_users_allowed': False,
        'no_database_creation_attempted': True,
        'no_passwords_or_database_names_logged': True,
        'writes': 0,
    }
    if not allowed:
        return result
    for function, label in (
        ('list_databases', 'mysql_list_databases_allowed'),
        ('list_users', 'mysql_list_users_allowed'),
    ):
        task = subprocess.run(
            [exe, '--output=json', 'Mysql', function],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=18, check=False,
        )
        if task.returncode != 0 or len(task.stdout) > 500000:
            continue
        try:
            data = json.loads(task.stdout)
            status = data.get('result', {}).get('status')
            result[label] = status in (1, True)
        except (ValueError, AttributeError, TypeError):
            pass
    return result


if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True))
