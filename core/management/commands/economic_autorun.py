"""Single-process-owner economic cycle with a host-wide, crash-safe lock."""

from contextlib import contextmanager
import fcntl
from io import StringIO
import os
from pathlib import Path
import stat

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


LOCK_DIR = Path.home() / "factory-runtime" / "private" / "master-agent"
LOCK_NAME = "economic-autorun.lock"


@contextmanager
def _exclusive_cycle_lock():
    """Hold one flock across the entire cycle, with no expiring cache TTL.

    The file may remain after a crash; the operating system releases the lock
    when the process exits. A foreign-owned or symlink target fails closed.
    """
    fd = None
    try:
        if LOCK_DIR.is_symlink():
            raise OSError("lock directory is a symlink")
        LOCK_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory = LOCK_DIR.stat()
        if (not stat.S_ISDIR(directory.st_mode) or
                directory.st_uid != os.geteuid() or
                directory.st_mode & 0o022):
            raise OSError("lock directory is not private and owner-controlled")
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(LOCK_DIR / LOCK_NAME, flags, 0o600)
        opened = os.fstat(fd)
        if (not stat.S_ISREG(opened.st_mode) or
                opened.st_uid != os.geteuid() or
                opened.st_mode & 0o077):
            raise OSError("lock file is not private and owner-controlled")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        if fd is not None:
            os.close(fd)
        yield False
        return
    except OSError as exc:
        if fd is not None:
            os.close(fd)
        raise CommandError(f"ECONOMIC_CYCLE_LOCK_UNAVAILABLE: {type(exc).__name__}") from exc
    try:
        yield True
    finally:
        os.close(fd)


class Command(BaseCommand):
    help = "Run one autonomous economic cycle: plan one concrete task, then execute it."

    def handle(self, *args, **options):
        with _exclusive_cycle_lock() as acquired:
            if not acquired:
                self.stdout.write("SKIP: economic cycle already running.")
                return
            plan_output = StringIO()
            worker_output = StringIO()
            call_command("online_income_cycle", stdout=plan_output)
            call_command("economic_worker", limit=1, stdout=worker_output)
            self.stdout.write(plan_output.getvalue().strip())
            self.stdout.write(worker_output.getvalue().strip())
            if "EXECUTED task=" in worker_output.getvalue():
                self.stdout.write("ECONOMIC_INTERNAL_TASK_EXECUTED revenue_not_assessed")
            else:
                self.stdout.write("ECONOMIC_NO_TASK_EXECUTED")
