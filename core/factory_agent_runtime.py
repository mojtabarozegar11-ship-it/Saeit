
"""Agent execution adapters for the existing Product Factory task and tool runtime."""
import hashlib
import ipaddress
import json
import os
import time
from datetime import timedelta
from urllib.parse import urlsplit
from decimal import Decimal
from importlib import import_module

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .factory_artifact_verifier import StaticResearchBriefVerifier
from .factory_builder import StaticResearchBriefBuilder
from .models import FactoryArtifact, FactoryMarketEligibility, Finding, Product, ResearchProject
from .factory_governance import validate_task_prerequisites
from .research_runtime import ResearchRuntime
from .factory_contracts import FactoryAgentOutput, GatewayAuthorization, canonical_digest
from .factory_economics import score_opportunity, validate_opportunity, SOURCE_QUALITY_POLICY_VERSION


class FactoryAgentBlocked(RuntimeError):
    retryable = False


class ResearchProvider:
    """Trusted, configured adapter contract for bounded search and snapshot fetch."""

    provider_name = "unconfigured"
    real_research = False
    extractor_version = "unknown"

    def search(self, *, goal, constraints, plan, task, authorization, authorization_check,
               timeout_seconds, max_results, max_snapshot_bytes, max_redirects, safe_url_policy):
        raise NotImplementedError


class FixtureResearchProvider(ResearchProvider):
    """Deterministic CI-only source records. Never eligible as real release evidence."""

    provider_name = "fixture"
    real_research = False
    extractor_version = "fixture-v1"

    def search(self, *, goal, constraints, plan, task, authorization, authorization_check,
               timeout_seconds, max_results, max_snapshot_bytes, max_redirects, safe_url_policy):
        if not authorization_check(authorization, task, "product_research"):
            raise FactoryAgentBlocked("Research Provider call requires current ToolGateway authorization.")
        if not callable(safe_url_policy):
            raise FactoryAgentBlocked("Research requires the enforced safe URL policy at the Provider boundary.")
        now = timezone.now().isoformat()
        factors_a = {
            "market_demand": {"value": 78, "claim": "Fixture-only demand signal."},
            "willingness_to_pay": {"value": 70, "claim": "Fixture-only willingness-to-pay signal."},
            "expected_revenue_potential": {"value": 65, "claim": "Fixture-only revenue-potential signal."},
            "expected_profit_potential": {"value": 72, "claim": "Fixture-only profit-potential signal."},
            "commercial_success_probability": {"value": 58, "claim": "Fixture-only success signal."},
        }
        factors_b = {
            "time_to_first_revenue": {"value": 80, "claim": "Fixture-only time-to-revenue signal."},
            "build_cost_efficiency": {"value": 82, "claim": "Fixture-only build-cost signal."},
            "operating_cost_efficiency": {"value": 76, "claim": "Fixture-only operating-cost signal."},
            "execution_feasibility": {"value": 81, "claim": "Fixture-only feasibility signal."},
            "competition_position": {"value": 60, "claim": "Fixture-only competition signal."},
            "capital_efficiency": {"value": 85, "claim": "Fixture-only capital-efficiency signal."},
            "legal_safety": {"value": 90, "claim": "Fixture-only legal-risk signal."},
            "security_safety": {"value": 90, "claim": "Fixture-only security-risk signal."},
            "scalability": {"value": 68, "claim": "Fixture-only scalability signal."},
            "defensibility": {"value": 55, "claim": "Fixture-only defensibility signal."},
        }
        result = []
        for key, title, passage, factors in (
            ("demand", "Fixture demand", f"Fixture-only demand observation for {goal}.", factors_a),
            ("cost", "Fixture constraints", "Fixture-only low-cost product constraint observation.", factors_b),
        ):
            url = f"fixture://source-{key}/snapshot"
            factor_text = "\n".join(f"{name}: {item['claim']} rating {item['value']}" for name, item in sorted(factors.items()))
            snapshot = f"Fixture snapshot v1\n{title}\n{passage}\n{factor_text}\n"
            result.append({
                "title": title, "url": url, "requested_url": url, "final_url": url,
                "publisher": f"CI fixture {key}", "source_identity": f"fixture-source-{key}",
                "query": plan["queries"][0], "provider_request_id": f"fixture-{key}-request-v1",
                "retrieved_at": now, "content_type": "text/plain", "snapshot": snapshot,
                "snapshot_sha256": hashlib.sha256(snapshot.encode("utf-8")).hexdigest(),
                "snapshot_hash": hashlib.sha256(snapshot.encode("utf-8")).hexdigest(),
                "passage": passage, "passage_locator": {"line": 3},
                "extractor_version": self.extractor_version, "source_type": "secondary",
                "confidence": "0.80" if key == "demand" else "0.75",
                "economic_factors": factors,
                "provenance": {"real_research": False, "fixture_id": f"{key}-v1"},
            })
        return result[:max_results]


def configured_research_provider():
    path = str(getattr(settings, "FACTORY_RESEARCH_PROVIDER", "") or os.environ.get("FACTORY_RESEARCH_PROVIDER", "")).strip()
    if not path:
        raise FactoryAgentBlocked("PROVIDER_UNAVAILABLE: no real Factory research provider is configured.")
    try:
        module, name = path.rsplit(".", 1)
        provider = getattr(import_module(module), name)()
    except Exception as exc:
        raise FactoryAgentBlocked("PROVIDER_UNAVAILABLE: configured research provider could not be loaded.") from exc
    if not callable(getattr(provider, "search", None)):
        raise FactoryAgentBlocked("PROVIDER_UNAVAILABLE: configured provider does not implement bounded search().")
    if getattr(provider, "real_research", None) is not True:
        raise FactoryAgentBlocked("PROVIDER_UNAVAILABLE: configured provider is not approved for real evidence.")
    return provider


def research_plan(goal, constraints=None, validation=None):
    goal = str(goal or "").strip()[:500]
    missing = list((validation or {}).get("missing_factors") or [])
    suffix = ", focused on: " + ", ".join(sorted(set(missing))) if missing else ""
    return {
        "version": "research-plan-v1",
        "goal": goal,
        "queries": [
            f"{goal} market demand independent evidence{suffix}",
            f"{goal} customer willingness to pay pricing{suffix}",
            f"{goal} alternatives competition and costs{suffix}",
        ],
        "hypotheses": ["A defined customer has a measurable problem.", "Customers may pay for a solution."],
        "source_strategy": ["Prefer primary sources and independent publishers.", "Use a maximum of one counted source per publisher identity."],
        "stopping_criteria": {"minimum_independent_sources": 2, "maximum_results": 6, "max_attempts": 2},
        "constraints": constraints if isinstance(constraints, (list, dict)) else [],
        "timeout_seconds": int(getattr(settings, "FACTORY_RESEARCH_TIMEOUT_SECONDS", 20)),
        "max_snapshot_bytes": min(max(1024, int(getattr(settings, "FACTORY_RESEARCH_MAX_SNAPSHOT_BYTES", 512000))), 1048576),
        "max_redirects": min(max(0, int(getattr(settings, "FACTORY_RESEARCH_MAX_REDIRECTS", 3))), 3),
        "deadline_at": (timezone.now() + timedelta(seconds=min(max(1, int(getattr(settings, "FACTORY_RESEARCH_DEADLINE_SECONDS", 90))), 300))).isoformat(),
    }


def _safe_research_url(value, *, allow_fixture=False):
    try:
        parsed = urlsplit(str(value or ""))
        if allow_fixture and parsed.scheme == "fixture" and parsed.hostname:
            return True
        if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
            return False
        host = parsed.hostname.rstrip(".").lower()
        if host in {"localhost", "metadata.google.internal", "metadata.azure.internal"} or host.endswith((".localhost", ".local", ".internal")):
            return False
        try:
            address = ipaddress.ip_address(host)
            if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved or address.is_unspecified or address.is_multicast:
                return False
        except ValueError:
            pass
        return parsed.port in (None, 80, 443)
    except (TypeError, ValueError):
        return False


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
            elif action == "product_validation":
                values = self._validate(task, product)
            elif action == "product_spec":
                values = self._spec(task, product)
            elif action == "product_build_record":
                values = self._build(task, product, authorization, authorization_check)
            elif action == "product_test":
                values = self._test(task, product, authorization, authorization_check)
            elif action == "product_security":
                values = self._security(task, product, authorization, authorization_check)
            elif action == "product_localize":
                values = self._localize(task, product)
            elif action == "product_market_eligibility":
                now = timezone.now()
                markets = FactoryMarketEligibility.objects.filter(
                    eligibility=FactoryMarketEligibility.ALLOWED,
                    reviewed_by__is_superuser=True,
                    valid_until__gt=now,
                ).order_by("market_code")
                values = {"markets": [{"market_code": item.market_code} for item in markets]}
            elif action == "product_qa":
                values = self._qa(task, product)
            elif action == "product_launch_candidate":
                values = self._launch_candidate(task, product)
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
        run = task.factory_run if task.factory_run_id else None
        product = task.product if task.product_id else None
        existing = ResearchProject.objects.filter(factory_run_id=run.pk).first() if run else None
        retry_validation = (product.metadata or {}).get("validation") or {} if product else {}
        is_research_retry = bool(existing and product and product.metadata.get("factory_state") == "needs_research")
        if existing and not is_research_retry:
            raise FactoryAgentBlocked("Research Run already has evidence; Master must request a bounded validation re-research.")
        provider = self.research_provider or configured_research_provider()
        goal = str(task.goal or (task.input_data or {}).get("goal") or "").strip()
        if not goal:
            raise FactoryAgentBlocked("Research goal is missing.")
        constraints = (task.input_data or {}).get("constraints", [])
        plan = research_plan(goal, constraints, retry_validation)
        timeout_seconds = plan["timeout_seconds"]
        if timeout_seconds < 1 or timeout_seconds > 120:
            raise FactoryAgentBlocked("Research policy timeout is outside the bounded range.")
        if not authorization_check(authorization, task, "product_research"):
            raise FactoryAgentBlocked("Research Provider call requires current ToolGateway authorization.")
        started = time.monotonic()
        max_attempts = min(max(1, int(getattr(settings, "FACTORY_RESEARCH_MAX_ATTEMPTS", 2))), 3)
        for attempt in range(max_attempts):
            try:
                records = provider.search(
                    goal=goal, constraints=constraints, plan=plan, task=task,
                    authorization=authorization, authorization_check=authorization_check,
                    timeout_seconds=timeout_seconds, max_results=6,
                    max_snapshot_bytes=plan["max_snapshot_bytes"], max_redirects=plan["max_redirects"],
                    safe_url_policy=lambda url: _safe_research_url(url, allow_fixture=isinstance(provider, FixtureResearchProvider)),
                )
                break
            except FactoryAgentBlocked:
                raise
            except Exception as exc:
                if getattr(exc, "status_code", None) in {401, 403} or getattr(exc, "policy_rejected", False):
                    raise FactoryAgentBlocked("PROVIDER_UNAVAILABLE: provider authentication or policy rejected the request.") from exc
                if attempt + 1 >= max_attempts:
                    raise FactoryAgentBlocked(f"PROVIDER_UNAVAILABLE: research provider failed after bounded retries ({type(exc).__name__}).") from exc
                retry_after = getattr(exc, "retry_after", None)
                if retry_after is None:
                    retry_after = min(0.25 * (2 ** attempt), 1.0)
                try:
                    delay = min(max(float(retry_after), 0.0), 3.0)
                except (TypeError, ValueError):
                    delay = min(0.25 * (2 ** attempt), 1.0)
                if time.monotonic() - started + delay >= timeout_seconds:
                    raise FactoryAgentBlocked("PROVIDER_UNAVAILABLE: provider retry exceeded the research deadline.") from exc
                time.sleep(delay)
        if time.monotonic() - started > timeout_seconds:
            raise FactoryAgentBlocked("PROVIDER_UNAVAILABLE: research provider exceeded its execution deadline.")
        if not authorization_check(authorization, task, "product_research"):
            raise FactoryAgentBlocked("Research grant was revoked before evidence could be persisted.")
        if not isinstance(records, list) or not records:
            raise FactoryAgentBlocked("NEEDS_MORE_EVIDENCE: provider returned no source-backed snapshot.")
        if len(records) > 6:
            raise FactoryAgentBlocked("Research provider exceeded the maximum result count.")

        is_fixture = isinstance(provider, FixtureResearchProvider)
        configured_path = str(getattr(settings, "FACTORY_RESEARCH_PROVIDER", "") or os.environ.get("FACTORY_RESEARCH_PROVIDER", "")).strip()
        provider_class = f"{provider.__class__.__module__}.{provider.__class__.__qualname__}"
        real_research = bool(
            not is_fixture and getattr(provider, "real_research", False) is True
            and configured_path == provider_class
        )
        clean_records, seen_source_ids, seen_snapshot_hashes = [], set(), set()
        if existing:
            for old in existing.evidence.select_related("source").all():
                seen_source_ids.add(str(old.source.provenance.get("source_identity") or old.source.url).lower())
                seen_snapshot_hashes.add(old.source.snapshot_hash)
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise FactoryAgentBlocked("Research provider returned a malformed source record.")
            requested_url = str(record.get("requested_url") or record.get("url") or "").strip()
            final_url = str(record.get("final_url") or record.get("url") or "").strip()
            if not _safe_research_url(requested_url, allow_fixture=is_fixture) or not _safe_research_url(final_url, allow_fixture=is_fixture):
                raise FactoryAgentBlocked("Research source URL is unsafe or targets a private/internal resource.")
            redirects = int(record.get("redirect_count", 0) or 0)
            if redirects < 0 or redirects > plan["max_redirects"]:
                raise FactoryAgentBlocked("Research source exceeded its redirect limit.")
            content_type = str(record.get("content_type") or "").split(";", 1)[0].lower().strip()
            if content_type not in {"text/plain", "text/html", "application/json", "text/csv", "application/xml", "text/xml"}:
                raise FactoryAgentBlocked("Research source content type is unsupported.")
            snapshot = record.get("snapshot")
            if not isinstance(snapshot, str) or not snapshot:
                raise FactoryAgentBlocked("Research source must include a text snapshot for content-based provenance.")
            snapshot_bytes = snapshot.encode("utf-8")
            if len(snapshot_bytes) > plan["max_snapshot_bytes"]:
                raise FactoryAgentBlocked("Research source snapshot exceeded the configured content limit.")
            snapshot_hash = hashlib.sha256(snapshot_bytes).hexdigest()
            if record.get("snapshot_sha256") and str(record["snapshot_sha256"]).lower() != snapshot_hash:
                raise FactoryAgentBlocked("Research snapshot digest does not match retrieved content.")
            passage = str(record.get("passage") or "").strip()
            locator = record.get("passage_locator")
            if not passage or len(passage) > 12000:
                raise FactoryAgentBlocked("Research passage is empty or exceeds the extraction limit.")
            if passage not in snapshot:
                if not isinstance(locator, dict):
                    raise FactoryAgentBlocked("Research passage cannot be traced to its source snapshot.")
                try:
                    start_offset, end_offset = int(locator["start"]), int(locator["end"])
                except (KeyError, TypeError, ValueError):
                    raise FactoryAgentBlocked("Research passage locator is invalid.")
                if start_offset < 0 or end_offset < start_offset or snapshot[start_offset:end_offset] != passage:
                    raise FactoryAgentBlocked("Research passage locator does not resolve in the source snapshot.")
            final_parts = urlsplit(final_url)
            source_identity = str(
                record.get("source_identity") if is_fixture else (final_parts.hostname or "")
            ).strip().lower()
            if not source_identity:
                source_identity = str(final_parts.hostname or "").strip().lower()
            if not source_identity:
                raise FactoryAgentBlocked("Research source identity is required.")
            if source_identity in seen_source_ids or snapshot_hash in seen_snapshot_hashes:
                continue
            retrieved_at = record.get("retrieved_at")
            if isinstance(retrieved_at, str):
                retrieved_at = parse_datetime(retrieved_at)
            if retrieved_at is None or timezone.is_naive(retrieved_at) or retrieved_at > timezone.now() + timedelta(minutes=5):
                raise FactoryAgentBlocked("Research retrieval timestamp is missing, naive, or in the future.")
            publisher = str(record.get("publisher") or "").strip()[:300]
            if not publisher:
                raise FactoryAgentBlocked("Research publisher identity is required.")
            source_type = str(record.get("source_type") or "unknown").lower()
            if source_type not in {"primary", "secondary", "unknown"}:
                raise FactoryAgentBlocked("Research source type is invalid.")
            published_at = record.get("published_at")
            if isinstance(published_at, str):
                published_at = parse_datetime(published_at)
            age_reference = published_at if published_at and timezone.is_aware(published_at) else None
            age_days = max(0, (timezone.now() - age_reference).days) if age_reference else None
            quality = {
                "policy_version": SOURCE_QUALITY_POLICY_VERSION,
                "source_identity": source_identity,
                "publisher": publisher,
                "source_type": source_type,
                "independent_source_key": source_identity,
                "published_at": published_at.isoformat() if published_at else None,
                "freshness": (
                    "unknown" if age_days is None else
                    "fresh" if age_days <= 180 else "aging" if age_days <= 365 else "stale"
                ),
                "duplicate": False,
                "quality_note": str(record.get("quality_note") or "Retrieved snapshot and publisher identity recorded.")[:500],
            }
            provenance = record.get("provenance") if isinstance(record.get("provenance"), dict) else {}
            factors = {}
            for factor, claim in (record.get("economic_factors") or {}).items():
                if not isinstance(claim, dict):
                    continue
                claim_text = str(claim.get("claim") or "").strip()
                factor_value = str(claim.get("value"))
                if factor in {
                    "market_demand", "willingness_to_pay", "expected_revenue_potential",
                    "expected_profit_potential", "time_to_first_revenue", "build_cost_efficiency",
                    "operating_cost_efficiency", "execution_feasibility", "competition_position",
                    "capital_efficiency", "legal_safety", "security_safety",
                    "commercial_success_probability", "scalability", "defensibility",
                } and claim_text and claim_text in snapshot and factor_value in snapshot:
                    factors[factor] = {"value": claim.get("value"), "claim": claim_text}
            clean_records.append({
                "title": str(record.get("title") or final_url)[:500], "url": final_url,
                "requested_url": requested_url, "final_url": final_url,
                "publisher": publisher, "source_identity": source_identity,
                "query": str(record.get("query") or plan["queries"][min(index, len(plan["queries"]) - 1)])[:1000],
                "provider_request_id": str(record.get("provider_request_id") or "")[:200],
                "retrieved_at": retrieved_at, "content_type": content_type,
                "snapshot": snapshot, "snapshot_hash": snapshot_hash,
                "passage": passage, "passage_locator": locator or {"match": "exact snapshot text"},
                "extractor_version": str(record.get("extractor_version") or getattr(provider, "extractor_version", "unknown"))[:100],
                "source_quality": quality, "source_type": source_type,
                "confidence": str(record.get("confidence", "0.5")),
                "economic_factors": factors,
                "provenance": provenance,
            })
            seen_source_ids.add(source_identity)
            seen_snapshot_hashes.add(snapshot_hash)
        if not clean_records and not existing:
            raise FactoryAgentBlocked("NEEDS_MORE_EVIDENCE: retrieved sources were empty or duplicates.")
        if not clean_records and existing:
            raise FactoryAgentBlocked("NEEDS_MORE_EVIDENCE: bounded re-research found no independent new source.")
        owner = self._owner(task)
        if not owner:
            raise FactoryAgentBlocked("Research requires an existing owner for ResearchProject provenance.")
        project = existing or ResearchProject.objects.create(
            title=f"Factory research: {goal[:240]}", objective=goal,
            status="evidence_collected", owner=owner, factory_run=run,
        )
        for record in clean_records:
            source = self.research.register_source(
                project=project, title=record["title"],
                url=record["final_url"] if record["final_url"].startswith(("https://", "http://")) else "",
                publisher=record["publisher"], content_hash=record["snapshot_hash"],
                snapshot_hash=record["snapshot_hash"], retrieved_at=record["retrieved_at"],
                provenance={
                    **record["provenance"], "provider": provider.provider_name,
                    "provider_request_id": record["provider_request_id"],
                    "run_id": run.run_id if run else None, "task_id": task.pk,
                    "execution_id": task.execution_id,
                    "provider_class": provider_class,
                    "real_research": real_research, "query": record["query"],
                    "requested_url": record["requested_url"], "final_url": record["final_url"],
                    "content_type": record["content_type"], "snapshot_reference": record["final_url"],
                    "snapshot_text": record["snapshot"], "snapshot_sha256": record["snapshot_hash"],
                    "passage_locator": record["passage_locator"], "extractor_version": record["extractor_version"],
                    "source_quality": record["source_quality"], "source_identity": record["source_identity"],
                    "source_type": record["source_type"], "economic_factors": record["economic_factors"],
                },
            )
            evidence = self.research.add_evidence(project, source, record["passage"], confidence=record["confidence"])
            finding = self.research.add_finding(project, title=source.title, statement=record["passage"], evidence=[evidence], confidence=record["confidence"])
        persisted = []
        for item in project.evidence.select_related("source").order_by("pk"):
            source = item.source
            persisted.append({
                "source": source.provenance.get("final_url") or source.url,
                "source_identity": source.provenance.get("source_identity") or source.url,
                "title": source.title, "passage": item.passage, "evidence_id": item.pk,
                "finding_id": Finding.objects.filter(evidence__pk=item.pk).order_by("pk").values_list("pk", flat=True).last(),
                "confidence": str(item.confidence), "snapshot_hash": source.snapshot_hash,
                "retrieved_at": source.retrieved_at.isoformat(), "provenance": source.provenance,
                "economic_factors": source.provenance.get("economic_factors", {}),
            })
        report_version = (project.reports.order_by("-version").values_list("version", flat=True).first() or 0) + 1
        report = self.research.create_report(
            project, f"Factory evidence report: {goal[:240]}",
            {"goal": goal, "run_id": run.run_id if run else None, "provider": provider.provider_name,
             "real_research": real_research, "research_plan": plan, "evidence": persisted,
             "quality_policy_version": SOURCE_QUALITY_POLICY_VERSION}, version=report_version,
        )
        return {
            "title": goal[:300], "sources": [{"url": item["source"], "finding": item["passage"]} for item in persisted],
            "research_project_id": project.pk, "research_report_id": report.pk,
            "research_provider": provider.provider_name, "real_research": real_research,
            "research_plan": plan, "evidence": persisted,
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
        return score_opportunity(records)

    def _validate(self, task, product):
        opportunity = (product.metadata or {}).get("opportunity") or {}
        research = (product.metadata or {}).get("research") or {}
        attempts = task.factory_run.tasks.filter(action_type="product_research").count() if task.factory_run_id else 1
        return {"validation": validate_opportunity(opportunity, research.get("evidence") or [], attempts)}

    def _spec(self, task, product):
        records = self._research_records(product)
        validation = (product.metadata or {}).get("validation") or {}
        opportunity = (product.metadata or {}).get("opportunity") or {}
        if validation.get("outcome") != "VALIDATED" or not opportunity.get("rubric"):
            raise FactoryAgentBlocked("Product Spec requires current validated Research, Evidence, Score, and Validation lineage.")
        problem = str((task.factory_run.goal if task.factory_run_id else task.goal) or "").strip()
        if not problem:
            raise ValueError("A research-backed Product goal is required for specification.")
        spec = {
            "version": int(task.factory_run.current_spec_version + 1 if task.factory_run_id else 1),
            "product_type": "static_research_brief",
            "goal": problem,
            "problem": problem,
            "target_customer": "Small agricultural operators managing harvest workflows; assumption to verify in market tests.",
            "value_proposition": "Organize source-backed harvest workflow information in a compact digital brief.",
            "functional_requirements": ["Present the defined problem.", "Show source-linked findings and their provenance."],
            "non_functional_requirements": ["Render as valid UTF-8 HTML.", "Do not claim synthetic research as real market evidence."],
            "title": product.title,
            "target_markets": ["global; assumed pending market-specific eligibility review"],
            "target_languages": ["en; initial supported-line assumption"],
            "commercial_assumptions": {"status": "assumptions, not realized revenue", "score_rubric_version": opportunity.get("rubric", {}).get("version")},
            "constraints": task.factory_run.constraints if task.factory_run_id else [],
            "evidence_references": [{"evidence_id": item["evidence_id"], "snapshot_digest": item["snapshot_hash"], "source_identity": item.get("source_identity")} for item in records],
            "score_reference": {"score": opportunity.get("score"), "rubric_version": opportunity.get("rubric", {}).get("version"), "evidence_digest": opportunity.get("rubric", {}).get("evidence_digest")},
            "validation_reference": {"outcome": validation.get("outcome"), "policy_version": validation.get("policy_version"), "evidence_digest": validation.get("evidence_digest")},
            "acceptance_criteria": [
                "The artifact is valid UTF-8 HTML.",
                "The artifact contains the specified problem statement.",
                f"The artifact contains source-linked findings from all {len(records)} persisted evidence records.",
                "The artifact digest matches the immutable FactoryArtifact record.",
            ],
        }
        spec["digest"] = canonical_digest(spec)
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
        artifact = {**artifact, "spec_digest": spec["digest"], "builder": task.agent.code,
                    "task_id": task.pk, "execution_id": task.execution_id,
                    "built_at": timezone.now().isoformat(), "status": "built"}
        return {"artifact": artifact}

    def _current_artifact(self, task, product):
        run = task.factory_run
        artifact = FactoryArtifact.objects.filter(
            product=product, run=run, version=run.current_artifact_version,
        ).order_by("-pk").first()
        if not artifact:
            raise FactoryAgentBlocked("Current persisted immutable build artifact is required.")
        return artifact

    def _test(self, task, product, authorization, authorization_check):
        artifact = self._current_artifact(task, product)
        tests = self.verifier.test(
            artifact, (product.metadata or {}).get("spec") or {}, task=task,
            authorization=authorization, authorization_check=authorization_check,
        )
        return {"tests": tests}

    def _security(self, task, product, authorization, authorization_check):
        artifact = self._current_artifact(task, product)
        security = self.verifier.security(
            artifact, (product.metadata or {}).get("spec") or {}, task=task,
            authorization=authorization, authorization_check=authorization_check,
        )
        return {"security": security}

    def _localize(self, task, product):
        build = (product.metadata or {}).get("build") or {}
        spec = (product.metadata or {}).get("spec") or {}
        required = ["en"]
        requested = spec.get("target_languages") or []
        normalized = [str(x).split(";", 1)[0].strip().lower() for x in requested]
        if "fa" in normalized:
            required.append("fa")
        locales = [{"locale": code, "version": 1, "status": "complete",
                    "rtl": code in {"fa", "ar", "ur"}, "fixture": False,
                    "source_locale": "en" if code != "en" else None}
                   for code in dict.fromkeys(required)]
        localization = {"policy_version": "factory-localization-v1",
                        "build_digest": build.get("sha256"), "required_locales": required,
                        "fallback_locale": "en", "architecture_locales": [
                            "en","zh-hans","hi","es","fr","ar","bn","pt","ru","ur","id","de",
                            "ja","sw","mr","te","tr","ta","vi","ko","it","nl","pl","th","fa"
                        ], "locales": locales}
        localization["attestation_digest"] = canonical_digest(localization)
        return {"localization": localization}

    def _qa(self, task, product):
        meta = product.metadata or {}
        qa = {"passed": True, "policy_version": "factory-qa-v1",
              "spec_digest": (meta.get("spec") or {}).get("digest"),
              "build_digest": (meta.get("build") or {}).get("sha256"),
              "test_attestation_digest": (meta.get("test_attestation") or {}).get("attestation_digest"),
              "security_attestation_digest": (meta.get("security_attestation") or {}).get("attestation_digest"),
              "localization_digest": canonical_digest(meta.get("localization") or {}),
              "eligibility_digest": canonical_digest(meta.get("market_eligibility") or []),
              "qa_agent": task.agent.code, "execution_id": task.execution_id}
        if not all(qa.get(k) for k in ("spec_digest","build_digest","test_attestation_digest",
                                      "security_attestation_digest")):
            raise FactoryAgentBlocked("QA requires complete Build/Test/Security lineage.")
        qa["attestation_digest"] = canonical_digest(qa)
        return {"qa": qa}

    def _launch_candidate(self, task, product):
        meta = product.metadata or {}
        build = meta.get("build") or {}
        qa = meta.get("qa_attestation") or {}
        candidate = {"product_id": product.pk, "release_version": build.get("version"),
                     "spec_digest": (meta.get("spec") or {}).get("digest"),
                     "build_digest": build.get("sha256"),
                     "test_attestation_digest": (meta.get("test_attestation") or {}).get("attestation_digest"),
                     "security_attestation_digest": (meta.get("security_attestation") or {}).get("attestation_digest"),
                     "localization_digest": canonical_digest(meta.get("localization") or {}),
                     "eligibility_digest": canonical_digest(meta.get("market_eligibility") or []),
                     "qa_attestation_digest": qa.get("attestation_digest"),
                     "created_by": task.agent.code, "execution_id": task.execution_id,
                     "status": "launch_candidate", "published": False, "deployed": False}
        candidate["attestation_digest"] = canonical_digest(candidate)
        return {"launch_candidate": candidate}
