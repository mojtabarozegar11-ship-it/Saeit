#!/usr/bin/env python3
"""Read-only proof that the cron scheduler (not only a manual run) is alive."""
import datetime as dt,json,subprocess
from pathlib import Path


def classify_reconciler_line(line):
    success=any('reconcile_MPW_COMMERCE_RECONCILE_state='+state in line
                for state in ('idle','scanned'))
    failure=any(value in line for value in (
        'reconcile_failed','reconcile_exception','reconcile_timeout',
        'reconcile_disabled','reconcile_MPW_COMMERCE_RECONCILE_state=disabled'))
    return success and not failure, failure


home=Path('/home/zomorod2')
path=home/'.private_mojplaywin_main_agents/mpw_commerce_reconcile_20261019.log'
cron=subprocess.run(['crontab','-l'],capture_output=True,text=True,timeout=20)
marker='MPW_TWO_BOOKS_INBOUND_RECONCILER_20261019'
data={'cron_readable':cron.returncode==0,
  'entry_count':cron.stdout.count(marker),
  'entry_once_per_minute':sum(x.lstrip().startswith('* * * * * ') and marker in x for x in cron.stdout.splitlines())==1,
  'log_exists':path.is_file() and not path.is_symlink(),
  'cron_heartbeat_distinguished_from_manual':False,
  'last_reconciler_success':False,
  'heartbeat_fresh':False,
  'observed_run_count_last_five_minutes':0}
if data['log_exists']:
    # Read only a bounded tail; the reconciler log may be long-lived.
    with path.open('rb') as handle:
        handle.seek(0,2)
        size=handle.tell()
        handle.seek(max(0,size-65536))
        lines=handle.read(65536).decode('utf8','replace').splitlines()
    if size>65536:
        lines=lines[1:]
    now=dt.datetime.now(dt.timezone.utc)
    recent=[]
    for line in lines[-100:]:
        try: stamp=dt.datetime.fromisoformat(line.split(' ',1)[0])
        except Exception:continue
        age=(now-stamp).total_seconds()
        if age>=-30 and age<=300:
            success,failure=classify_reconciler_line(line)
            recent.append({'age_seconds':round(age),
                           'reconciler_success':success,
                           'failure':failure})
    data['recent_runs']=recent[-12:]
    data['heartbeat_fresh']=bool(recent and recent[-1]['age_seconds']<=180)
    data['observed_run_count_last_five_minutes']=len(recent)
    # Evidence of a repeated schedule, but not cryptographic proof of origin.
    data['cron_heartbeat_distinguished_from_manual']=any(
        35 <= abs(a['age_seconds']-b['age_seconds']) <= 90
        for a,b in zip(recent,recent[1:])
        if a['reconciler_success'] and b['reconciler_success']
        and not a['failure'] and not b['failure']
    )
    data['last_reconciler_success']=bool(recent and recent[-1]['reconciler_success']
                                         and not recent[-1]['failure'])
print('MPW_PAYMENT_CRON_HEARTBEAT='+json.dumps(data,sort_keys=True))

