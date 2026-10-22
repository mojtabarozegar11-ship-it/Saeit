"""Idempotent, authenticated F41 private production work-order bridge."""
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.factory_f41_gateway import ACTION, ORDER, inspect_order, roots, build_verified_order
from core.models import Agent, AgentTask
from core.economic_tool_pack import build_economic_gateway
from core.worker_runner import WorkerRunner

PERMITTED = {"factory_native_review", ACTION}


class Command(BaseCommand):
    help = "Build bounded private F41 orders through genuine moj_1ro_1 AgentTasks."

    def add_arguments(self, parser):
        parser.add_argument("--execute", action="store_true")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        if opts["execute"] and opts["dry_run"]:
            raise CommandError("F41_MASTER_CONFLICTING_MODES")
        if os.getenv("MOJ_FACTORY_LOCAL_MODE") != "1":
            raise CommandError("F41_MASTER_VPS_LOCAL_MODE_REQUIRED")
        root, ops = roots()
        order_dir = root / "orders"
        if order_dir.is_symlink() or not order_dir.is_dir():
            raise CommandError("F41_MASTER_ORDER_QUEUE_UNAVAILABLE")
        files = sorted(order_dir.iterdir())
        if len(files) > 64:
            raise CommandError("F41_MASTER_ORDER_QUEUE_CAP_EXCEEDED")
        payloads = []
        seen = set()
        try:
            for file in files:
                if (not file.is_file() or file.is_symlink() or file.suffix != ".json"
                        or not ORDER.fullmatch(file.stem)):
                    raise ValueError("F41_MASTER_UNEXPECTED_QUEUE_ENTRY")
                item = inspect_order(root, ops, file.stem)
                if item["product_id"] in seen:
                    raise ValueError("F41_MASTER_DUPLICATE_PRODUCT_ID")
                seen.add(item["product_id"])
                payloads.append(item)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            raise CommandError("F41_MASTER_PREFLIGHT_FAILED:" + str(exc)) from exc
        self.stdout.write("F41_MASTER_VALIDATED_ORDERS=" + str(len(payloads)))
        if opts["dry_run"]:
            self.stdout.write("F41_MASTER_DRY_RUN=PASS")
            return
        with transaction.atomic():
            agent = Agent.objects.select_for_update().filter(code="moj_1ro_1", active=True).first()
            if agent is None:
                raise CommandError("F41_MASTER_AGENT_NOT_ACTIVE")
            if set(agent.capabilities.filter(active=True).values_list("code", flat=True)) != PERMITTED:
                raise CommandError("F41_MASTER_AGENT_CAPABILITY_MISMATCH")
            cap = agent.capabilities.filter(code=ACTION, active=True, risk_level="low").first()
            if cap is None:
                raise CommandError("F41_MASTER_EXECUTOR_NOT_AUTHORIZED")
            tasks = []
            created = 0
            for item in payloads:
                existing = AgentTask.objects.filter(agent=agent, action_type=ACTION,
                    input_data__order_id=item["order_id"]).order_by("pk").first()
                if existing:
                    if existing.input_data != item:
                        raise CommandError("F41_MASTER_CHANGED_ORDER_REQUIRES_NEW_ID")
                    task = existing
                else:
                    task = AgentTask.objects.create(agent=agent, action_type=ACTION,
                        capability_code=ACTION, risk_snapshot="low", input_data=item,
                        status="queued", max_attempts=2)
                    created += 1
                tasks.append(task)
        self.stdout.write("F41_MASTER_AGENT_ID=" + agent.code)
        self.stdout.write("F41_MASTER_TASKS_NEW=" + str(created))
        worker = WorkerRunner(build_economic_gateway()) if opts["execute"] else None
        verified = 0
        for task in tasks:
            if task.status == "completed":
                result = build_verified_order(task.input_data)
                if (task.output_data.get("product_manifest_sha256") != result["product_manifest_sha256"]
                        or task.output_data.get("verified_effect") is not True):
                    raise CommandError("F41_MASTER_COMPLETED_TASK_EVIDENCE_MISMATCH")
                verified += 1
            elif opts["execute"] and task.status == "queued":
                finished = worker.run(task.pk)
                if (finished.status != "completed"
                        or finished.output_data.get("verified_effect") is not True
                        or finished.output_data.get("commercial_release") is not False):
                    raise CommandError("F41_MASTER_EXECUTION_NOT_VERIFIED")
                verified += 1
            elif task.status in ("failed", "cancelled"):
                raise CommandError("F41_MASTER_FAILED_ORDER_REQUIRES_REWORK")
            elif task.status not in ("queued", "running", "blocked"):
                raise CommandError("F41_MASTER_UNKNOWN_TASK_STATE")
        self.stdout.write("F41_MASTER_AUTHENTIC_TASKS_VERIFIED=" + str(verified))
        self.stdout.write("F41_MASTER_SALES_CERTIFIED=0")
        self.stdout.write("F41_MASTER_MAINNET_TRANSACTIONS=0")
        if opts["execute"] and verified != len(tasks):
            raise CommandError("F41_MASTER_INCOMPLETE_EXECUTION")
