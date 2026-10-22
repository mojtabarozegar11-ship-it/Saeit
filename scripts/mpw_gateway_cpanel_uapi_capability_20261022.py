#!/usr/bin/env python3
"""Read-only cPanel UAPI capability probe: never disclose database identities."""
import json
import getpass
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
        'user_account_matches_expected': getpass.getuser() == 'zomorod2',
    }
    if not allowed:
        return result
    if result['user_account_matches_expected'] is not True:
        return result
    for function, label in (
        ('list_databases', 'mysql_list_databases_allowed'),
        ('list_users', 'mysql_list_users_allowed'),
    ):
        task = subprocess.run(
            [exe, '--user=zomorod2', '--output=json', 'Mysql', function],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=18, check=False,
        )
        result[label + '_exit_code'] = task.returncode
        if task.returncode:
            # Errors may contain private installation details. Report only a
            # fixed category, never stderr/stdout, usernames, paths or tokens.
            diagnostic = ((task.stderr or b'') + (task.stdout or b'')[:2000]).lower()
            markers = (
                (b'permission denied', 'os_permission'),
                (b'not authorized', 'authorization'),
                (b'access denied', 'authorization'),
                (b'license', 'license'),
                (b'cannot connect', 'service_connection'),
                (b'could not connect', 'service_connection'),
                (b'missing', 'missing_dependency'),
                (b'not found', 'missing_dependency'),
                (b'cloudlinux', 'cloudlinux_environment'),
                (b'invalid option', 'unsupported_option'),
                (b'unknown option', 'unsupported_option'),
            )
            result[label + '_error_category'] = next(
                (category for marker, category in markers if marker in diagnostic),
                'unclassified',
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
