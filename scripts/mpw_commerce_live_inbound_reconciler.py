#!/usr/bin/env python3
"""Main-MojPlayWin-only cron worker for incoming ETH/TRX invoices.

No transfer, withdrawal, refund, swap, private-key operations or browser access.
Use with a single-user flock lock. Invokes the already audited Django command;
its trusted chain checks are the only mechanism allowed to authorize fulfillment.
"""
import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path

HOME=Path('/home/zomorod2')
APP=HOME/'Saeit-staging'
VENV=HOME/'virtualenv/Saeit-staging/3.11/bin/python'
WSGI=HOME/'mojplaywin.com/passenger_wsgi.py'
ROOT=HOME/'.private_mojplaywin_main_agents'
LOG=ROOT/'mpw_commerce_reconcile_20261019.log'
STATUS=re.compile(r'^MPW_COMMERCE_RECONCILE state=(idle|disabled|scanned) pending=([0-9]{1,8}) matched=([0-9]{1,8}) paid=([0-9]{1,8}) rejected=([0-9]{1,8})$',re.M)

def guard():
    if (APP.is_symlink() or ROOT.is_symlink() or WSGI.is_symlink()
        or not APP.is_dir() or not ROOT.is_dir() or not VENV.is_file()
        or not WSGI.is_file() or not (APP/'manage.py').is_file()
        or "APP='/home/zomorod2/Saeit-staging'" not in WSGI.read_text('utf8','replace')):
        raise RuntimeError('Main application scope mismatch')

def report(state,code=0):
    stamp=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    # Never log customer PII, wallet address, invoice identifier or transaction hash.
    line=f"{stamp} {state}\n"
    if LOG.is_symlink():raise RuntimeError('Log symlink blocked')
    if LOG.exists() and LOG.stat().st_size > 262144:
        rotated=LOG.with_suffix('.previous.log')
        if rotated.is_symlink():raise RuntimeError('Rotated log symlink blocked')
        os.replace(LOG,rotated)
    fd=os.open(LOG,os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'a',encoding='utf8') as f:
        f.write(line)
    return code

def run():
    guard()
    env=os.environ.copy()
    env['DJANGO_SETTINGS_MODULE']='config.settings'
    try:
        res=subprocess.run([str(VENV),str(APP/'manage.py'),'mpw_commerce_reconcile'],
            cwd=str(APP),env=env,capture_output=True,text=True,
            timeout=50,check=False)
        found=STATUS.search(res.stdout[:5000])
        if res.returncode==0 and found:
            return report('reconcile_'+found.group(0).replace(' ','_'),0)
        return report('reconcile_failed_exit='+str(res.returncode),1)
    except subprocess.TimeoutExpired:
        return report('reconcile_timeout',1)
    except Exception as e:
        return report('reconcile_exception_'+type(e).__name__,1)

if __name__=='__main__':
    if sys.argv[1:] not in ([],['--once']):
        raise SystemExit('Only --once supported; never pass wallet credentials')
    sys.exit(run())
