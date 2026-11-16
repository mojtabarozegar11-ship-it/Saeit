"""Durable, redacted public site-monitor receipts owned by ONE canonical Agent.

This logs already-computed HTTP observations, NOT proof of content generation,
private worker execution, merchant payment or successful agent retirement.
No raw HTML, private log, buyer record, API key or customer identifier is saved.
"""
from __future__ import annotations

from hashlib import sha256
import json
import re

from django.db import transaction

from .models import Agent, AuditLog
from .mojtaba_site_fleet import CANONICAL_BOT, ROUTES, SiteFleetError

ACTION = "mojtaba_site_public_monitor"
ACTOR = "mojtaba-bot-ai"
SHA = re.compile(r"^[0-9a-f]{64}$")
CYCLE_ID = re.compile(r"^[0-9a-f]{32}$")


def summarize_public_cycle(report):
    """Fail closed on absent, mixed-tenant or fabricated route structures."""
    if not isinstance(report, dict) or report.get("canonical_bot") != CANONICAL_BOT:
        raise SiteFleetError("CANONICAL_PUBLIC_REPORT_INVALID")
    observations = report.get("observations")
    if not isinstance(observations, list):
        raise SiteFleetError("OBSERVATION_LIST_MISSING")
    expected = {(tenant, role) for tenant, roles in ROUTES.items() for role in roles}
    if len(observations) != len(expected) or report.get("public_checks_count") != len(expected):
        raise SiteFleetError("INCOMPLETE_PUBLIC_SITE_CYCLE")
    seen = set()
    details = {tenant: [] for tenant in ROUTES}
    for item in observations:
        if not isinstance(item, dict):
            raise SiteFleetError("OBSERVATION_NOT_OBJECT")
        key = (item.get("tenant"), item.get("role"))
        if key not in expected or key in seen or item.get("bot") != CANONICAL_BOT:
            raise SiteFleetError("CROSS_TENANT_OR_DUPLICATE_ROLE")
        seen.add(key)
        state = item.get("state")
        if state not in ("http_probe_ok", "unverified"):
            raise SiteFleetError("INVALID_PUBLIC_STATE")
        digest = item.get("response_sha256")
        if state == "http_probe_ok" and (
            not isinstance(digest, str) or not SHA.fullmatch(digest)
            or item.get("http_status") != 200
        ):
            raise SiteFleetError("INVALID_PUBLIC_HTTP_EVIDENCE")
        if digest is not None and (not isinstance(digest, str) or not SHA.fullmatch(digest)):
            raise SiteFleetError("INVALID_RESPONSE_DIGEST")
        details[key[0]].append({
            "role": key[1],
            "state": state,
            "html_digest": digest if state == "http_probe_ok" else None,
        })
    if seen != expected:
        raise SiteFleetError("INCOMPLETE_PUBLIC_SITE_ROLES")
    result = {}
    for tenant, lines in details.items():
        lines.sort(key=lambda x: x["role"])
        canonical = json.dumps(lines, sort_keys=True, separators=(",", ":")).encode()
        result[tenant] = {
            "observed_roles": len(lines),
            "http_ok_count": sum(line["state"] == "http_probe_ok" for line in lines),
            "all_public_routes_ok": all(line["state"] == "http_probe_ok" for line in lines),
            "sha256_public_observations": sha256(canonical).hexdigest(),
            "private_worker_execution_verified": False,
            "products_generated_verified": False,
            "payment_verified": False,
            "legacy_agent_retirement_authorized": False,
        }
    return result


def record_public_cycle(report, *, cycle_id):
    """Atomically insert two site receipts, idempotent under canonical DB lock."""
    if not isinstance(cycle_id, str) or not CYCLE_ID.fullmatch(cycle_id):
        raise SiteFleetError("INVALID_CANONICAL_CYCLE_ID")
    summaries = summarize_public_cycle(report)
    with transaction.atomic():
        agent = Agent.objects.select_for_update().filter(code=ACTOR, active=True).first()
        if agent is None:
            raise SiteFleetError("CANONICAL_AGENT_NOT_PROVISIONED")
        old = list(AuditLog.objects.filter(
            actor_type="system", actor_id=ACTOR,
            action=ACTION, trace_id=cycle_id
        ).order_by("target_id", "pk"))
        if old:
            if (len(old) != len(ROUTES)
                    or {r.target_id for r in old} != set(ROUTES)
                    or any(r.after_state != summaries[r.target_id] for r in old)):
                raise SiteFleetError("CYCLE_ID_REPLAY_MISMATCH")
            return {"written": False, "idempotent_replay": True,
                    "cycle_id": cycle_id, "site_receipts": len(old)}
        for tenant in ROUTES:
            AuditLog.objects.create(
                actor_type="system", actor_id=ACTOR, action=ACTION,
                target_type="site_native_public_monitor", target_id=tenant,
                trace_id=cycle_id, before_state={}, after_state=summaries[tenant]
            )
    return {"written": True, "idempotent_replay": False,
            "cycle_id": cycle_id, "site_receipts": len(ROUTES)}
