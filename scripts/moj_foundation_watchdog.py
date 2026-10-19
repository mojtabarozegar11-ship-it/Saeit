"""Restart the sole primary worker after a crash. Worker lock prevents duplicates."""
import fcntl, subprocess
from pathlib import Path
ROOT = Path('/home/zomorod2/Saeit')
LOCK = Path('/home/zomorod2/logs/moj-1ro-1-runtime.lock')
with LOCK.open('a') as stream:
    try:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(0)
with Path('/home/zomorod2/logs/moj-foundation-v2.log').open('ab') as log:
    worker = subprocess.Popen(
        ['/home/zomorod2/virtualenv/Saeit/3.11/bin/python', '-u',
         'core/moj_1ro/revenue_scheduler.py'], cwd=ROOT,
        stdin=subprocess.DEVNULL, stdout=log, stderr=log,
        start_new_session=True, close_fds=True)
print('primary_worker_started', worker.pid)
