import json
import uuid
from io import StringIO

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.factory_contracts import canonical_digest
from core.models import AuditLog, FactoryEvidence, FactoryRun, Product
from django.db.models import Max
from pathlib import Path
import hashlib
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
            raise CommandError("Staging acceptance preflight BLOCKED")
        run_id = opts["run_id"] or f"staging-{uuid.uuid4().hex}"
        started = timezone.now()
        
        before_audits = AuditLog.objects.aggregate(last=Max("pk"))["last"] or 0
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
        task_ids = [str(task.pk) for task in tasks]
        audit = AuditLog.objects.filter(target_type="AgentTask", target_id__in=task_ids)
        planned = set(audit.filter(action="factory_next_step_planned", actor_type="agent",
                                  actor_id="factory-master-agent").values_list("target_id", flat=True))
        unplanned = sum(str(task.pk) not in planned for task in tasks)
        unverified = sum(task.status == "completed" and (
            not task.execution_id or not task.output_data.get("verified_effect") or
            not task.factory_evidence.filter(status="valid").exists()) for task in tasks)
        external = sum(bool(task.bridge_nonce or task.bridge_idempotency_key) or
                       bool(set(task.input_data) - {"goal", "run_id", "constraints", "product_id"}) for task in tasks)
        sources = list(run.research_project.sources.all()) if run and hasattr(run, "research_project") else []
        real_sources = bool(sources) and all(
            item.provenance.get("real_research") is True and
            item.provenance.get("provider") == "self-hosted-staging" and
            item.provenance.get("provider_request_id") and
            hashlib.sha256(str(item.provenance.get("snapshot_text", "")).encode()).hexdigest() == item.snapshot_hash
            for item in sources)
        for artifact in run.artifacts.all() if run else []:
            try:
                lineage_ok = lineage_ok and hashlib.sha256(Path(artifact.reference).read_bytes()).hexdigest() == artifact.content_digest
            except OSError:
                lineage_ok = False
        report = {
            "environment": "staging", "run_id": run_id,
            "goal_id": canonical_digest({"goal": opts["goal"]}),
            "started_at": started.isoformat(), "ended_at": timezone.now().isoformat(),
            "providers_used": provider_names, "fixture_provider_count": fixture_count,
            "human_task_creation_count": unplanned, "manual_stage_advancement_count": unverified,
            "external_intermediate_artifact_count": external, "real_source_provenance": real_sources,
            "builder_identity": next((task.agent.code for task in tasks if task.action_type == "product_build_record"), None), "stages_completed": stages,
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
            "production_action_successes": sum(task.action_type not in {
                "product_research", "product_opportunity_score", "product_validation", "product_spec",
                "product_build_record", "product_test", "product_security", "product_localize",
                "product_market_eligibility", "product_qa", "product_launch_candidate"
            } and task.status == "completed" for task in tasks),
            "scope": "single-run candidate verification; not full Gate 97",
            "gate97_result": "PENDING_OPERATIONAL_DRILLS",
            "operational_drills_required": ["unattended_scheduler", "process_restart_resume", "stale_recovery",
                                            "transient_retry", "bounded_reresearch", "idempotent_replay"],
        }
        report["result"] = "PASS" if validate_acceptance_report(report) else "BLOCKED"
        self.stdout.write(json.dumps(report, sort_keys=True))

        if report["result"] != "PASS":
            raise CommandError("Candidate acceptance BLOCKED; preserve report and inspect run audit")
