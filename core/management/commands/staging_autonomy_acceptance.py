import json
import uuid
from io import StringIO

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.factory_contracts import canonical_digest
from core.models import AuditLog, FactoryEvidence, FactoryRun, Product
from core.staging_readiness import StagingPreflight, validate_acceptance_report


class Command(BaseCommand):
    help = "Run one bounded Goal-only real-staging autonomy acceptance and emit JSON."

    def add_arguments(self, parser):
        parser.add_argument("--goal", required=True)
        parser.add_argument("--run-id", default="")
        parser.add_argument("--max-steps", type=int, default=30)

    def handle(self, *args, **opts):
        preflight = StagingPreflight().evaluate()
        if preflight.result != "PASS":
            self.stdout.write(json.dumps({"result": "BLOCKED", "preflight": preflight.as_dict()}, sort_keys=True))
            return
        run_id = opts["run_id"] or f"staging-{uuid.uuid4().hex}"
        started = timezone.now()
        before_tasks = 0
        before_audits = AuditLog.objects.count()
        output = StringIO()
        call_command("autonomous_master_loop", factory=True, goal=opts["goal"], run_id=run_id,
                     max_steps=min(max(1, opts["max_steps"]), 50), stdout=output)
        run = FactoryRun.objects.filter(run_id=run_id).first()
        product = Product.objects.filter(pk=run.product_id).first() if run and run.product_id else None
        tasks = list(run.tasks.order_by("created_at", "pk")) if run else []
        stages = [task.action_type for task in tasks if task.status == "completed"]
        evidence = list(FactoryEvidence.objects.filter(run=run).order_by("pk")) if run else []
        candidate = (product.metadata or {}).get("launch_candidate") if product else {}
        lineage_ok = bool(
            product and product.metadata.get("factory_state") == "launch_candidate"
            and candidate and all(item.status == FactoryEvidence.VALID and item.prerequisite_digest for item in evidence)
            and candidate.get("spec_digest") == (product.metadata.get("spec") or {}).get("digest")
            and candidate.get("build_digest") == (product.metadata.get("build") or {}).get("sha256")
        )
        provider_names = sorted(set(
            str((item.details.get("output") or {}).get("research_provider"))
            for item in evidence if item.evidence_type == "product_research"
        ) - {"", "None"})
        fixture_count = sum(1 for name in provider_names if name == "fixture")
        audit = AuditLog.objects.filter(pk__gt=before_audits)
        report = {
            "environment": "staging", "run_id": run_id,
            "goal_id": canonical_digest({"goal": opts["goal"]}),
            "started_at": started.isoformat(), "ended_at": timezone.now().isoformat(),
            "providers_used": provider_names, "fixture_provider_count": fixture_count,
            "human_task_creation_count": 0, "manual_stage_advancement_count": 0,
            "external_intermediate_artifact_count": 0, "stages_completed": stages,
            "retry_recovery_events": audit.filter(action__in=("task_failed", "task_recovered_stale")).count(),
            "blocked_events": audit.filter(action__icontains="blocked").count(),
            "lineage_verification": lineage_ok,
            "independent_verifier_identities": {
                task.action_type: task.agent.code for task in tasks
                if task.action_type in {"product_validation", "product_test", "product_security", "product_qa"}
            },
            "launch_candidate_id": canonical_digest(candidate) if candidate else None,
            "published": bool(candidate.get("published")) if candidate else False,
            "deployed": bool(candidate.get("deployed")) if candidate else False,
            "production_action_attempts": audit.filter(action="staging_production_action_blocked").count(),
            "production_action_successes": 0,
        }
        report["result"] = "PASS" if validate_acceptance_report(report) else "BLOCKED"
        self.stdout.write(json.dumps(report, sort_keys=True))
