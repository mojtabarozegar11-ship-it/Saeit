"""Bind the private six-native rework queue to the actual Django master AgentTask runtime.

A real running AgentTask is claimed by TaskRuntime and audited by ToolGateway.
The logical requested label moj_1ro_1 remains DISTINCT from the persisted
agent code economic-master-agent. This command never impersonates an owner,
a professional reviewer, or a physical-device tester.
"""
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.factory_native_review_gateway import (
    ACTION, FAMILIES, digest, latest_snapshot, private_root, snapshot
)
from core.models import Agent, AgentCapability, AgentTask
from core.economic_tool_pack import build_economic_gateway
from core.worker_runner import WorkerRunner

class Command(BaseCommand):
    help="Idempotently create and execute six real evidence-bound native review tasks using the live master agent."

    def add_arguments(self, parser):
        parser.add_argument("--execute", action="store_true",
                            help="Run the six authorized audit tasks through authenticated WorkerRunner.")
        parser.add_argument("--dry-run", action="store_true",
                            help="Read verified receipts but never modify Django tasks or factory state.")

    def handle(self,*args,**options):
        if options["execute"] and options["dry_run"]:
            raise CommandError("BRIDGE_EXECUTE_AND_DRY_RUN_CONFLICT")
        if os.getenv("MOJ_FACTORY_LOCAL_MODE")!="1":
            raise CommandError("BRIDGE_REQUIRES_PRIVATE_VPS_FACTORY_LOCAL_MODE")
        root=private_root(Path.home()/"factory-runtime"/"private"/"autonomous-product-cycle")
        try:
            source_run=latest_snapshot(root)
            snapshot_data=snapshot(root,source_run)
        except (ValueError,KeyError,TypeError,OSError) as err:
            raise CommandError("BRIDGE_PRIVATE_SOURCE_UNVERIFIED:"+str(err)) from err
        review_folder=root/"quality-excellence"/"six-native-rework"/source_run
        whole=digest(review_folder/"review.json")
        evidence=[{
            "family":family,"source_run":source_run,
            "review_sha256":whole,
            "family_receipt_sha256":digest(review_folder/(family+".json")),
            "requested_logical_orchestrator":"moj_1ro_1",
            "verified_task_runtime":"economic-master-agent",
        } for family in FAMILIES]
        if options["dry_run"]:
            self.stdout.write("MOJ1RO1_NATIVE_BRIDGE_DRY_RUN=VERIFIED_6")
            self.stdout.write("MOJ1RO1_NATIVE_BRIDGE_SOURCE_REWORK="+str(
                snapshot_data["source_rework_needed"]))
            return
        with transaction.atomic():
            master=Agent.objects.select_for_update().filter(
                code="economic-master-agent",active=True).first()
            if not master:
                raise CommandError("BRIDGE_VERIFIED_DJANGO_MASTER_INACTIVE")
            capability=master.capabilities.filter(code=ACTION,active=True).first()
            if not capability or capability.risk_level!="low":
                raise CommandError("BRIDGE_REGISTERED_ALLOWLIST_CAPABILITY_MISSING")
            tasks=[]
            created=0
            for payload in evidence:
                present=AgentTask.objects.filter(
                    agent=master,action_type=ACTION,
                    input_data__source_run=source_run,
                    input_data__family=payload["family"]
                ).order_by("pk").first()
                if present:
                    # A new SHA of review evidence cannot silently reuse the old task.
                    if (present.input_data.get("review_sha256")!=payload["review_sha256"]
                        or present.input_data.get("family_receipt_sha256")!=payload["family_receipt_sha256"]):
                        raise CommandError("BRIDGE_TASK_SOURCE_CHANGED_WITHOUT_NEW_VERSION")
                    task=present
                else:
                    task=AgentTask.objects.create(
                        agent=master,action_type=ACTION,capability_code=ACTION,
                        risk_snapshot="low",input_data=payload,status="queued",
                        max_attempts=2)
                    created+=1
                tasks.append(task)
        self.stdout.write("MOJ1RO1_NATIVE_AUTHENTIC_MASTER_DB_CODE="+master.code)
        self.stdout.write("MOJ1RO1_NATIVE_MASTER_DB_PK="+str(master.pk))
        self.stdout.write("MOJ1RO1_NATIVE_AUDIT_TASKS="+str(len(tasks)))
        self.stdout.write("MOJ1RO1_NATIVE_AUDIT_TASKS_NEW="+str(created))
        complete=0
        executor=WorkerRunner(build_economic_gateway()) if options["execute"] else None
        for task in tasks:
            if task.status=="completed":
                output=task.output_data or {}
                if (output.get("verified_effect") is not True
                        or output.get("family")!=task.input_data["family"]
                        or output.get("artifact_sha256")!=next(r["artifact_sha256"]
                            for r in snapshot_data["families"]
                            if r["family_id"]==task.input_data["family"])
                        or output.get("quality_1000_certified") is not False):
                    raise CommandError("BRIDGE_COMPLETED_TASK_EVIDENCE_INVALID")
                complete+=1
            elif options["execute"] and task.status=="queued":
                finished=executor.run(task.pk)
                output=finished.output_data or {}
                if (finished.status!="completed" or output.get("verified_effect") is not True
                        or output.get("quality_1000_certified") is not False
                        or output.get("commercial_release") is not False
                        or output.get("family")!=task.input_data["family"]):
                    raise CommandError("BRIDGE_WORKER_TASK_DID_NOT_VERIFY")
                complete+=1
            elif task.status=="failed":
                raise CommandError("BRIDGE_TASK_REQUIRES_REWORK:"+str(task.pk))
            elif task.status not in ("queued","running","blocked"):
                raise CommandError("BRIDGE_UNEXPECTED_TASK_STATUS")
        self.stdout.write("MOJ1RO1_NATIVE_AUTHENTIC_AGENT_TASKS_COMPLETED="+str(complete))
        self.stdout.write("MOJ1RO1_NATIVE_PENDING_REAL_WORLD_SPECIALIST_GATES="+str(
            snapshot_data["specialist_or_physical_review_needed"]))
        self.stdout.write("MOJ1RO1_NATIVE_PROFESSIONAL_QUALITY_1000=NOT_CERTIFIED")
        self.stdout.write("MOJ1RO1_NATIVE_PUBLIC_WEBSITE_WRITES=0")
        if options["execute"] and complete!=6:
            raise CommandError("BRIDGE_NOT_ALL_SIX_TASKS_COMPLETE")
