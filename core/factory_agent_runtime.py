
"""Agent execution adapters for the existing Product Factory task and tool runtime."""
import hashlib
import json
from decimal import Decimal
from importlib import import_module

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

from .factory_artifact_verifier import StaticResearchBriefVerifier
from .factory_builder import StaticResearchBriefBuilder
from .models import FactoryArtifact, FactoryMarketEligibility, Product, ResearchProject
from .factory_governance import validate_task_prerequisites
from .research_runtime import ResearchRuntime
from .factory_contracts import FactoryAgentOutput, GatewayAuthorization


class FactoryAgentBlocked(RuntimeError):
    retryable = False


class ResearchProvider:
    """Provider contract: return retrieved, source-addressable findings; no fake fallback."""

    provider_name = "unconfigured"
    real_research = False

    def search(self, *, goal, constraints, task, authorization, authorization_check):
        raise NotImplementedError


class FixtureResearchProvider(ResearchProvider):
    """Deterministic CI adapter. Its records are explicitly marked as non-real research."""

    provider_name = "fixture"
    real_research = False

    def search(self, *, goal, constraints, task, authorization, authorization_check):
        if not authorization_check(authorization, task, "product_research"):
            raise FactoryAgentBlocked("Research Provider call requires current ToolGateway authorization.")
        if not str(goal or "").strip():
            raise ValueError("Research goal is required.")
        now = timezone.now().isoformat()
        return [
            {
                "title": "Fixture evidence: workflow demand",
                "url": "fixture://research/workflow-demand",
                "publisher": "CI fixture",
                "passage": f"Fixture-only observation for goal: {goal}",
                "confidence": "0.80",
                "retrieved_at": now,
                "provenance": {"provider": "fixture", "real_research": False, "fixture_id": "workflow-demand-v1"},
            },
            {
                "title": "Fixture evidence: product constraints",
                "url": "fixture://research/product-constraints",
                "publisher": "CI fixture",
                "passage": "Fixture-only constraint: prefer a small static deliverable with no external side effects.",
                "confidence": "0.75",
                "retrieved_at": now,
                "provenance": {"provider": "fixture", "real_research": False, "fixture_id": "product-constraints-v1"},
            },
        ]


def configured_research_provider():
    path = str(getattr(settings, "FACTORY_RESEARCH_PROVIDER", "") or "").strip()
    if not path:
        raise FactoryAgentBlocked("No real Factory research provider is configured.")
    module, name = path.rsplit(".", 1)
    provider = getattr(import_module(module), name)()
    if not isinstance(provider, ResearchProvider):
        if not callable(getattr(provider, "search", None)):
            raise FactoryAgentBlocked("Configured research provider does not implement search().")
    return provider


class FactoryAgentRuntime:
    """Derive each specialist output from the goal and persisted, verified prerequisites."""

    def __init__(self, *, research_provider=None, builder=None, verifier=None):
        self.research_provider = research_provider
        self.builder = builder or StaticResearchBriefBuilder()
        self.verifier = verifier or StaticResearchBriefVerifier()
        self.research = ResearchRuntime()

    def execute(self, task, *, authorization=None, authorization_check=None):
        if (
            not isinstance(authorization, GatewayAuthorization)
            or not callable(authorization_check)
            or not authorization_check(authorization, task, task.action_type)
        ):
            raise FactoryAgentBlocked("Factory adapter execution requires a current ToolGateway authorization.")
        action = task.action_type
        if action != "product_research":
            validate_task_prerequisites(task)
        if action == "product_research":
            values = self._research(task, authorization, authorization_check)
        else:
            product = task.product
            if not product:
                raise FactoryAgentBlocked("Factory task has no persisted Product prerequisite.")
            if action == "product_opportunity_score":
                values = self._score(task, product)
            elif action == "product_spec":
                values = self._spec(task, product)
            elif action == "product_build_record":
                values = self._build(task, product, authorization, authorization_check)
            elif action == "product_qa":
                values = self._verify(task, product, authorization, authorization_check)
            elif action == "product_localize":
                values = {"locales": ["en"]}
            elif action == "product_launch_candidate":
                now = timezone.now()
                markets = FactoryMarketEligibility.objects.filter(
                    eligibility=FactoryMarketEligibility.ALLOWED,
                    reviewed_by__is_superuser=True,
                    valid_until__gt=now,
                ).order_by("market_code")
                values = {"markets": [{"market_code": item.market_code} for item in markets]}
            else:
                raise FactoryAgentBlocked(f"No execution adapter is registered for {action}.")
        return FactoryAgentOutput.validate(action, values)

    @staticmethod
    def _owner(task):
        if task.project_id:
            return task.project.owner
        return get_user_model().objects.filter(is_superuser=True, is_active=True).order_by("pk").first()

    @transaction.atomic
    def _research(self, task, authorization, authorization_check):
        if task.factory_run_id:
            existing = ResearchProject.objects.filter(factory_run_id=task.factory_run_id).first()
            if existing:
                report = existing.reports.order_by("-version", "-pk").first()
                if not report:
                    raise FactoryAgentBlocked("Run-bound ResearchProject is incomplete; owner remediation is required.")
                records = []
                for item in existing.evidence.select_related("source").order_by("pk"):
                    source = item.source
                    records.append({
                        "source": source.provenance.get("source_url") or source.url,
                        "title": source.title, "passage": item.passage, "evidence_id": item.pk,
                        "confidence": str(item.confidence), "snapshot_hash": source.snapshot_hash,
                        "retrieved_at": source.retrieved_at.isoformat(), "provenance": source.provenance,
                    })
                if len(records) < 2:
                    raise FactoryAgentBlocked("Run-bound ResearchProject has insufficient evidence.")
                return {
                    "title": task.goal[:300],
                    "sources": [{"url": item["source"], "finding": item["passage"]} for item in records],
                    "research_project_id": existing.pk, "research_report_id": report.pk,
                    "research_provider": report.content.get("provider", "unknown"),
                    "real_research": report.content.get("real_research") is True, "evidence": records,
                }
        provider = self.research_provider or configured_research_provider()
        goal = str(task.goal or (task.input_data or {}).get("goal") or "").strip()
        if not goal:
            raise ValueError("Factory Research requires a goal.")
        constraints = (task.input_data or {}).get("constraints", [])
        if not authorization_check(authorization, task, "product_research"):
            raise FactoryAgentBlocked("Research Provider call requires current ToolGateway authorization.")
        records = provider.search(
            goal=goal, constraints=constraints, task=task,
            authorization=authorization, authorization_check=authorization_check,
        )
        if not isinstance(records, list) or len(records) < 2:
            raise ValueError("Research provider must return at least two source-backed findings.")
        if not authorization_check(authorization, task, "product_research"):
            raise FactoryAgentBlocked("Research grant was revoked before evidence could be persisted.")
        owner = self._owner(task)
        if not owner:
            raise FactoryAgentBlocked("Research requires an existing owner for ResearchProject provenance.")
        project = ResearchProject.objects.create(
            title=f"Factory research: {goal[:240]}",
            objective=goal,
            status="evidence_collected",
            owner=owner,
            factory_run=task.factory_run if task.factory_run_id else None,
        )
        persisted = []
        for record in records:
            if not isinstance(record, dict) or not record.get("url") or not record.get("passage"):
                raise ValueError("Provider evidence requires source URL and passage.")
            passage = str(record["passage"]).strip()
            if not passage:
                raise ValueError("Provider returned an empty passage.")
            source_url = str(record["url"]).strip()
            raw = json.dumps(
                {"url": source_url, "passage": passage, "provenance": record.get("provenance", {})},
                sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            ).encode("utf-8")
            snapshot_hash = hashlib.sha256(raw).hexdigest()
            source = self.research.register_source(
                project=project,
                title=str(record.get("title") or source_url)[:500],
                url=source_url if source_url.startswith(("https://", "http://")) else "",
                publisher=str(record.get("publisher") or provider.provider_name)[:300],
                content_hash=snapshot_hash,
                snapshot_hash=snapshot_hash,
                retrieved_at=record.get("retrieved_at") or timezone.now(),
                provenance={
                    **(record.get("provenance") if isinstance(record.get("provenance"), dict) else {}),
                    "provider": provider.provider_name,
                    "real_research": getattr(provider, "real_research", False) is True,
                    "source_url": source_url,
                },
            )
            evidence = self.research.add_evidence(
                project, source, passage, confidence=record.get("confidence", "0.5")
            )
            finding = self.research.add_finding(
                project, title=source.title, statement=passage,
                evidence=[evidence], confidence=record.get("confidence", "0.5"),
            )
            persisted.append({
                "source": source.url or source_url,
                "title": source.title,
                "passage": evidence.passage,
                "evidence_id": evidence.pk,
                "finding_id": finding.pk,
                "confidence": str(evidence.confidence),
                "snapshot_hash": source.snapshot_hash,
                "retrieved_at": source.retrieved_at.isoformat(),
                "provenance": source.provenance,
            })
        report = self.research.create_report(
            project, f"Factory evidence report: {goal[:240]}",
            {"goal": goal, "run_id": task.factory_run.run_id if task.factory_run_id else None, "provider": provider.provider_name, "real_research": getattr(provider, "real_research", False) is True, "evidence": persisted},
        )
        return {
            "title": goal[:300], "sources": [
                {"url": item["source"], "finding": item["passage"]} for item in persisted
            ],
            "research_project_id": project.pk, "research_report_id": report.pk,
            "research_provider": provider.provider_name,
            "real_research": getattr(provider, "real_research", False) is True,
            "evidence": persisted,
        }

    @staticmethod
    def _research_records(product):
        research = (product.metadata or {}).get("research") or {}
        records = research.get("evidence") or []
        if not records:
            raise FactoryAgentBlocked("Current Run has no persisted ResearchRuntime evidence.")
        return records

    def _score(self, task, product):
        records = self._research_records(product)
        confidence = sum(Decimal(item["confidence"]) for item in records) / Decimal(len(records))
        score = (confidence * Decimal("100")).quantize(Decimal("0.01"))
        rubric = {"id": "evidence-confidence-v1", "formula": "100 * mean(validated evidence confidence)", "evidence_ids": [item["evidence_id"] for item in records]}
        return {"score": float(score), "rationale": f"Mean evidence confidence across {len(records)} persisted findings.", "rubric": rubric}

    def _spec(self, task, product):
        records = self._research_records(product)
        problem = str((task.factory_run.goal if task.factory_run_id else task.goal) or "").strip()
        if not problem:
            raise ValueError("A research-backed Product goal is required for specification.")
        spec = {
            "version": int(task.factory_run.current_spec_version + 1 if task.factory_run_id else 1),
            "product_type": "static_research_brief",
            "problem": problem,
            "title": product.title,
            "evidence_ids": [item["evidence_id"] for item in records],
            "acceptance_criteria": [
                "The artifact is valid UTF-8 HTML.",
                "The artifact contains the specified problem statement.",
                f"The artifact contains source-linked findings from all {len(records)} persisted evidence records.",
                "The artifact digest matches the immutable FactoryArtifact record.",
            ],
        }
        spec["digest"] = hashlib.sha256(
            json.dumps(spec, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return {"spec": spec}

    def _build(self, task, product, authorization, authorization_check):
        spec = (product.metadata or {}).get("spec") or {}
        if not spec.get("digest"):
            raise FactoryAgentBlocked("Builder requires a versioned and digested persisted Product spec.")
        records = self._research_records(product)
        run = task.factory_run
        version = run.current_artifact_version + 1
        artifact = self.builder.build(
            run_id=run.run_id, product_id=product.pk, version=version, spec=spec, evidence=records,
            task=task, authorization=authorization, authorization_check=authorization_check,
        )
        return {"artifact": artifact}

    def _verify(self, task, product, authorization, authorization_check):
        run = task.factory_run
        artifact = FactoryArtifact.objects.filter(
            product=product, run=run, version=run.current_artifact_version,
        ).order_by("-pk").first()
        if not artifact:
            raise FactoryAgentBlocked("Test/Security requires the current persisted artifact.")
        spec = (product.metadata or {}).get("spec") or {}
        tests, security = self.verifier.verify(
            artifact, spec, task=task, authorization=authorization,
            authorization_check=authorization_check,
        )
        return {"tests": tests, "security": security}
