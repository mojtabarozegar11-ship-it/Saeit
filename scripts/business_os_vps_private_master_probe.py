"""Authenticate the existing VPS Django master agent without mutating tasks.

Run with the factory's installed private virtualenv. This is observation, not
permission to create capabilities, task approvals or financial actions.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys

from business_os_private_control import _write_private


def inspect_master():
    base = Path.home().resolve() / "factory-runtime"
    app = base / "django-app"
    master = base / "operations" / "master-agent"
    if not (app / "manage.py").is_file() or not master.is_dir():
        raise RuntimeError("factory_master_runtime_unavailable")
    sys.path.insert(0, str(app))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    os.environ.setdefault("MOJ_FACTORY_LOCAL_MODE", "1")
    import django
    django.setup()
    from core.models import Agent, AgentTask

    agents = list(Agent.objects.filter(code="moj_1ro_1", active=True).values_list("pk", flat=True)[:2])
    if len(agents) != 1:
        raise RuntimeError("not_exactly_one_registered_active_master")
    agent_pk = agents[0]
    active = AgentTask.objects.filter(agent_id=agent_pk, status__in=("queued", "running")).count()
    blocked = AgentTask.objects.filter(agent_id=agent_pk, status="blocked").count()
    return {
        "schema": "saeit.business-os.authenticated-master-observation.v1",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "orchestrator": "moj_1ro_1",
        "state": "verified_active_in_private_factory_django",
        "master_agent_id": str(agent_pk),
        "queued_or_running_master_tasks": active,
        "blocked_master_tasks": blocked,
        "master_lock_present": (master / "master-cycle.lock").is_file(),
        "authority": "read_only",
        "business_os_task_capability_confirmed": False,
        "new_tasks": 0,
    }


def main():
    root = Path(__file__).resolve().parent.parent
    expected = Path.home().resolve() / "saeit-business-os-staging" / "releases"
    if expected not in root.resolve().parents:
        raise RuntimeError("not_vps_private_staging")
    report = inspect_master()
    _write_private(root / "private" / "master-observer.json", report)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        raise SystemExit("BUSINESS_OS_MASTER_IDENTITY_UNVERIFIED")
    print("BUSINESS_OS_AUTHENTICATED_MOJ1RO1_READ_ONLY=PASS")
