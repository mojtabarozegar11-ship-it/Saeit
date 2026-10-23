#!/usr/bin/env python3
"""Bounded VPS Stage4 retry-to-task bridge, preserving every existing gate.

This does not fabricate research, approve products, change evidence budgets,
or publish anything. It only asks the installed factory master to plan the
next already-authorized validation when a persisted retry becomes due.
"""
import argparse
from collections import Counter
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import sys
import tempfile


CURSOR_SCHEMA = "saeit.factory.stage4-due-dispatch.cursor.v1"


def read_cursor(root):
    """Resume beyond the previous bounded batch without trusting arbitrary state."""
    path = root / "stage4-due-dispatch.cursor.json"
    if path.is_symlink():
        raise RuntimeError("STAGE4_DISPATCH_CURSOR_SYMLINK")
    if not path.exists():
        return 0
    if not path.is_file() or path.stat().st_size > 1024:
        raise RuntimeError("STAGE4_DISPATCH_CURSOR_INVALID")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise RuntimeError("STAGE4_DISPATCH_CURSOR_INVALID") from exc
    cursor = data.get("last_pk") if isinstance(data, dict) and data.get("schema") == CURSOR_SCHEMA else None
    if type(cursor) is not int or not 0 <= cursor <= 2**63 - 1:
        raise RuntimeError("STAGE4_DISPATCH_CURSOR_INVALID")
    return cursor


def write_cursor(root, last_pk):
    """Atomically checkpoint scanned IDs, never changing product or QC records."""
    path = root / "stage4-due-dispatch.cursor.json"
    if path.is_symlink():
        raise RuntimeError("STAGE4_DISPATCH_CURSOR_SYMLINK")
    fd, temp = tempfile.mkstemp(prefix=".stage4-cursor-", dir=root)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump({"schema": CURSOR_SCHEMA, "last_pk": last_pk}, stream)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def candidate_window(manager, cursor, limit):
    """Page after the saved PK, wrapping exactly once to avoid starvation."""
    after = list(manager.filter(pk__gt=cursor).order_by("pk").values_list(
        "pk", "metadata")[:limit])
    if len(after) == limit:
        return after
    before = list(manager.filter(pk__lte=cursor).order_by("pk").values_list(
        "pk", "metadata")[:limit - len(after)])
    return after + before


def due_retry(metadata, now):
    """Return an aware due date only for a valid Stage4 retry window."""
    if not isinstance(metadata, dict):
        return None
    validation = metadata.get("validation")
    if not isinstance(validation, dict):
        return None
    progress = validation.get("stage4_research")
    if not isinstance(progress, dict) or progress.get("status") == "capacity_exhausted":
        return None
    raw = progress.get("next_retry_at")
    if not isinstance(raw, str) or len(raw) > 80:
        return None
    try:
        when = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None or when.utcoffset() is None or when > now:
        return None
    return when


def safe_error_code(error):
    """Only emit database errno/known generic class, never SQL or credentials."""
    first = error.args[0] if error.args else None
    if type(first) is int and 0 <= first <= 99999:
        return str(first)
    if isinstance(first, str) and "database is locked" in first.lower():
        return "sqlite_locked"
    return "unspecified"


def _locked_file(root):
    if not root.is_dir() or root.is_symlink():
        raise RuntimeError("STAGE4_DISPATCH_RUNTIME_DIRECTORY_UNSAFE")
    path = root / "stage4-due-dispatch.lock"
    if path.is_symlink():
        raise RuntimeError("STAGE4_DISPATCH_LOCK_SYMLINK")
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    if os.fstat(fd).st_mode & 0o077:
        os.fchmod(fd, 0o600)
    return os.fdopen(fd, "a+b")


def dispatch(*, root, apply, batch=12, scan_limit=500):
    if not 1 <= batch <= 100 or not 1 <= scan_limit <= 5000:
        raise RuntimeError("STAGE4_DISPATCH_LIMIT_INVALID")
    root = Path(root)
    with _locked_file(root) as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            result = {"schema": "saeit.factory.stage4-due-dispatch.v1",
                      "apply": apply, "counts": {"cycle_already_running": 1},
                      "policy_override": False, "budget_override": False,
                      "self_approval": False, "release_modified": False}
            print("STAGE4_DUE_DISPATCH=" + json.dumps(result, sort_keys=True))
            return result
        app = root.parent / "django-app"
        if not (app / "manage.py").is_file() or app.is_symlink():
            raise RuntimeError("STAGE4_DISPATCH_APP_DIRECTORY_UNSAFE")
        sys.path.insert(0, str(app))
        os.chdir(app)
        os.environ.setdefault("SAEIT_ENV", "production")
        os.environ.setdefault("MOJ_FACTORY_LOCAL_MODE", "1")
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
        import django
        django.setup()
        from django.apps import apps
        from django.db import OperationalError, transaction
        from django.utils import timezone
        from core.autonomous_brain import AutonomousBrain

        Product = apps.get_model("core", "Product")
        FactoryRun = apps.get_model("core", "FactoryRun")
        brain = AutonomousBrain()
        counts = Counter()
        scanned = 0
        now = timezone.now()
        # Materialize a bounded snapshot *before* writes. Keeping a streaming
        # MariaDB cursor open while the planner creates tasks on the same
        # connection can cause intermittent OperationalError and lost cycles.
        # Every candidate is still re-read within its own locked transaction.
        prior_cursor = read_cursor(root)
        candidates = candidate_window(Product.objects, prior_cursor, scan_limit)
        last_scanned_pk = prior_cursor
        for product_pk, metadata in candidates:
            if counts["queued"] + counts["approval_gated"] >= batch:
                counts["batch_limit_reached"] += 1
                break
            scanned += 1
            last_scanned_pk = product_pk
            if due_retry(metadata, now) is None:
                continue
            counts["due_seen"] += 1
            try:
                with transaction.atomic():
                    run = (FactoryRun.objects.select_for_update()
                           .filter(product_id=product_pk).order_by("-created_at", "-pk").first())
                    if not run or run.status != "active":
                        counts["no_active_run"] += 1
                        continue
                    product = Product.objects.get(pk=product_pk)
                    due = due_retry(product.metadata, timezone.now())
                    if due is None:
                        counts["changed_or_not_due"] += 1
                        continue
                    tasks = run.tasks
                    if tasks.filter(status__in=("queued", "running", "blocked")).exists():
                        counts["already_in_flight_or_gated"] += 1
                        continue
                    latest = (tasks.filter(action_type="product_validation", status="completed")
                              .order_by("-updated_at", "-pk").first())
                    if latest and latest.updated_at >= due:
                        counts["already_validated_this_window"] += 1
                        continue
                    decision = brain.decide_product_factory_step(product_id=product_pk, run_id=run.run_id)
                    if decision.get("action") != "product_validation":
                        counts["master_decision_" + str(decision.get("action", "unknown"))[:40]] += 1
                        continue
                    if not apply:
                        counts["would_queue_validation"] += 1
                        continue
                    task = brain.plan_product_factory_step(
                        product_id=product_pk, run_id=run.run_id,
                        payload={"goal": "Perform the existing Stage4 evidence validation without changing research limits, quality review or release policy."})
                    if task.status == "queued":
                        counts["queued"] += 1
                    elif task.status == "blocked":
                        counts["approval_gated"] += 1
                    else:
                        counts["planner_returned_" + str(task.status)[:40]] += 1
            except Exception as error:
                counts["planning_error_" + type(error).__name__] += 1
                if isinstance(error, OperationalError):
                    counts["db_error_code_" + safe_error_code(error)] += 1
        if apply and scanned:
            write_cursor(root, last_scanned_pk)
        result = {
            "schema": "saeit.factory.stage4-due-dispatch.v1",
            "apply": apply, "scanned": scanned, "cursor_before": prior_cursor,
            "cursor_after": last_scanned_pk, "counts": dict(sorted(counts.items())),
            "policy_override": False, "budget_override": False,
            "self_approval": False, "release_modified": False,
        }
        print("STAGE4_DUE_DISPATCH=" + json.dumps(result, sort_keys=True))
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--batch", type=int, default=12)
    parser.add_argument("--scan-limit", type=int, default=500)
    args = parser.parse_args()
    dispatch(root=args.root, apply=args.apply, batch=args.batch, scan_limit=args.scan_limit)
