#!/usr/bin/env python3
"""Read-only VPS state signals for safe factory-subdomain repair planning.

No service restarts, no code changes, no credential/log contents, no raw process
arguments, and no transaction, factory, or database mutations.
"""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
from collections import Counter
from pathlib import Path


MATCH = re.compile(r'factory|saeit|production|product|farm[_-]|zomorod', re.I)
SERVICE = re.compile(r'^[A-Za-z0-9_.@\-]+\.service$')
TIMER = re.compile(r'^[A-Za-z0-9_.@\-]+\.timer$')


def run_readonly(args: list[str], timeout: int = 12) -> tuple[str, str]:
    try:
        completed = subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, check=False)
        if completed.returncode:
            return 'UNAVAILABLE', ''
        return 'OK', completed.stdout[:200000]
    except (OSError, subprocess.TimeoutExpired):
        return 'UNAVAILABLE', ''


def matching_units(kind: str) -> dict[str, object]:
    status, output = run_readonly(
        ['systemctl', 'list-units', '--all', '--type=' + kind,
         '--no-legend', '--no-pager', '--plain'])
    if status != 'OK':
        return {'status': status}
    rows = []
    for line in output.splitlines():
        fields = line.strip().lstrip('●').split()
        if len(fields) < 4:
            continue
        name = fields[0]
        pattern = SERVICE if kind == 'service' else TIMER
        if pattern.fullmatch(name) and MATCH.search(name):
            rows.append({'name': name, 'load': fields[1],
                         'active': fields[2], 'sub': fields[3]})
    return {'status': 'OK', 'matching_units': rows[:45]}


def matching_unit_files() -> dict[str, object]:
    status, output = run_readonly(
        ['systemctl', 'list-unit-files', '--type=service',
         '--no-legend', '--no-pager', '--plain'])
    if status != 'OK':
        return {'status': status}
    rows = []
    for line in output.splitlines():
        fields = line.strip().split()
        if len(fields) >= 2 and SERVICE.fullmatch(fields[0]) and MATCH.search(fields[0]):
            rows.append({'name': fields[0], 'state': fields[1]})
    return {'status': 'OK', 'matching_unit_files': rows[:45]}


def listening_ports() -> dict[str, object]:
    status, output = run_readonly(['ss', '-ltnH'])
    if status != 'OK':
        return {'status': status}
    ports: set[int] = set()
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 4:
            continue
        match = re.search(r':(\d{1,5})$', fields[3])
        if match:
            port = int(match.group(1))
            if port in (80, 443, 3000, 5000, 8000, 8080, 8443) or 8001 <= port <= 8999:
                ports.add(port)
    return {'status': 'OK', 'selected_web_ports': sorted(ports)}


def local_dns() -> dict[str, object]:
    names = ['factory.zomorodmelal.ir', 'zomorodmelal.ir']
    results = {}
    for name in names:
        try:
            results[name] = sorted({record[4][0] for record in
                                    socket.getaddrinfo(name, None, proto=socket.IPPROTO_TCP)})
        except OSError:
            results[name] = ['UNRESOLVED']
    return results


def app_process_counts() -> dict[str, object]:
    # /proc/<pid>/comm exposes only the short executable name, never arguments.
    counts: Counter[str] = Counter()
    for path in Path('/proc').glob('[0-9]*/comm'):
        try:
            value = path.read_text('utf-8', 'replace').strip()
            if value in ('python', 'python3', 'gunicorn', 'uvicorn',
                         'nginx', 'apache2', 'httpd', 'lshttpd'):
                counts[value] += 1
        except OSError:
            continue
    return {'executable_name_counts': dict(sorted(counts.items()))}


def main() -> None:
    user = os.environ.get('USER', '')
    uid = os.geteuid()
    print('FACTORY_VPS_READONLY_DIAGNOSTIC=' + json.dumps({
        'effective_uid_nonroot': uid != 0,
        'configured_ssh_user_is_githubops': user == 'githubops',
        'factory_related_services': matching_units('service'),
        'factory_related_timers': matching_units('timer'),
        'matching_service_files': matching_unit_files(),
        'web_listeners': listening_ports(),
        'dns': local_dns(),
        'process_name_counts': app_process_counts(),
        'changes_performed': False,
    }, sort_keys=True))
    print('FACTORY_VPS_READONLY_COMPLETE=1')


if __name__ == '__main__':
    main()
