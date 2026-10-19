"""Primary worker. Exclusive lock, durable tasks, bounded actions, stable log."""
import fcntl, json, os, sys, time
from pathlib import Path
ROOT = Path('/home/zomorod2/Saeit')
LOCK = Path('/home/zomorod2/logs/moj-1ro-1-runtime.lock')
STATE = ROOT / 'var/moj_runtime/state.json'
INTERVAL = 10
ROOT.mkdir(parents=True, exist_ok=True)
stream = LOCK.open('a')
try:
    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
except BlockingIOError:
    sys.exit(0)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
sys.path.insert(0, str(ROOT))
import django
django.setup()
from core.moj_1ro.foundation_runtime import tick, atomic_json, VERSION
try:
    count = int(json.loads(STATE.read_text()).get('cycle', 0))
except (OSError, ValueError, TypeError):
    count = 0
while True:
    started = time.monotonic()
    count += 1
    try:
        # EXECUTIVE_SCHEDULER_INTEGRATION
        from core.moj_1ro.executive_runtime import tick as executive_tick
        from core.moj_1ro.foundation_runtime import business_snapshot
        frame = executive_tick(count) if count % 3 == 0 else None
        if frame and frame['outcome']['state'] != 'idle':
            result = {'goal':'executive_portfolio','task_states':frame['states'],
                      'outcome':frame['outcome'],'business':business_snapshot()}
        else:
            result = tick(count)
        atomic_json(STATE, {'cycle': count, 'architecture': VERSION,
                           'updated_at': time.time(), 'outcome': result['outcome']['state']})
        print(time.strftime('%F %T'), json.dumps({
            'cycle': count, 'architecture': VERSION, 'goal': result['goal'],
            'task_states': result['task_states'], 'outcome': result['outcome']['state'],
            'reason': result['outcome'].get('reason'),
            'business': result['business']}, ensure_ascii=False), flush=True)
    except Exception as exc:
        print(json.dumps({'cycle': count, 'state': 'failed',
                          'error': type(exc).__name__}), flush=True)
    time.sleep(max(1, INTERVAL - (time.monotonic() - started)))
