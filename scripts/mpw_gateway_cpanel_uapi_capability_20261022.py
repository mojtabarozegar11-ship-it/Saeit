#!/usr/bin/env python3
"""Read-only cPanel UAPI capability probe: never disclose database identities."""
import json
import os
import shutil
import subprocess


def check():
    # In a restricted Passenger/SSH login shell the cPanel binary directory
    # is often absent from PATH even when the supported CLI is installed.
    # Accept only cPanel-owned absolute locations, never an untrusted PATH
    # shadow executable.  All operations below are strictly read-only.
    trusted_paths = (
        '/usr/local/cpanel/bin/uapi',
        '/usr/local/cpanel/bin/uapi.pl',
        '/usr/local/cpanel/3rdparty/bin/uapi',
    )
    discovered = shutil.which('uapi')
    if discovered:
        trusted_paths = (*trusted_paths, discovered)
    exe = next((p for p in trusted_paths
                if os.path.realpath(p).startswith('/usr/local/cpanel/')
                and os.path.isfile(p) and os.access(p, os.X_OK)), None)
    allowed = bool(exe)
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
