"""Keyless, self-hosted real-staging web research provider.

Search and source retrieval run directly from the staging host. The provider is
read-only, bounded, provenance-preserving, and rejects unsafe/private URLs via
the Factory runtime policy. It does not generate or invent economic ratings.
"""
import hashlib
import logging
import html
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote_plus, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from django.conf import settings
from django.utils import timezone

from .factory_agent_runtime import FactoryAgentBlocked, ResearchProvider


logger = logging.getLogger(__name__)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class SelfHostedStagingResearchProvider(ResearchProvider):
    provider_name = "self-hosted-staging"
    real_research = True
    extractor_version = "self-hosted-web-v1"
    search_endpoint = "https://search.brave.com/search?q={query}&source=web"
    user_agent = "ZomorodResearch/1.0 (+https://zomorodmelal.ir)"

    def __init__(self):
        if settings.SAEIT_ENV != "staging":
            raise FactoryAgentBlocked("Self-hosted staging research requires SAEIT_ENV=staging")
        self.opener = build_opener(ProxyHandler({}), _NoRedirect())

    def _get(self, url, *, timeout, byte_limit, safe_url_policy):
        if not safe_url_policy(url):
            err = FactoryAgentBlocked("Research URL rejected by safe URL policy")
            err.policy_rejected = True
            raise err
        req = Request(url, headers={"User-Agent": self.user_agent, "Accept": "text/html,text/plain,application/json"})
        try:
            with self.opener.open(req, timeout=max(1.0, min(float(timeout), 30.0))) as response:
                content_type = response.headers.get_content_type().lower()
                if content_type not in {"text/html", "text/plain", "application/json", "text/csv", "application/xml", "text/xml"}:
                    raise FactoryAgentBlocked("Research source content type is unsupported")
                raw = response.read(byte_limit + 1)
                if len(raw) > byte_limit:
                    raise FactoryAgentBlocked("Research source exceeds byte budget")
                charset = response.headers.get_content_charset() or "utf-8"
                return response.geturl(), content_type, raw.decode(charset, errors="replace")
        except HTTPError as exc:
            if 300 <= exc.code < 400:
                raise FactoryAgentBlocked("Research redirect rejected") from None
            if exc.code in {401, 403, 429}:
                err = RuntimeError("Research source temporarily unavailable")
                err.status_code = exc.code
                raise err from None
            raise RuntimeError("Research source HTTP failure") from None
        except (URLError, TimeoutError, OSError) as exc:
            raise RuntimeError(f"Research network failure: {type(exc).__name__}") from exc

    @staticmethod
    def _search_links(body):
        links = []
        for match in re.finditer(r'href=["\']([^"\']+)["\']', body, re.I):
            href = html.unescape(match.group(1))
            if href.startswith("/url?"):
                target = parse_qs(urlsplit(href).query).get("q", [""])[0]
            elif href.startswith("http://") or href.startswith("https://"):
                target = href
            else:
                continue
            host = (urlsplit(target).hostname or "").lower()
            if host and not any(engine in host for engine in ("google.", "search.brave.com", "imgs.search.brave.com", "cdn.search.brave.com", "tiles.search.brave.com")) and target not in links:
                links.append(target)
        return links

    @staticmethod
    def _text_snapshot(body, content_type):
        if content_type != "text/html":
            return body.strip()
        body = re.sub(r"(?is)<(script|style|noscript).*?>.*?</\1>", " ", body)
        body = re.sub(r"(?s)<[^>]+>", " ", body)
        return re.sub(r"\s+", " ", html.unescape(body)).strip()

    def search(self, *, goal, constraints, plan, task, authorization, authorization_check,
               timeout_seconds, max_results, max_snapshot_bytes, max_redirects, safe_url_policy):
        if not authorization_check(authorization, task, "product_research"):
            raise FactoryAgentBlocked("Research authorization missing or revoked")
        if not callable(safe_url_policy):
            raise FactoryAgentBlocked("Research requires safe URL enforcement")
        started = time.monotonic()
        records, seen_hosts = [], set()
        failures = {}

        def record_failure(stage, reason):
            key = f'{stage}:{reason}'
            failures[key] = failures.get(key, 0) + 1
            logger.warning('staging_research_failure task_id=%s stage=%s reason=%s count=%d',
                           getattr(task, 'pk', None), stage, reason, failures[key])
        request_seq = 0
        for query in plan["queries"][:3]:
            if not authorization_check(authorization, task, "product_research"):
                raise FactoryAgentBlocked("Research authorization revoked")
            remaining = timeout_seconds - (time.monotonic() - started)
            if remaining <= 0:
                break
            search_url = self.search_endpoint.format(query=quote_plus(query))
            try:
                _, _, search_body = self._get(
                    search_url, timeout=remaining, byte_limit=min(max_snapshot_bytes * 4, 1_000_000),
                    safe_url_policy=safe_url_policy,
                )
            except FactoryAgentBlocked as exc:
                record_failure('discovery', 'policy_rejected' if getattr(exc, 'policy_rejected', False) else 'blocked')
                if getattr(exc, 'policy_rejected', False):
                    raise
                continue
            except RuntimeError as exc:
                record_failure('discovery', 'http_' + str(exc.status_code) if getattr(exc, 'status_code', None) else 'network_or_http')
                continue
            request_seq += 1
            for url in self._search_links(search_body):
                if len(records) >= max_results:
                    return records
                if not safe_url_policy(url):
                    record_failure('source', 'unsafe_url')
                    continue
                host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
                if not host or host in seen_hosts:
                    continue
                remaining = timeout_seconds - (time.monotonic() - started)
                if remaining <= 0:
                    break
                try:
                    final_url, content_type, body = self._get(
                        url, timeout=remaining, byte_limit=max_snapshot_bytes,
                        safe_url_policy=safe_url_policy,
                    )
                except (FactoryAgentBlocked, RuntimeError) as exc:
                    record_failure('fetch', 'policy_rejected' if getattr(exc, 'policy_rejected', False) else ('http_' + str(exc.status_code) if getattr(exc, 'status_code', None) else type(exc).__name__))
                    if getattr(exc, 'policy_rejected', False):
                        raise
                    continue
                if final_url != url and not safe_url_policy(final_url):
                    continue
                snapshot = self._text_snapshot(body, content_type)
                if not snapshot:
                    record_failure('extract', 'empty_content')
                    continue
                encoded = snapshot.encode("utf-8")
                if len(encoded) > max_snapshot_bytes:
                    snapshot = encoded[:max_snapshot_bytes].decode("utf-8", errors="ignore")
                passage = snapshot[:10000].strip()
                if not passage:
                    continue
                digest = hashlib.sha256(snapshot.encode("utf-8")).hexdigest()
                records.append({
                    "title": passage[:180], "url": final_url, "requested_url": url,
                    "final_url": final_url, "redirect_count": 0,
                    "publisher": host, "source_identity": host, "query": query,
                    "provider_request_id": f"selfhost-{request_seq}-{digest[:16]}",
                    "retrieved_at": timezone.now().isoformat(), "content_type": content_type,
                    "snapshot": snapshot, "snapshot_sha256": digest, "passage": passage,
                    "passage_locator": {"start": 0, "end": len(passage)},
                    "extractor_version": self.extractor_version, "source_type": "unknown",
                    "confidence": "0.5", "economic_factors": {},
                    "provenance": {
                        "transport": "direct-https", "provider_mediated_snapshot": False,
                        "real_research": True, "provider": self.provider_name,
                        "provider_request_id": f"selfhost-{request_seq}-{digest[:16]}",
                        "response_sha256": digest,
                    },
                })
                seen_hosts.add(host)
        if not records:
            summary = ','.join(f'{key}={count}' for key, count in sorted(failures.items())) or 'no_discovered_urls'
            raise FactoryAgentBlocked(f'NEEDS_MORE_EVIDENCE: no usable direct web source snapshots ({summary})')
        return records
