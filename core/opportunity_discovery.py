"""Stage 1: autonomous opportunity discovery.

Discovers a bounded pool of evidence-backed product opportunities using the
configured real research provider. It is deliberately read-only: discovery
never builds, publishes, deploys, charges, or transfers funds.
"""
import hashlib
import json
import uuid
from dataclasses import dataclass
from urllib.parse import urlsplit

from django.conf import settings
from django.utils import timezone

from core.factory_agent_runtime import configured_research_provider, FactoryAgentBlocked


@dataclass(frozen=True)
class DiscoveryOpportunity:
    opportunity_id: str
    title: str
    problem: str
    audience: str
    evidence_urls: tuple
    evidence_hosts: tuple
    discovered_at: str

    def as_dict(self):
        return {
            "opportunity_id": self.opportunity_id,
            "title": self.title,
            "problem": self.problem,
            "audience": self.audience,
            "evidence_urls": list(self.evidence_urls),
            "evidence_hosts": list(self.evidence_hosts),
            "discovered_at": self.discovered_at,
        }


class OpportunityDiscovery:
    """Bounded Stage-1 discovery with provenance and deterministic deduplication."""

    DEFAULT_SEEDS = (
        "small business repetitive manual workflow pain software",
        "small business spreadsheet inventory costing pricing problems",
        "online seller profit fees inventory workflow problems",
        "restaurant food costing inventory pricing workflow problems",
        "freelancer agency repetitive admin workflow software problems",
        "creator digital product workflow repetitive problems",
    )

    def __init__(self, provider=None):
        self.provider = provider or configured_research_provider()

    @staticmethod
    def _authorization_check(_authorization, _task, action):
        return action == "product_research"

    @staticmethod
    def _safe_url(url):
        parts = urlsplit(str(url or ""))
        return parts.scheme == "https" and bool(parts.hostname)

    @staticmethod
    def _opportunity_from_record(seed, record):
        passage = " ".join(str(record.get("passage") or "").split())
        if len(passage) < 80:
            return None
        host = (urlsplit(str(record.get("final_url") or record.get("url") or "")).hostname or "").lower()
        if not host:
            return None
        # Stage 1 must not pretend an LLM-derived market thesis exists. Persist a
        # conservative evidence-backed problem statement for Stage 2 to research.
        problem = passage[:700]
        audience = seed.split(" problems", 1)[0][:180]
        digest = hashlib.sha256((seed + "|" + host + "|" + problem.lower()).encode()).hexdigest()[:20]
        return DiscoveryOpportunity(
            opportunity_id=f"opp-{digest}",
            title=f"Investigate product opportunity: {audience}",
            problem=problem,
            audience=audience,
            evidence_urls=(str(record.get("final_url") or record.get("url") or ""),),
            evidence_hosts=(host,),
            discovered_at=timezone.now().isoformat(),
        )

    def discover(self, *, seeds=None, max_opportunities=25):
        if settings.SAEIT_ENV not in {"staging", "development", "test", "ci"}:
            raise FactoryAgentBlocked("Opportunity discovery is disabled in production.")
        seeds = tuple(seeds or self.DEFAULT_SEEDS)
        limit = max(1, min(int(max_opportunities), 50))
        found, seen = [], set()
        task = type("DiscoveryTask", (), {"goal": "", "input_data": {}, "pk": 0})()
        auth = {"stage": "opportunity_discovery", "nonce": uuid.uuid4().hex}
        for seed in seeds[:12]:
            if len(found) >= limit:
                break
            task.goal = seed
            plan = {
                "queries": [seed],
                "timeout_seconds": 30,
                "max_snapshot_bytes": 120000,
                "max_redirects": 0,
            }
            records = self.provider.search(
                goal=seed, constraints={"stage": 1}, plan=plan, task=task,
                authorization=auth, authorization_check=self._authorization_check,
                timeout_seconds=30, max_results=min(6, limit - len(found)),
                max_snapshot_bytes=120000, max_redirects=0,
                safe_url_policy=self._safe_url,
            )
            for record in records:
                item = self._opportunity_from_record(seed, record)
                if not item:
                    continue
                key = (item.audience.lower(), item.evidence_hosts[0])
                if key in seen:
                    continue
                seen.add(key)
                found.append(item)
                if len(found) >= limit:
                    break
        return {
            "stage": "opportunity_discovery",
            "status": "PASS" if found else "NO_EVIDENCE",
            "provider": getattr(self.provider, "provider_name", "unknown"),
            "real_research": getattr(self.provider, "real_research", False) is True,
            "opportunity_count": len(found),
            "opportunities": [item.as_dict() for item in found],
            "next_stage": "market_research",
        }
