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
QUALITY_ISSUES = frozenset({
    "missing_title", "title_over_100_chars", "h1_count_not_one",
    "missing_meta_description", "no_anchor_links",
    "invalid_or_short_html", "invalid_html_encoding",
})

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
        public_row = {
            "role": key[1],
            "state": state,
            "html_digest": digest if state == "http_probe_ok" else None,
        }
        qa = item.get("site_html_quality")
        if qa is not None:
            if (state != "http_probe_ok" or not isinstance(qa, dict)
                    or qa.get("source_content_logged") is not False
                    or qa.get("status") not in ("review", "blocked")
                    or type(qa.get("score")) is not int
                    or not 0 <= qa["score"] <= 100
                    or not isinstance(qa.get("issues"), list)
                    or any(x not in QUALITY_ISSUES for x in qa["issues"])):
                raise SiteFleetError("UNTRUSTED_STRUCTURAL_QA")
            public_row["structural_qa"] = {
                "status": qa["status"], "score": qa["score"],
                "issues": sorted(set(qa["issues"])),
            }
        details[key[0]].append(public_row)
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
            "structural_qa_reported_roles": sum(
                "structural_qa" in line for line in lines
            ),
            "structural_qa_results": [
                {"role": line["role"], **line["structural_qa"]}
                for line in lines if "structural_qa" in line
            ],
            "legacy_sqlite_history_migrated": False,
            "legacy_php_dashboard_replaced": False,
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



def inspect_public_monitor_continuity(*, now=None):
    """Read only the last 24 hours of canonical public-monitor AuditLog rows.

    Two independent successful cycles spaced >=5 min qualify solely for
    *public route monitoring* review. They NEVER prove private agent migration,
    payment safety, DNS ownership, publication or host cleanup permission.
    """
    from datetime import datetime, timedelta, timezone

    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise SiteFleetError("UTC_CLOCK_REQUIRED")
    oldest = now - timedelta(hours=24)
    records = list(
        AuditLog.objects.filter(
            actor_type="system", actor_id=ACTOR, action=ACTION,
            target_type="site_native_public_monitor",
            created_at__gte=oldest,
            created_at__lte=now,
        ).order_by("-created_at", "-pk").values(
            "target_id", "trace_id", "created_at", "after_state",
        )[:250]
    )
    results = {}
    for tenant, roles in ROUTES.items():
        # No trust in missing identifiers or duplicated audit rows.
        grouped = {}
        for row in records:
            if row["target_id"] != tenant:
                continue
            key = row["trace_id"]
            grouped.setdefault(key, []).append(row)
        good = []
        for key, items in grouped.items():
            if not (isinstance(key, str) and CYCLE_ID.fullmatch(key)
                    and len(items) == 1):
                continue
            item = items[0]
            state = item.get("after_state")
            if not isinstance(state, dict):
                continue
            if (state.get("observed_roles") != len(roles)
                    or state.get("http_ok_count") != len(roles)
                    or state.get("all_public_routes_ok") is not True
                    or state.get("private_worker_execution_verified") is not False
                    or state.get("legacy_agent_retirement_authorized") is not False
                    or not isinstance(state.get("sha256_public_observations"), str)
                    or not SHA.fullmatch(state["sha256_public_observations"])):
                continue
            good.append(item["created_at"])
        times = sorted(good)
        pair_ready = len(times) >= 2 and (
            times[-1] - times[0] >= timedelta(minutes=5)
        )
        results[tenant] = {
            "successful_public_observation_receipts_24h": len(times),
            "two_distinct_spaced_cycles": bool(pair_ready),
            "public_monitor_continuity_observed": bool(pair_ready),
            "private_site_worker_replacement_verified": False,
            "legacy_php_dashboard_replaced": False,
            "legacy_sqlite_history_migrated": False,
            "legacy_host_cleanup_authorized": False,
        }
    return {
        "canonical_bot": CANONICAL_BOT,
        "evidence_source": "local_django_auditlog_not_independent_host_attestation",
        "sites": results,
        "all_public_monitors_have_two_cycles": all(
            r["two_distinct_spaced_cycles"] for r in results.values()
        ),
        "private_workers_migrated": False,
        "site_files_deleted": 0,
        "cron_entries_removed": 0,
        "legacy_host_cleanup_authorized": False,
    }
