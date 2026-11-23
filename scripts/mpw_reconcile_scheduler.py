"""Owner-local cron runner for the gated MojPlayWin reconciliation command.
No GitHub dependency. Install only after production approval.
"""
import ast
import hashlib
import fcntl
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

ROOT = Path("/home/zomorod2/Saeit-mojprop-candidate-20261122")
PUBLIC_WSGI = Path("/home/zomorod2/mojplaywin.com/passenger_wsgi.py")
PYTHON = Path("/home/zomorod2/virtualenv/Saeit-staging/3.11/bin/python")
STATE = Path("/home/zomorod2/.local/share/mpw-reconcile")
LIMIT = 3
# Reviewed bounded existing-invoice command; *source* bytes only, NOT approval
# for a cron install or permission to change customer finances.
PAYMENT_COMMAND_BLOB = "b401e229a5c53c20cf4a110fdf501d68d5a24737"
PAYMENT_COMMAND_PATH = "core/management/commands/mpw_reconcile_pending_trx.py"


def require_effective_wsgi_source():
    """Fail closed if this owner-local writer targets a different app than live WSGI.

    Parsing the startup file as data never imports/executes it. A preview or
    staging Django tree must not reconcile live invoices by accident.
    """
    if PUBLIC_WSGI.is_symlink() or not PUBLIC_WSGI.is_file():
        raise ValueError("Live WSGI root cannot be established")
    tree = ast.parse(PUBLIC_WSGI.read_text(encoding="utf-8"))
    app_values = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "APP"
            for target in node.targets
        ):
            if not isinstance(node.value, ast.Constant) or type(node.value.value) is not str:
                raise ValueError("Live WSGI APP must be one literal path")
            app_values.append(node.value.value)
    if len(app_values) != 1 or not Path(app_values[0]).is_absolute():
        raise ValueError("Live WSGI APP is absent or ambiguous")
    if Path(app_values[0]) != ROOT or ROOT.resolve() != ROOT:
        raise ValueError("Scheduler source differs from live WSGI APP; no settlement run")


def require_reviewed_payment_command():
    """Never run a stale, symlinked, or unreviewed finance command."""
    command = ROOT / PAYMENT_COMMAND_PATH
    if command.is_symlink() or command.parent.is_symlink() or not command.is_file():
        raise ValueError("Reviewed local payment command is missing or unsafe")
    info = command.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not 1000 <= info.st_size <= 20000:
        raise ValueError("Reviewed payment command has unsafe file metadata")
    raw = command.read_bytes()
    blob = hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\\0" + raw).hexdigest()
    if blob != PAYMENT_COMMAND_BLOB:
        raise ValueError("Payment command differs from pinned reviewed source")


def private_dir(path):
    if not path.is_absolute() or path.resolve() != path:
        raise ValueError("Unsafe state directory")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    st = path.stat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise ValueError("State directory must be owner-only")


def read_cursor(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return 0
    with os.fdopen(fd, "rb") as source:
        st = os.fstat(source.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077 or st.st_size > 64:
            raise ValueError("Invalid cursor file")
        raw = source.read(65)
    cursor = json.loads(raw)
    if type(cursor) is not int or not 0 <= cursor < 2**63:
        raise ValueError("Invalid cursor")
    return cursor


def store_cursor(path, cursor):
    if type(cursor) is not int or not 0 <= cursor < 2**63:
        raise ValueError("Invalid result cursor")
    fd, tmp = tempfile.mkstemp(prefix=".cursor-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as out:
            json.dump(cursor, out)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def validate_result(raw, cursor, limit):
    rows = [line for line in raw.splitlines() if line.startswith("{")]
    if len(rows) != 1:
        raise ValueError("Missing command result")
    data = json.loads(rows[0])
    keys = {"scanned", "paid", "pending", "deferred", "next_after_id"}
    if type(data) is not dict or set(data) != keys or any(type(data[k]) is not int or data[k] < 0 for k in keys):
        raise ValueError("Invalid result")
    if data["scanned"] > limit or sum(data[k] for k in ("paid", "pending", "deferred")) != data["scanned"]:
        raise ValueError("Inconsistent batch")
    next_id = data["next_after_id"]
    if (next_id != 0 and (data["scanned"] != limit or next_id <= cursor or next_id >= 2**63)
            or next_id == 0 and data["scanned"] == limit):
        raise ValueError("Invalid continuation")
    return data


def run():
    if ROOT.resolve() != ROOT or not (ROOT/"manage.py").is_file() or not PYTHON.is_file():
        raise ValueError("Owner runtime unavailable")
    require_effective_wsgi_source()
    require_reviewed_payment_command()
    private_dir(STATE)
    fd = os.open(STATE/"run.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(fd, "rb+") as lock:
        st = os.fstat(lock.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
            raise ValueError("Unsafe runner lock")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"overlap_skipped": True}
        cursor = read_cursor(STATE/"cursor.json")
        result = subprocess.run(
            [str(PYTHON), "-B", str(ROOT/"manage.py"), "mpw_reconcile_pending_trx",
             "--after-id", str(cursor), "--limit", str(LIMIT)],
            cwd=ROOT, capture_output=True, text=True, timeout=240,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, check=False,
        )
        if result.returncode != 0:
            raise RuntimeError("Reconciliation command failed")
        data = validate_result(result.stdout, cursor, LIMIT)
        store_cursor(STATE/"cursor.json", data["next_after_id"])
        return data


if __name__ == "__main__":
    try:
        print("MPW_RECONCILE_SCHEDULER=" + json.dumps(run(), sort_keys=True))
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print("MPW_RECONCILE_SCHEDULER_ERROR=" + type(exc).__name__, file=sys.stderr)
        sys.exit(1)
