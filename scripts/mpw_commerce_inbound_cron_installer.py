#!/usr/bin/env python3
"""Append exactly one safe noncustodial checkout-reconciler crontab entry.

Does not change existing jobs, storefront, shared Passenger, wallets, or funds.
Everything is scoped to the known cPanel account and a single private worker.
"""
import hashlib,json,os,re,shutil,stat,subprocess,sys,tempfile
from pathlib import Path

HOME=Path('/home/zomorod2')
ROOT=HOME/'.private_mojplaywin_main_agents'
APP=HOME/'Saeit-staging'
WORKER=ROOT/'mpw_commerce_live_inbound_reconciler.py'
PIN=HOME/'mojplaywin.com/passenger_wsgi.py'
PY=HOME/'virtualenv/Saeit-staging/3.11/bin/python'
MARK='# MPW_TWO_BOOKS_INBOUND_RECONCILER_20261019'
CRON=(
'* * * * * /usr/bin/flock -n '
'/home/zomorod2/.private_mojplaywin_main_agents/mpw_commerce_inbound.lock '
'/home/zomorod2/virtualenv/Saeit-staging/3.11/bin/python '
'/home/zomorod2/.private_mojplaywin_main_agents/mpw_commerce_live_inbound_reconciler.py '
'>/dev/null 2>&1 '+MARK
)
def run(command,input_data=None):
    return subprocess.run(command,input=input_data,text=True,capture_output=True,timeout=22)

def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()

def guard():
    if (ROOT.is_symlink() or APP.is_symlink() or WORKER.is_symlink() or PIN.is_symlink()
        or not ROOT.is_dir() or not APP.is_dir() or not PY.is_file()
        or not WORKER.is_file() or not (APP/'manage.py').is_file()
        or not PIN.is_file() or "APP='/home/zomorod2/Saeit-staging'" not in PIN.read_text('utf8','replace')
        or not Path('/usr/bin/flock').is_file() or not shutil.which('crontab')):
        raise RuntimeError('Bounded production prerequisites missing')
    if stat.S_IMODE(ROOT.stat().st_mode) & 0o077:
        raise RuntimeError('Private worker directory exposed')

def backup(run_id):
    return ROOT/('.mpw_crontab_before_'+run_id+'.private')
def planned(run_id):
    return ROOT/('.mpw_crontab_installed_'+run_id+'.sha')
def read_cron():
    result=run(['crontab','-l'])
    if result.returncode!=0:
        raise RuntimeError('Expected existing crontab unavailable; refusing overwrite')
    return result.stdout

def install(run_id):
    guard()
    old=read_cron()
    if old.count(MARK)>1:raise RuntimeError('Duplicate scheduler marker detected')
    if old.count(MARK)==1:
        if CRON not in old:raise RuntimeError('Unknown existing scheduler entry')
        print('MPW_RECONCILER_CRON='+json.dumps({'status':'already_present','existing_lines_preserved':True}))
        return
    before=backup(run_id)
    after=planned(run_id)
    if before.exists() or after.exists() or before.is_symlink() or after.is_symlink():
        raise RuntimeError('Backup collision')
    proposed=old.rstrip('\n')+'\n'+CRON+'\n'
    with before.open('x',encoding='utf8') as f:
        os.chmod(before,0o600)
        f.write(old);f.flush();os.fsync(f.fileno())
    if read_cron()!=old:raise RuntimeError('Crontab changed concurrently, untouched')
    fd,path=tempfile.mkstemp(dir=ROOT,prefix='.mpw_cron_',text=True)
    try:
        with os.fdopen(fd,'w',encoding='utf8') as f:
            f.write(proposed);f.flush();os.fsync(f.fileno())
        result=run(['crontab',path])
        if result.returncode!=0:raise RuntimeError('Cron install rejected')
    finally:
        if os.path.exists(path):os.unlink(path)
    observed=read_cron()
    if observed!=proposed:
        raise RuntimeError('Installed cron mismatch; reconcile manually using private backup')
    with after.open('x',encoding='utf8') as f:
        os.chmod(after,0o600);f.write(sha(proposed)+'\n')
    print('MPW_RECONCILER_CRON='+json.dumps({
        'status':'installed','cadence':'every_minute','previous_entries_preserved':True,
        'prior_line_count':len(old.splitlines()),'current_line_count':len(observed.splitlines()),
        'wallet_withdrawal_enabled':False,'payment_flow_modified':False
    }))

def rollback(run_id):
    guard()
    before=backup(run_id);after=planned(run_id)
    if before.is_symlink() or after.is_symlink() or not before.is_file() or not after.is_file():
        raise RuntimeError('Rollback evidence absent')
    original=before.read_text('utf8');installed=read_cron()
    if sha(installed)!=after.read_text('utf8').strip():
        raise RuntimeError('Cron changed since install; refuse unrelated overwrite')
    fd,path=tempfile.mkstemp(dir=ROOT,prefix='.mpw_cron_restore_',text=True)
    try:
        with os.fdopen(fd,'w') as f:f.write(original)
        result=run(['crontab',path])
        if result.returncode!=0:raise RuntimeError('Unable to restore cron')
    finally:
        if os.path.exists(path):os.unlink(path)
    if read_cron()!=original:raise RuntimeError('Rollback verify failed')
    print('MPW_RECONCILER_ROLLBACK=PASS')

if __name__=='__main__':
    if len(sys.argv)!=3 or sys.argv[1] not in ('install','rollback') or not re.fullmatch(r'[0-9]{8,20}',sys.argv[2]):
        raise SystemExit('Usage: installer.py install|rollback RUN_ID')
    (install if sys.argv[1]=='install' else rollback)(sys.argv[2])
