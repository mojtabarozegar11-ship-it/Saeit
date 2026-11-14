#!/usr/bin/env python3
"""Fail-closed, offline per-source disposition from two read-only host snapshots.

This is a PREVIEW, never a deactivation authorization, live worker receipt,
accepted revenue confirmation, or a substitute for owner-specific approval.
Only fixed category labels, counts, and SHA comparison states are emitted.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import sys


SCHEMA = "mojtaba.bot.ai.live-disposition-preview.v1"
TOPOLOGY_SCHEMA = "mojtaba.bot.ai.live-topology-observation.v1"
MANIFEST_SCHEMA = "mojtaba.bot.ai.disposition-sources.v1"

# All known source groups; these are logical systems, not independently running bots.
GROUPS = {
    "django_agent_registry": {
        "hosts": ("vps", "cpanel"),
        "routes": ("online_income_cycle", "run_economic_worker", "knowledge_agent_cycle",
                   "newsletter_process_queue"),
        "files": ("unified_bot_identity.py",),
    },
    "zomorod_php_site_agent_runtime": {
        "hosts": ("cpanel",),
        "routes": ("site_agent_workforce.php", "site_agents.php"),
        "files": (),
    },
    "factory_site_federation": {
        "hosts": ("vps",),
        "routes": ("factory_agent_runtime", "factory_staging_tick",
                   "stage4_due_dispatch", "run_factory_worker"),
        "files": (),
    },
    "company_activity_intelligence": {
        "hosts": ("cpanel",),
        "routes": ("company_activity_agent_cycle",),
        "files": ("management/commands/company_activity_agent_cycle.py",),
    },
    "newsletter_legacy_roles": {
        "hosts": ("cpanel",),
        "routes": ("newsletter_process_queue", "site_agent_workforce.php"),
        "files": (),
    },
    "content_director_newsletter": {
        "hosts": ("cpanel",),
        "routes": ("newsletter_process_queue",),
        "files": ("newsletter_engine.py",),
    },
    "knowledge_content_director": {
        "hosts": ("cpanel",),
        "routes": ("knowledge_agent_cycle", "knowledge_agent_generate"),
        "files": ("management/commands/knowledge_agent_cycle.py",),
    },
    "weather_publication_module": {
        "hosts": ("cpanel",),
        "routes": ("weather_agent_cycle",),
        "files": ("weather_agent.py",),
    },
    "two_host_live_topology_observation": {
        "hosts": ("vps", "cpanel"),
        "routes": ("mojtaba_bot", "mojtaba-bot-ai", "mojtaba.bot.ai"),
        "files": ("unified_bot_identity.py",),
    },
    # The host probe already recognizes these routes. The earlier nine-group
    # preview silently omitted them, giving a misleadingly narrow disposition.
    # Indicators remain observations, never proof of live bots or safe removal.
    "mojtrade_signal_and_broker_runtime": {
        "hosts": ("vps", "cpanel"),
        "routes": ("mojtrade_observer", "SAEIT_MOJTRADE_OBSERVER_V1"),
        "files": (),
    },
    "moj_coin_game_token_workers": {
        "hosts": ("vps", "cpanel"),
        "routes": ("mojcoin",),
        "files": (),
    },
    "canonical_cycle_and_legacy_master_schedulers": {
        "hosts": ("vps", "cpanel"),
        "routes": (
            "mojtaba_bot_cycle_worker.py", "mojtaba_bot_cycle_coordinator.py",
            "autonomous_master_loop",
        ),
        "files": (),
    },
    # Neither the Android handset nor linked third-party apps can be attested
    # by a VPS/cPanel snapshot. They must remain visible unresolved scopes.
    "mobile_sms_termux_automate_runtime": {
        "hosts": (),
        "routes": (),
        "files": (),
    },
    "external_connected_app_agents": {
        "hosts": (),
        "routes": (),
        "files": (),
    },
}


def parse_snapshot(path: Path, expected_role: str, *, now: datetime) -> dict:
    if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 512000:
        raise ValueError("TOPOLOGY_FILE_UNAVAILABLE")
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) != 1 or not lines[0].startswith("MOJTABA_LIVE_TOPOLOGY="):
        raise ValueError("TOPOLOGY_FORMAT_INVALID")
    item = json.loads(lines[0].split("=", 1)[1])
    if not isinstance(item, dict) or item.get("schema") != TOPOLOGY_SCHEMA:
        raise ValueError("TOPOLOGY_SCHEMA_INVALID")
    required_maps = (
        "cron", "processes", "user_services", "system_services",
        "user_timers", "system_timers",
        "installed_source_digests", "private_php_site_registry", "attestation",
    )
    if any(not isinstance(item.get(name), dict) for name in required_maps):
        raise ValueError("TOPOLOGY_SHAPE_INVALID")
    if (item.get("host_role") != expected_role or
            item.get("read_only") is not True or
            item.get("expected_user_verified") is not True or
            item["attestation"].get("automatic_deactivation_authorized") is not False):
        raise ValueError("TOPOLOGY_IDENTITY_OR_READONLY_INVALID")
    timestamp = item.get("captured_at_utc")
    if not isinstance(timestamp, str):
        raise ValueError("TOPOLOGY_TIMESTAMP_INVALID")
    try:
        when = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("TOPOLOGY_TIMESTAMP_INVALID") from exc
    if when.tzinfo is None or not now - timedelta(hours=1) <= when <= now + timedelta(minutes=2):
        raise ValueError("TOPOLOGY_STALE_OR_FUTURE")
    return item


def trusted_count(value) -> int:
    if type(value) is int and 0 <= value <= 1000000:
        return value
    raise ValueError("TOPOLOGY_COUNT_INVALID")


def route_hits(snapshot: dict, permitted: tuple[str, ...]) -> dict:
    allowed = set(permitted)
    hit_counts = Counter()
    cron = snapshot.get("cron", {})
    if cron.get("state") == "observed":
        # An absent inventory is not proof of zero scheduled workers.
        entries = cron.get("entries")
        if not isinstance(entries, list):
            raise ValueError("TOPOLOGY_CRON_ENTRIES_INVALID")
        for row in entries:
            if not isinstance(row, dict) or not isinstance(row.get("known_route_flags"), list):
                raise ValueError("TOPOLOGY_CRON_ENTRIES_INVALID")
            flags = row["known_route_flags"]
            if any(not isinstance(tag, str) for tag in flags):
                raise ValueError("TOPOLOGY_CRON_ENTRIES_INVALID")
            for tag in set(flags):
                if tag in allowed:
                    hit_counts[("user_cron", tag)] += 1
    processes = snapshot.get("processes", {})
    if processes.get("state") == "observed":
        counts = processes.get("route_match_counts")
        if not isinstance(counts, dict):
            raise ValueError("TOPOLOGY_PROCESS_COUNTS_INVALID")
        for tag, n in counts.items():
            if type(tag) is not str:
                raise ValueError("TOPOLOGY_PROCESS_COUNTS_INVALID")
            # Even an unrecognized route must have a valid nonnegative count:
            # otherwise a corrupt inventory could be silently discarded.
            count = trusted_count(n)
            if tag in allowed:
                hit_counts[("process_argv_indicator", tag)] += count
    for layer in ("user_services", "system_services", "user_timers", "system_timers"):
        status = snapshot.get(layer, {})
        if status.get("state") != "observed":
            continue
        # Missing evidence must not masquerade as an empty unit inventory.
        units = status.get("candidate_units")
        if not isinstance(units, list):
            raise ValueError("TOPOLOGY_SYSTEMD_UNITS_INVALID")
        for unit in units:
            if not isinstance(unit, dict):
                raise ValueError("TOPOLOGY_SYSTEMD_UNITS_INVALID")
            flags = unit.get("known_route_flags")
            if not isinstance(flags, list) or any(not isinstance(tag, str) for tag in flags):
                raise ValueError("TOPOLOGY_SYSTEMD_UNITS_INVALID")
            for tag in set(flags):
                if tag in allowed:
                    hit_counts[(layer + "_candidate", tag)] += 1
    return {
        "by_observation_surface": {
            surface: int(sum(v for (s, _), v in hit_counts.items() if s == surface))
            for surface in ("user_cron", "process_argv_indicator",
                            "user_services_candidate", "system_services_candidate",
                            "user_timers_candidate", "system_timers_candidate")
        },
        "route_indicators_total_not_unique_workers": sum(hit_counts.values()),
    }


def source_revision(snapshot: dict, names: tuple[str, ...], repository_root: Path) -> dict:
    if not names:
        return {}
    observed = snapshot.get("installed_source_digests", {})
    result = {}
    for name in names:
        if name.startswith("/") or ".." in Path(name).parts:
            raise ValueError("SOURCE_ALLOWLIST_INVALID")
        candidate = repository_root / "core" / name
        record = observed.get(name)
        if (not isinstance(record, dict) or
                record.get("state") != "file_observed_not_runtime_executed" or
                not isinstance(record.get("sha256"), str) or
                not candidate.is_file() or candidate.is_symlink() or
                not 0 < candidate.stat().st_size <= 512000):
            result[name] = "unknown"
            continue
        expected = hashlib.sha256(candidate.read_bytes()).hexdigest()
        result[name] = "matches_reviewed_source" if expected == record["sha256"] else "drift_or_mismatch"
    return result


# These names are source-defined registry identifiers, not observed running bots.
PHP_ROLE_CODES = (
    "master", "content", "seo", "commerce", "agriculture", "research",
    "economic", "weather", "quality", "media", "security",
)
DJANGO_ROLE_CODES = (
    "core_research", "newsletter-specialist", "newsletter-company-news",
    "newsletter-world-watch", "newsletter-unit-reports",
    "company-activity-intelligence", "content-director",
    "knowledge-content-director", "content-research", "mojtaba-bot-ai",
)


def identity_dispositions(cpanel: dict) -> list[dict]:
    """List each source-defined identity separately without declaring it live."""
    php = cpanel.get("private_php_site_registry", {})
    observed_php = php.get("state") == "source_registry_snapshot_only"
    role_rows = php.get("agent_roles")
    has_role_rows = isinstance(role_rows, list)
    seen_php = {}
    if observed_php and has_role_rows:
        for row in role_rows:
            if (isinstance(row, dict)
                    and row.get("code") in PHP_ROLE_CODES
                    and type(row.get("enabled")) is bool):
                seen_php[row["code"]] = row["enabled"]
    identities = []
    for code in PHP_ROLE_CODES:
        if not observed_php:
            registered = "unknown_registry_unobserved"
        elif not has_role_rows:
            registered = "unknown_role_rows_unavailable"
        elif code not in seen_php:
            registered = "not_in_observed_private_registry"
        elif seen_php[code]:
            registered = "enabled_database_record_not_live_worker"
        else:
            registered = "disabled_database_record_not_retirement_proof"
        identities.append({
            "source": "cpanel_php_sqlite", "code": code,
            "registration_state": registered,
            "live_execution_verified": False,
            "next_step": "map_site_adapter_receipts_to_canonical_bot",
            "retirement_authorized": False,
        })
    for code in DJANGO_ROLE_CODES:
        identities.append({
            "source": "django_agent_registry", "code": code,
            "registration_state": "unknown_django_database_not_observed",
            "live_execution_verified": False,
            "next_step": ("verify_canonical_bot_runtime_and_task_delivery"
                          if code == "mojtaba-bot-ai"
                          else "reconcile_legacy_tasks_receipts_and_schedulers"),
            "retirement_authorized": False,
        })
    return identities


def preview(vps: dict, cpanel: dict, manifest: dict, *, repository_root: Path) -> dict:
    if (not isinstance(manifest, dict)
            or manifest.get("schema") != MANIFEST_SCHEMA
            or manifest.get("canonical_bot_id") != "mojtaba.bot.ai"):
        raise ValueError("DISPOSITION_MANIFEST_INVALID")
    sources = manifest.get("sources")
    if not isinstance(sources, list) or any(
        not isinstance(item, dict) or not isinstance(item.get("id"), str)
        for item in sources
    ):
        raise ValueError("DISPOSITION_MANIFEST_SOURCES_INVALID")
    identifiers = [item["id"] for item in sources]
    # Unknown or duplicate source groups must not disappear silently from the
    # audit. A missing known group is kept visible with a blocking finding.
    if len(identifiers) != len(set(identifiers)) or set(identifiers) - GROUPS.keys():
        raise ValueError("DISPOSITION_MANIFEST_GROUPS_UNRECONCILED")
    declared = set(identifiers)
    unresolved = manifest.get("not_yet_enumerated_runtime_scopes")
    if not isinstance(unresolved, list) or any(not isinstance(s, str) for s in unresolved):
        raise ValueError("DISPOSITION_UNSCOPED_RUNTIME_INVALID")
    groups = []
    for group_id, policy in GROUPS.items():
        observed = []
        blockers = ["no_accepted_task_delivery_receipts",
                    "no_proven_complete_external_scheduler_census",
                    "no_reconciled_historical_tasks_and_publication_receipts",
                    "no_case_specific_owner_retirement_approval"]
        for host in policy["hosts"]:
            snap = {"vps": vps, "cpanel": cpanel}[host]
            obs = {
                "host": host,
                "cron_read": snap.get("cron", {}).get("state", "unavailable"),
                "process_read": snap.get("processes", {}).get("state", "unavailable"),
                "user_services_read": snap.get("user_services", {}).get("state", "unavailable"),
                "system_services_read": snap.get("system_services", {}).get("state", "unavailable"),
                "user_timers_read": snap.get("user_timers", {}).get("state", "unavailable"),
                "system_timers_read": snap.get("system_timers", {}).get("state", "unavailable"),
                "source_revisions": source_revision(snap, policy["files"], repository_root),
                **route_hits(snap, policy["routes"]),
            }
            if host == "cpanel" and group_id == "zomorod_php_site_agent_runtime":
                php = snap.get("private_php_site_registry", {})
                obs["php_registry_state"] = php.get("state", "unknown")
                if php.get("state") == "source_registry_snapshot_only":
                    obs["php_known_roles_found"] = trusted_count(php.get("known_roles_found"))
                    obs["php_enabled_records_not_active_bots"] = trusted_count(php.get("enabled_count"))
                    # Separate known and unrecognized enabled identities; a
                    # total alone can falsely imply all roles were inventoried.
                    known_enabled = php.get("known_enabled_count")
                    unknown_enabled = php.get("unknown_enabled_count")
                    if known_enabled is None or unknown_enabled is None:
                        blockers.append("php_enabled_identity_breakdown_unavailable")
                    else:
                        known_enabled = trusted_count(known_enabled)
                        unknown_enabled = trusted_count(unknown_enabled)
                        if (known_enabled + unknown_enabled != obs["php_enabled_records_not_active_bots"]
                                or known_enabled > obs["php_known_roles_found"]
                                or (php.get("records") is not None
                                    and obs["php_enabled_records_not_active_bots"] > trusted_count(php["records"]))):
                            blockers.append("php_enabled_identity_counts_inconsistent")
                        else:
                            obs["php_known_enabled_records_not_active_bots"] = known_enabled
                            obs["php_unknown_enabled_records_not_active_bots"] = unknown_enabled
                            if unknown_enabled:
                                blockers.append("unknown_enabled_php_identities_need_reconciliation")
                else:
                    blockers.append("private_php_sqlite_snapshot_unavailable")
            if any(obs[k] != "observed" for k in
                   ("cron_read", "process_read", "user_services_read", "system_services_read",
                    "user_timers_read", "system_timers_read")):
                blockers.append("partial_host_topology_observation")
            if snap.get("cron", {}).get("enumeration_truncated") is True:
                blockers.append("host_cron_inventory_truncated")
            if snap.get("processes", {}).get("enumeration_truncated") is True:
                blockers.append("host_process_inventory_truncated")
            if any(snap.get(layer, {}).get("enumeration_truncated") is True for layer in
                   ("user_services", "system_services", "user_timers", "system_timers")):
                blockers.append("host_systemd_unit_inventory_truncated")
            if any(v == "drift_or_mismatch" for v in obs["source_revisions"].values()):
                blockers.append("installed_source_revision_differs_from_reviewed_pr")
            if any(v == "unknown" for v in obs["source_revisions"].values()):
                blockers.append("installed_source_revision_unknown")
            observed.append(obs)
        if group_id not in declared:
            blockers.append("group_missing_from_checked_in_manifest")
        if not policy["hosts"]:
            blockers.append("external_runtime_outside_vps_cpanel_observation")
        groups.append({
            "source_group": group_id,
            "source_defined_not_live_count": True,
            "host_observations": observed,
            "status": "candidate_routes_seen_but_not_verified_live"
            if any(x["route_indicators_total_not_unique_workers"] > 0 for x in observed)
            else "runtime_unverified_no_known_route_indicators",
            "blocking_evidence": sorted(set(blockers)),
            "retirement_authorized": False,
            "historical_records_can_be_deleted": False,
        })
    # These are intentionally separate denominators. Manifest registration
    # can reach 100% while every live handoff remains unknown: never blend
    # a source listing into an invented operational completion percentage.
    registered = len(declared)
    expected = len(GROUPS)
    return {
        "schema": SCHEMA, "canonical_bot": "mojtaba.bot.ai",
        "evidence_progress": {
            "known_source_group_registration": {
                "registered": registered,
                "expected_known_source_groups": expected,
                "percent": round(100 * registered / expected, 1),
                "scope": "checked_in_known_groups_only_not_a_complete_live_bot_census",
            },
            "verified_live_retirement": {
                "groups_with_verified_handoff_and_retirement": 0,
                "expected_known_source_groups": expected,
                "proof_coverage_percent": 0.0,
                "scope": "zero_verified_receipts_not_zero_actual_real_world_progress",
            },
            "overall_operational_completion_percent": None,
        },
        "sources_in_manifest": len(declared),
        "sources_evaluated": len(groups), "groups": groups,
        "unscoped_runtime_scopes_not_attested": sorted(set(unresolved)),
        "unscoped_runtime_scope_count": len(set(unresolved)),
        "all_source_families_accounted_for": (
            len(declared) == len(GROUPS) and not unresolved
        ),
        "all_independent_runtimes_retired_verified": False,
        "source_defined_identity_count_not_live_bots": len(PHP_ROLE_CODES) + len(DJANGO_ROLE_CODES),
        "identity_dispositions": identity_dispositions(cpanel),
        "verified_live_agents": None,
        "percent_fully_consolidated": None,
        "all_legacy_agents_retired": False,
        "production_cutover_authorized": False,
        "read_only": True,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vps", type=Path, required=True)
    parser.add_argument("--cpanel", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        now = datetime.now(timezone.utc)
        result = preview(
            parse_snapshot(args.vps, "vps", now=now),
            parse_snapshot(args.cpanel, "cpanel", now=now),
            json.loads(args.manifest.read_text(encoding="utf-8")),
            repository_root=Path(__file__).resolve().parents[1],
        )
    except (ValueError, TypeError, KeyError, OSError, json.JSONDecodeError) as exc:
        # A fixed error category avoids echoing raw host JSON or private paths.
        print("MOJTABA_DISPOSITION_PREVIEW=invalid_or_incomplete_evidence", file=sys.stderr)
        return 2
    print("MOJTABA_DISPOSITION_PREVIEW=" +
          json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
