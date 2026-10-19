#!/usr/bin/env python3
"""Read-only proof that the cron scheduler (not only a manual run) is alive."""
import datetime as dt,json,subprocess
from pathlib import Path
home=Path('/home/zomorod2')
path=home/'.private_mojplaywin_main_agents/mpw_commerce_reconcile_20261019.log'
cron=subprocess.run(['crontab','-l'],capture_output=True,text=True,timeout=20)
marker='MPW_TWO_BOOKS_INBOUND_RECONCILER_20261019'
data={'cron_readable':cron.returncode==0,
  'entry_count':cron.stdout.count(marker),
  'entry_once_per_minute':sum(x.lstrip().startswith('* * * * * ') and marker in x for x in cron.stdout.splitlines())==1,
  'log_exists':path.is_file() and not path.is_symlink(),
  'cron_heartbeat_distinguished_from_manual':False}
if data['log_exists']:
    lines=path.read_text('utf8','replace').splitlines()
    now=dt.datetime.now(dt.timezone.utc)
    recent=[]
    for line in lines[-100:]:
        try: stamp=dt.datetime.fromisoformat(line.split(' ',1)[0])
        except Exception:continue
        age=(now-stamp).total_seconds()
        if age>=-30 and age<=300:
            recent.append({'age_seconds':round(age),
                           'reconciler_success':'reconcile_MPW_COMMERCE_RECONCILE_state=' in line,
                           'failure':'reconcile_failed' in line or 'reconcile_timeout' in line})
    data['recent_runs']=recent[-12:]
    data['heartbeat_fresh']=bool(recent and recent[-1]['age_seconds']<=180)
    data['observed_run_count_last_five_minutes']=len(recent)
    data['cron_heartbeat_distinguished_from_manual']=len(recent)>=2
print('MPW_PAYMENT_CRON_HEARTBEAT='+json.dumps(data,sort_keys=True))
