"""Network-backed, staging-only Tavily research adapter.

The API key is read locally from STAGING_RESEARCH_API_KEY. No credential belongs in Git.
"""
import json
import os
import urllib.error
import urllib.request
from datetime import timezone as dt_timezone
from email.utils import parsedate_to_datetime

from django.utils import timezone

from .factory_agent_runtime import FactoryAgentBlocked, ResearchProvider


class TavilyStagingResearchProvider(ResearchProvider):
    provider_name = "tavily-staging"
    real_research = True
    extractor_version = "tavily-staging-v1"
    endpoint = "https://api.tavily.com/search"

    def _request(self, query, *, timeout_seconds, max_results):
        key = os.environ.get("STAGING_RESEARCH_API_KEY", "").strip()
        if not key:
            raise FactoryAgentBlocked("PROVIDER_UNAVAILABLE: STAGING_RESEARCH_API_KEY is not configured.")
        payload = json.dumps({
            "api_key": key,
            "query": query,
            "search_depth": "advanced",
            "max_results": min(max(2, int(max_results)), 6),
            "include_answer": False,
            "include_raw_content": True,
        }).encode("utf-8")
        req = urllib.request.Request(self.endpoint, data=payload, method="POST",
                                     headers={"Content-Type": "application/json", "User-Agent": "Zomorod-Staging/1"})
        try:
            with urllib.request.urlopen(req, timeout=min(max(float(timeout_seconds), 1), 120)) as response:
                if response.status != 200:
                    raise FactoryAgentBlocked(f"PROVIDER_UNAVAILABLE: Tavily returned HTTP {response.status}.")
                body = response.read(2_000_000)
                return json.loads(body.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            err = FactoryAgentBlocked(f"PROVIDER_UNAVAILABLE: Tavily returned HTTP {exc.code}.")
            err.status_code = exc.code
            raise err from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Tavily staging request failed: {type(exc).__name__}") from exc

    def search(self, *, goal, constraints, plan, task, authorization, authorization_check,
               timeout_seconds, max_results, max_snapshot_bytes, max_redirects, safe_url_policy):
        if not authorization_check(authorization, task, "product_research"):
            raise FactoryAgentBlocked("Research Provider call requires current ToolGateway authorization.")
        if not callable(safe_url_policy):
            raise FactoryAgentBlocked("Research requires safe URL enforcement.")
        records = []
        request_count = 0
        for query in plan["queries"][:3]:
            data = self._request(query, timeout_seconds=timeout_seconds, max_results=max_results)
            request_count += 1
            request_id = str(data.get("request_id") or f"tavily-{request_count}")
            for item in data.get("results") or []:
                url = str(item.get("url") or "").strip()
                if not safe_url_policy(url):
                    continue
                raw = item.get("raw_content") or item.get("content") or ""
                snapshot = str(raw).strip()
                if not snapshot:
                    continue
                snapshot = snapshot[:max_snapshot_bytes]
                passage = str(item.get("content") or snapshot[:4000]).strip()
                if passage not in snapshot:
                    snapshot = passage + "\n\n" + snapshot
                    snapshot = snapshot[:max_snapshot_bytes]
                    if passage not in snapshot:
                        continue
                title = str(item.get("title") or url).strip()
                publisher = urllib.request.urlparse(url).hostname if hasattr(urllib.request, "urlparse") else ""
                if not publisher:
                    from urllib.parse import urlsplit
                    publisher = urlsplit(url).hostname or ""
                records.append({
                    "title": title[:500], "url": url, "requested_url": url, "final_url": url,
                    "publisher": publisher, "source_identity": publisher.lower(),
                    "query": query, "provider_request_id": request_id,
                    "retrieved_at": timezone.now().isoformat(), "content_type": "text/plain",
                    "snapshot": snapshot, "passage": passage,
                    "extractor_version": self.extractor_version, "source_type": "secondary",
                    "confidence": "0.65", "economic_factors": {},
                    "provenance": {"real_research": True, "provider": self.provider_name,
                                   "provider_request_id": request_id},
                })
                if len(records) >= max_results:
                    return records
        return records
