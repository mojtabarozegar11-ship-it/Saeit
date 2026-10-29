#!/usr/bin/env python3
"""F->S read-only guest capacity triage. NEVER authorizes deployment."""
import argparse
import datetime as dt
import json
import sys

MIN_AVAILABLE = 2 * 1024**3
MAX_AGE = dt.timedelta(minutes=15)


def evaluate(snapshot, now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    blockers = []
    if snapshot.get('schema') != 'f01-vps-console-readonly.v1':
        blockers.append('UNRECOGNIZED_SCHEMA')
    if snapshot.get('read_only') is not True or snapshot.get('production_change') is not False:
        blockers.append('NOT_A_READ_ONLY_SNAPSHOT')
    try:
        observed = dt.datetime.fromisoformat(snapshot['observed_utc'])
        if observed.tzinfo is None or not dt.timedelta(0) <= now - observed <= MAX_AGE:
            blockers.append('STALE_OR_FUTURE_SNAPSHOT')
    except (KeyError, TypeError, ValueError):
        blockers.append('MISSING_OR_INVALID_TIMESTAMP')
    fs = snapshot.get('filesystem', {}).get('target_1', {})
    available = fs.get('available_bytes')
    if fs.get('state') != 'OBSERVED' or not isinstance(available, int) or isinstance(available, bool) or available < MIN_AVAILABLE:
        blockers.append('ROOT_DISK_RESERVE_UNVERIFIED_OR_LOW')
    guest = snapshot.get('guest', {})
    cpu = guest.get('cpu_count')
    load = guest.get('loadavg')
    if not isinstance(cpu, int) or cpu <= 0 or not isinstance(load, list) or len(load) < 1 or not isinstance(load[0], (int, float)) or load[0] > 4 * cpu:
        blockers.append('GUEST_CPU_LOAD_UNVERIFIED_OR_HIGH')
    pressure = snapshot.get('process_pressure', {})
    states = pressure.get('all_process_states', {})
    blocked_io = states.get('D') if isinstance(states, dict) else None
    fanout = pressure.get('factory_max_children_same_parent')
    if (pressure.get('state') != 'OBSERVED'
            or not isinstance(blocked_io, int) or isinstance(blocked_io, bool)
            or blocked_io > 8
            or not isinstance(fanout, int) or isinstance(fanout, bool)
            or fanout > 32):
        blockers.append('PROCESS_STORM_OR_IO_WAIT_UNVERIFIED_OR_HIGH')
    mem = guest.get('memory', {})
    mem_avail = mem.get('MemAvailable_kib') if isinstance(mem, dict) else None
    if not isinstance(mem_avail, int) or isinstance(mem_avail, bool) or mem_avail < 512 * 1024:
        blockers.append('GUEST_AVAILABLE_MEMORY_UNVERIFIED_OR_LOW')
    if snapshot.get('offhost_backup_restored') != 'VERIFIED':
        blockers.append('OFFHOST_RESTORE_UNVERIFIED')
    if snapshot.get('worker_running_verified') is not True:
        blockers.append('WORKER_EXECUTION_UNVERIFIED')
    return {'schema': 'f01-s01-release-preflight.v1', 'read_only': True,
            'guest_capacity_screen': 'PASS' if not blockers else 'NO_GO',
            'production_deployment_authorized': False,
            'required_independent_gates': ['S_OWNER_APPROVAL', 'DB_IDENTITY', 'OFFHOST_RESTORE', 'ROLLBACK', 'CHECKOUT_REGRESSION'],
            'blockers': sorted(set(blockers))}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('snapshot', help='JSON snapshot from existing F-01 guest collector')
    args = p.parse_args()
    try:
        with open(args.snapshot, encoding='utf-8') as f:
            data = json.load(f)
        report = evaluate(data)
    except (OSError, ValueError, TypeError):
        report = {'schema': 'f01-s01-release-preflight.v1', 'guest_capacity_screen': 'NO_GO',
                  'production_deployment_authorized': False, 'blockers': ['INPUT_UNAVAILABLE_OR_INVALID']}
    print(json.dumps(report, sort_keys=True))
    return 0 if report['guest_capacity_screen'] == 'PASS' else 2

if __name__ == '__main__':
    sys.exit(main())
