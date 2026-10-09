"""Read-only Tavily transport. Raw source text is never replaced by generated answers."""
import hashlib
import json
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, ProxyHandler, build_opener

from django.conf import settings
from django.utils import timezone
from .factory_agent_runtime import ResearchProvider, FactoryAgentBlocked


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class TavilyStagingProvider(ResearchProvider):
    provider_name = "tavily-staging"
    real_research = True
    extractor_version = "tavily-raw-text-v1"
    endpoint = "https://api.tavily.com/search"

    def __init__(self):
        if settings.SAEIT_ENV != "staging":
            raise FactoryAgentBlocked("Tavily staging adapter requires SAEIT_ENV=staging")
        self.key = getattr(settings, "STAGING_RESEARCH_API_KEY", "")
        if not self.key:
            raise FactoryAgentBlocked("STAGING_RESEARCH_API_KEY is required")

    def search(self, *, goal, constraints, plan, task, authorization, authorization_check,
               timeout_seconds, max_results, max_snapshot_bytes, max_redirects, safe_url_policy):
        if not authorization_check(authorization, task, "product_research"):
            raise FactoryAgentBlocked("Research authorization missing or revoked")
        started = time.monotonic()
        records, publishers = [], set()
        # Fixed destination, TLS verification, no proxy inheritance or redirects.
        opener = build_opener(ProxyHandler({}), NoRedirect())
        for query in plan["queries"][:3]:
            remaining = timeout_seconds - (time.monotonic() - started)
            if remaining <= 0:
                break
            if not authorization_check(authorization, task, "product_research"):
                raise FactoryAgentBlocked("Research authorization revoked")
            body = json.dumps({"query": query, "search_depth": "basic", "max_results": min(max_results, 6),
                               "include_raw_content": True, "include_answer": False}).encode()
            request = Request(self.endpoint, data=body, headers={
                "Authorization": "Bearer " + self.key, "Content-Type": "application/json"})
            try:
                with opener.open(request, timeout=remaining) as response:
                    limit = min(max_snapshot_bytes * 8, 8 * 1048576)
                    raw = response.read(limit + 1)
                    if len(raw) > limit:
                        raise FactoryAgentBlocked("Research response exceeds byte budget")
                    payload = json.loads(raw)
            except HTTPError as exc:
                # Do not expose request headers, credentials, or provider response bodies.
                if exc.code in (401, 403) or 300 <= exc.code < 400:
                    raise FactoryAgentBlocked("Research authentication or redirect rejected") from None
                raise RuntimeError("Research service HTTP failure") from None
            if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
                raise FactoryAgentBlocked("Malformed research response")
            request_id = str(payload.get("request_id") or hashlib.sha256(raw).hexdigest())
            for item in payload["results"]:
                url = item.get("url", "")
                if not safe_url_policy(url):
                    continue
                host = urlsplit(url).hostname.lower().removeprefix("www.")
                snapshot = item.get("raw_content")
                if host in publishers or not isinstance(snapshot, str) or not snapshot.strip():
                    continue
                if len(snapshot.encode()) > max_snapshot_bytes:
                    continue
                # Search rank is NOT an economic rating. Unknown factors stay unknown.
                # Explicit source-published structured ratings may be consumed without invention.
                factors = {}
                try:
                    source_json = json.loads(snapshot)
                    if isinstance(source_json, dict) and isinstance(source_json.get("economic_factors"), dict):
                        factors = source_json["economic_factors"]
                except (ValueError, TypeError):
                    pass
                records.append({
                    "title": str(item.get("title") or url), "url": url, "requested_url": url,
                    "final_url": url, "publisher": host, "source_identity": host,
                    "query": query, "provider_request_id": request_id,
                    "retrieved_at": timezone.now().isoformat(), "content_type": "text/plain",
                    "snapshot": snapshot, "snapshot_sha256": hashlib.sha256(snapshot.encode()).hexdigest(),
                    "passage": snapshot[:10000].strip(), "passage_locator": {"match": "exact snapshot text"},
                    "extractor_version": self.extractor_version, "source_type": "unknown",
                    "confidence": "0.5", "economic_factors": factors,
                    "provenance": {"transport": "tavily-https-api", "provider_mediated_snapshot": True,
                                   "response_sha256": hashlib.sha256(raw).hexdigest(), "real_research": True},
                })
                publishers.add(host)
                if len(records) >= max_results:
                    return records
        if not records:
            raise FactoryAgentBlocked("NEEDS_MORE_EVIDENCE: no usable real raw source snapshots")
        return records
