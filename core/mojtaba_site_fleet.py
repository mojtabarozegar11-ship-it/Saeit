"""Site-native monitoring capabilities for the ONE Mojtaba.bot.ai identity.

Source-stage only. A site role is a capability, never an independent agent,
invoice worker, product publisher, or an assertion of a deployed bot. Nothing
here reads cPanel secrets, mutates site state, or connects to the central VPS.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
import json
import re

CANONICAL_BOT = "mojtaba.bot.ai"
TENANTS = {
    "zomorodmelal": "https://zomorodmelal.ir",
    "mojplaywin": "https://mojplaywin.com",
}
ZM_ROUTES = {
    "master": "/", "content": "/knowledge/", "seo": "/search/",
    "commerce": "/store/", "agriculture": "/agriculture/",
    "research": "/research/", "economic": "/economy/",
    "weather": "/weather/", "quality": "/about/",
    "media": "/news/", "security": "/business/",
}
# Only routes independently named in the site's existing published documents.
MPW_ROUTES = {"public_home": "/", "public_store": "/store/", "public_games": "/games/"}
ROUTES = {"zomorodmelal": ZM_ROUTES, "mojplaywin": MPW_ROUTES}
MPW_NAMED_ROBOTS = (
    "main_route_observer", "editorial_integrity", "draft_fingerprint",
    "editorial_review_queue", "agent_runtime_watch", "seo_metadata",
    "reference_origin", "release_reconciliation", "public_content_security",
    "disk_capacity", "publication_worklist",
)
# Only these precise legacy files may *eventually* be considered for removal.
# Parent directories and application files must never be purged by inference.
RETIRE_CANDIDATE_SUFFIXES = {
    "zomorodmelal": (
        "site_agent_cycle_cli.php", "site_agents.php", "site_agent_workforce.php",
    ),
    "mojplaywin": ("mpw_monitor_collector.py",),
}
# Each is required with literal boolean true for EACH of the two tenants.
GATES = (
    "site_inventory_fresh", "bot_dns_tls_verified", "bot_runtime_deployed",
    "new_executor_two_distinct_cycles_verified",
    "role_by_role_functional_receipts_verified",
    "legacy_77_executors_accounted_for",
    "agent_history_exported_and_reconciled",
    "pending_queued_running_blocked_zero_or_transferred",
    "publication_and_order_boundaries_preserved",
    "backups_integrity_verified", "off_host_restore_verified",
    "source_file_hashes_verified", "exact_legacy_cron_identity_verified",
    "replacement_scheduler_single_owner_verified",
    "rollback_drill_verified", "tenant_boundary_verified",
)


class SiteFleetError(ValueError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def inventory():
    """Known source identities only; counts are NOT live workers."""
    return {
        "canonical_bot": CANONICAL_BOT,
        "zomorodmelal": {
            "site_health_roles": tuple(ZM_ROUTES), "role_count": len(ZM_ROUTES),
            "actual_active_worker_count": None,
        },
        "mojplaywin": {
            "public_probe_routes": tuple(MPW_ROUTES),
            "legacy_named_robot_slots": MPW_NAMED_ROBOTS,
            "legacy_module_slots_not_functionally_verified": 77,
            "legacy_master_slots": ("master_gen64", "agent_gen65"),
            "actual_active_worker_count": None,
        },
        "live_execution_verified": False,
        "legacy_cleanup_authorized": False,
    }


def probe(tenant, role, *, transport=None):
    """Bounded, HTTPS-only GET of an exactly allowlisted site route.

    Records hashes and structural response properties; never persists raw
    page content or claims this check proves product production or payment.
    """
    if tenant not in TENANTS or role not in ROUTES[tenant]:
        raise SiteFleetError("UNREGISTERED_TENANT_OR_ROUTE")
    url = TENANTS[tenant] + ROUTES[tenant][role]
    if transport is None:
        req = Request(url, headers={"User-Agent": "MojtabaSiteFleet/1.0",
                                    "Accept": "text/html,application/json"})
        try:
            with build_opener(_NoRedirect).open(req, timeout=7) as response:
                status = response.status
                content_type = response.headers.get("Content-Type", "")
                data = response.read(262145)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            return {"bot": CANONICAL_BOT, "tenant": tenant, "role": role,
                    "state": "unverified", "transport_error_class": type(exc).__name__,
                    "publication_verified": False, "payment_verified": False}
    else:
        result = transport(url)
        if not (isinstance(result, tuple) and len(result) == 3):
            raise SiteFleetError("INVALID_TEST_TRANSPORT")
        status, content_type, data = result
    if type(status) is not int or not isinstance(content_type, str) or not isinstance(data, bytes):
        raise SiteFleetError("INVALID_RESPONSE_TYPES")
    safe_type = bool(re.match(r"^(text/html|application/json|application/xhtml\+xml)(;|$)",
                              content_type, flags=re.I))
    valid = status == 200 and 64 <= len(data) <= 262144 and safe_type
    return {
        "bot": CANONICAL_BOT, "tenant": tenant, "role": role,
        "state": "http_probe_ok" if valid else "unverified",
        "http_status": status, "response_bytes": len(data),
        "response_sha256": sha256(data).hexdigest() if valid else None,
        "publication_verified": False, "payment_verified": False,
        "product_generated_verified": False,
    }


def retirement_decision(attestations, *, now=None):
    """Require fresh independent evidence for BOTH tenant cutovers.

    Pure analysis; never returns shell commands or deletes filesystem paths.
    Future destructive operations require separate host-scoped inventory and
    application-specific implementation, not this result alone.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise SiteFleetError("UTC_CLOCK_REQUIRED")
    decision = {"canonical_bot": CANONICAL_BOT, "site_decisions": {},
                "all_sites_ready": False, "files_deleted": 0, "crons_removed": 0}
    if not isinstance(attestations, dict) or set(attestations) != set(TENANTS):
        raise SiteFleetError("EXACT_TWO_TENANT_ATTESTATIONS_REQUIRED")
    for tenant in TENANTS:
        row = attestations[tenant]
        if not isinstance(row, dict) or row.get("tenant") != tenant:
            raise SiteFleetError("TENANT_ATTESTATION_MISMATCH")
        try:
            moment = datetime.fromisoformat(row["observed_at_utc"].replace("Z", "+00:00"))
            if moment.tzinfo is None:
                raise ValueError("timezone required")
            fresh = timedelta(0) <= now - moment <= timedelta(minutes=30)
        except (ValueError, TypeError, KeyError, AttributeError):
            fresh = False
        failed = [name for name in GATES if row.get(name) is not True]
        if not fresh:
            failed.insert(0, "fresh_timestamp_within_30_minutes")
        # Role-level counts cannot substitute for immutable receipts.
        receipts = row.get("functional_receipt_ids")
        if not isinstance(receipts, list) or not receipts or not all(
            isinstance(x, str) and bool(re.fullmatch(r"[0-9a-f]{64}", x)) for x in receipts
        ) or len(set(receipts)) != len(receipts):
            failed.append("independent_functional_receipt_ids_missing")
        decision["site_decisions"][tenant] = {
            "ready_for_host_scoped_retirement_review": not failed,
            "blockers": failed,
            "only_candidate_filenames": RETIRE_CANDIDATE_SUFFIXES[tenant],
            "root_or_parent_directory_deletion_allowed": False,
        }
    decision["all_sites_ready"] = all(
        item["ready_for_host_scoped_retirement_review"]
        for item in decision["site_decisions"].values()
    )
    return decision



def run_one_bot_public_cycle(*, transport=None):
    """Observe the 14 known public routes in ONE process, no site workers.

    Site-local PHP/cron can be considered for retirement only after a separate
    verified cutover; this never replaces private editorial/quality workers.
    """
    observations = []
    for tenant in TENANTS:
        for role in ROUTES[tenant]:
            observations.append(probe(tenant, role, transport=transport))
    return {
        "canonical_bot": CANONICAL_BOT,
        "single_process_route_monitor": True,
        "public_checks_count": len(observations),
        "http_ok_count": sum(x["state"] == "http_probe_ok" for x in observations),
        "observations": observations,
        "private_robots_or_modules_executed": 0,
        "products_generated": 0,
        "payments_collected": 0,
        "automatic_site_cleanup": False,
    }


def main():
    import sys
    if sys.argv[1:] == ["--observe-public"]:
        result = run_one_bot_public_cycle()
    elif len(sys.argv) == 1:
        result = inventory()
    else:
        raise SystemExit("usage: python -m core.mojtaba_site_fleet [--observe-public]")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
