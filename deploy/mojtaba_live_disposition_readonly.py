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
        "installed_source_digests", "private_php_site_registry", "attestation",
    )
    if any(not isinstance(item.get(name), dict) for name in required_maps):
        raise ValueError("TOPOLOGY_SHAPE_INVALID")
    if (item.get("host_role") != expected_role or
            item.get("read_only") is not True or
            item.get("expected_user_verified") is not True or
            item["attestation"].get("automatic_deactivation_authorized") is not False):
        raise ValueError("TOPOLOGY_IDENTITY_OR_READONLY_INVALID")
    when = datetime.fromisoformat(item["captured_at_utc"].replace("Z", "+00:00"))
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
        for row in cron.get("entries", []):
            for tag in set(row.get("known_route_flags", [])):
                if tag in allowed:
                    hit_counts[("user_cron", tag)] += 1
    processes = snapshot.get("processes", {})
    if processes.get("state") == "observed":
        for tag, n in processes.get("route_match_counts", {}).items():
            if tag in allowed:
                hit_counts[("process_argv_indicator", tag)] += trusted_count(n)
    for layer in ("user_services", "system_services"):
        status = snapshot.get(layer, {})
        if status.get("state") != "observed":
            continue
        for unit in status.get("candidate_units", []):
            for tag in set(unit.get("known_route_flags", [])):
                if tag in allowed:
                    hit_counts[(layer + "_candidate", tag)] += 1
    return {
        "by_observation_surface": {
            surface: int(sum(v for (s, _), v in hit_counts.items() if s == surface))
            for surface in ("user_cron", "process_argv_indicator",
                            "user_services_candidate", "system_services_candidate")
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


def preview(vps: dict, cpanel: dict, manifest: dict, *, repository_root: Path) -> dict:
    if manifest.get("schema") != MANIFEST_SCHEMA or manifest.get("canonical_bot_id") != "mojtaba.bot.ai":
        raise ValueError("DISPOSITION_MANIFEST_INVALID")
    declared = {x["id"] for x in manifest["sources"] if isinstance(x, dict) and x.get("id") in GROUPS}
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
                "source_revisions": source_revision(snap, policy["files"], repository_root),
                **route_hits(snap, policy["routes"]),
            }
            if host == "cpanel" and group_id == "zomorod_php_site_agent_runtime":
                php = snap.get("private_php_site_registry", {})
                obs["php_registry_state"] = php.get("state", "unknown")
                if php.get("state") == "source_registry_snapshot_only":
                    obs["php_known_roles_found"] = trusted_count(php.get("known_roles_found"))
                    obs["php_enabled_records_not_active_bots"] = trusted_count(php.get("enabled_count"))
                else:
                    blockers.append("private_php_sqlite_snapshot_unavailable")
            if any(obs[k] != "observed" for k in
                   ("cron_read", "process_read", "user_services_read", "system_services_read")):
                blockers.append("partial_host_topology_observation")
            if any(v == "drift_or_mismatch" for v in obs["source_revisions"].values()):
                blockers.append("installed_source_revision_differs_from_reviewed_pr")
            if any(v == "unknown" for v in obs["source_revisions"].values()):
                blockers.append("installed_source_revision_unknown")
            observed.append(obs)
        if group_id not in declared:
            blockers.append("group_missing_from_checked_in_manifest")
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
    return {
        "schema": SCHEMA, "canonical_bot": "mojtaba.bot.ai",
        "sources_in_manifest": len(declared),
        "sources_evaluated": len(groups), "groups": groups,
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
