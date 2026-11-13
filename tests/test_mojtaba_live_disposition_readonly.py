"""Host evidence is observation only; never a retirement grant or live proof."""
import importlib.util
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy/mojtaba_live_disposition_readonly.py"
spec = importlib.util.spec_from_file_location("disposition_preview", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
MANIFEST = json.loads((ROOT / "runtime/mojtaba_bot_disposition_sources_v1.json").read_text())


def snap(role, **overrides):
    base = {
        "schema": module.TOPOLOGY_SCHEMA, "host_role": role,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "expected_user_verified": True, "read_only": True,
        "cron": {"state": "observed", "entries": []},
        "processes": {"state": "observed", "route_match_counts": {}},
        "user_services": {"state": "observed", "candidate_units": []},
        "system_services": {"state": "observed", "candidate_units": []},
        "installed_source_digests": {},
        "private_php_site_registry": {"state": "private_database_not_observed"},
        "attestation": {"automatic_deactivation_authorized": False,
                        "handoff_verified": False},
    }
    base.update(overrides)
    return base


def save_snapshot(folder, role, data):
    path = folder / (role + ".jsonline")
    path.write_text("MOJTABA_LIVE_TOPOLOGY=" + json.dumps(data) + "\n", encoding="utf-8")
    return path


def test_no_evidence_never_yields_live_count_or_retirement_permission():
    report = module.preview(snap("vps"), snap("cpanel"), MANIFEST, repository_root=ROOT)
    assert report["sources_evaluated"] == 14
    assert report["verified_live_agents"] is None
    assert report["percent_fully_consolidated"] is None
    assert report["production_cutover_authorized"] is False
    for group in report["groups"]:
        assert group["retirement_authorized"] is False
        assert group["historical_records_can_be_deleted"] is False
        assert "no_accepted_task_delivery_receipts" in group["blocking_evidence"]


def test_cpanel_known_cron_and_system_service_are_indicators_not_operational_proof():
    cpanel = snap("cpanel")
    cpanel["cron"]["entries"] = [{
        "schedule": "0 * * * *",
        "known_route_flags": ["knowledge_agent_cycle"],
        "command_digest": "123456789abcdef0",
    }]
    cpanel["system_services"]["candidate_units"] = [{
        "known_route_flags": ["knowledge_agent_cycle"],
        "active": "active", "load": "loaded", "unit_name_digest": "1"*16,
    }]
    report = module.preview(snap("vps"), cpanel, MANIFEST, repository_root=ROOT)
    knowledge = next(x for x in report["groups"]
                     if x["source_group"] == "knowledge_content_director")
    observation = knowledge["host_observations"][0]
    assert observation["by_observation_surface"]["user_cron"] == 1
    assert observation["by_observation_surface"]["system_services_candidate"] == 1
    assert knowledge["status"] == "candidate_routes_seen_but_not_verified_live"
    assert knowledge["retirement_authorized"] is False
    assert "no_proven_complete_external_scheduler_census" in knowledge["blocking_evidence"]


def test_untrusted_unknown_cron_route_is_not_redistributed_or_printed():
    secret = "SECRET_UNLISTED_ROUTE"
    cpanel = snap("cpanel")
    cpanel["cron"]["entries"] = [
        {"known_route_flags": [secret], "command_digest": secret}
    ]
    out = json.dumps(module.preview(
        snap("vps"), cpanel, MANIFEST, repository_root=ROOT
    ))
    assert secret not in out


def test_legacy_site_php_registry_enumerates_records_without_claiming_workers():
    cpanel = snap("cpanel", private_php_site_registry={
        "state": "source_registry_snapshot_only",
        "known_roles_found": 11, "enabled_count": 10,
        "run_status_counts": {"ok": 23},
    })
    report = module.preview(snap("vps"), cpanel, MANIFEST, repository_root=ROOT)
    row = next(g for g in report["groups"]
               if g["source_group"] == "zomorod_php_site_agent_runtime")
    obs = row["host_observations"][0]
    assert obs["php_known_roles_found"] == 11
    assert obs["php_enabled_records_not_active_bots"] == 10
    assert row["retirement_authorized"] is False
    assert report["verified_live_agents"] is None


def test_unavailable_php_private_registry_is_not_zero():
    report = module.preview(snap("vps"), snap("cpanel"),
                            MANIFEST, repository_root=ROOT)
    row = next(g for g in report["groups"]
               if g["source_group"] == "zomorod_php_site_agent_runtime")
    assert "private_php_sqlite_snapshot_unavailable" in row["blocking_evidence"]
    assert "php_known_roles_found" not in row["host_observations"][0]


def test_installed_revision_mismatch_blocks_handoff():
    cpanel = snap("cpanel")
    cpanel["installed_source_digests"] = {
        "weather_agent.py": {
            "state": "file_observed_not_runtime_executed",
            "sha256": "0" * 64,
        }
    }
    result = module.preview(snap("vps"), cpanel, MANIFEST, repository_root=ROOT)
    weather = next(x for x in result["groups"]
                   if x["source_group"] == "weather_publication_module")
    assert weather["host_observations"][0]["source_revisions"] == {
        "weather_agent.py": "drift_or_mismatch"
    }
    assert "installed_source_revision_differs_from_reviewed_pr" in weather["blocking_evidence"]


def test_known_source_hash_match_does_not_claim_agent_running():
    cpanel = snap("cpanel")
    file = ROOT / "core/weather_agent.py"
    import hashlib
    cpanel["installed_source_digests"] = {
        "weather_agent.py": {"state": "file_observed_not_runtime_executed",
                             "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
    }
    r = module.preview(snap("vps"), cpanel, MANIFEST, repository_root=ROOT)
    weather = next(x for x in r["groups"]
                   if x["source_group"] == "weather_publication_module")
    assert weather["host_observations"][0]["source_revisions"]["weather_agent.py"] == "matches_reviewed_source"
    assert weather["retirement_authorized"] is False


@pytest.mark.parametrize("mutation", [
    {"host_role": "cpanel"},
    {"read_only": False},
    {"expected_user_verified": False},
    {"attestation": {"automatic_deactivation_authorized": True}},
])
def test_mismatched_host_identity_or_writeable_snapshot_is_rejected(tmp_path, mutation):
    data = snap("vps", **mutation)
    path = save_snapshot(tmp_path, "vps", data)
    with pytest.raises(ValueError, match="TOPOLOGY_IDENTITY_OR_READONLY_INVALID"):
        module.parse_snapshot(path, "vps", now=datetime.now(timezone.utc))


def test_stale_snapshot_is_not_accepted_as_live_evidence(tmp_path):
    old = (datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
    path = save_snapshot(tmp_path, "vps", snap("vps", captured_at_utc=old))
    with pytest.raises(ValueError, match="TOPOLOGY_STALE_OR_FUTURE"):
        module.parse_snapshot(path, "vps", now=datetime.now(timezone.utc))


def test_negative_or_boolean_counts_do_not_enter_report():
    cpanel = snap("cpanel", private_php_site_registry={
        "state": "source_registry_snapshot_only",
        "known_roles_found": True, "enabled_count": -1,
    })
    with pytest.raises(ValueError, match="TOPOLOGY_COUNT_INVALID"):
        module.preview(snap("vps"), cpanel, MANIFEST, repository_root=ROOT)


def test_cli_generates_safe_per_source_preview_from_two_fake_host_snapshots(tmp_path):
    vps = save_snapshot(tmp_path, "vps", snap("vps"))
    cpanel = save_snapshot(tmp_path, "cpanel", snap("cpanel"))
    cmd = [
        sys.executable, str(SCRIPT),
        "--vps", str(vps), "--cpanel", str(cpanel),
        "--manifest", str(ROOT / "runtime/mojtaba_bot_disposition_sources_v1.json"),
    ]
    res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert res.returncode == 0, res.stderr
    assert res.stdout.startswith("MOJTABA_DISPOSITION_PREVIEW=")
    report = json.loads(res.stdout.split("=", 1)[1])
    assert report["sources_evaluated"] == 14
    assert report["verified_live_agents"] is None


def test_cli_fails_closed_on_missing_snapshot(tmp_path):
    cpanel = save_snapshot(tmp_path, "cpanel", snap("cpanel"))
    proc = subprocess.run([
        sys.executable, str(SCRIPT),
        "--vps", str(tmp_path / "missing.jsonline"), "--cpanel", str(cpanel),
        "--manifest", str(ROOT / "runtime/mojtaba_bot_disposition_sources_v1.json"),
    ], cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert proc.returncode == 2
    assert "MOJTABA_DISPOSITION_PREVIEW=invalid_or_incomplete_evidence" in proc.stderr
    assert "missing.jsonline" not in proc.stderr


def test_unavailable_surfaces_cannot_supply_fake_route_activity():
    cpanel = snap("cpanel")
    cpanel["cron"] = {
        "state": "unavailable", "entries": [{
            "known_route_flags": ["knowledge_agent_cycle"],
        }]
    }
    cpanel["processes"] = {
        "state": "unavailable",
        "route_match_counts": {"knowledge_agent_cycle": 999},
    }
    cpanel["user_services"] = {
        "state": "unavailable",
        "candidate_units": [{"known_route_flags": ["knowledge_agent_cycle"]}],
    }
    cpanel["system_services"] = {
        "state": "unavailable",
        "candidate_units": [{"known_route_flags": ["knowledge_agent_cycle"]}],
    }
    report = module.preview(snap("vps"), cpanel, MANIFEST, repository_root=ROOT)
    knowledge = next(g for g in report["groups"]
                     if g["source_group"] == "knowledge_content_director")
    obs = knowledge["host_observations"][0]
    assert obs["route_indicators_total_not_unique_workers"] == 0
    assert knowledge["status"] == "runtime_unverified_no_known_route_indicators"
    assert "partial_host_topology_observation" in knowledge["blocking_evidence"]
    assert knowledge["retirement_authorized"] is False


@pytest.mark.parametrize("field", [
    "cron", "processes", "user_services", "system_services",
    "installed_source_digests", "private_php_site_registry", "attestation",
])
def test_malformed_snapshot_structures_fail_before_disposition(tmp_path, field):
    data = snap("vps")
    data[field] = ["not-a-mapping"]
    path = save_snapshot(tmp_path, "vps", data)
    with pytest.raises(ValueError, match="TOPOLOGY_SHAPE_INVALID"):
        module.parse_snapshot(path, "vps", now=datetime.now(timezone.utc))


def test_every_source_defined_identity_has_explicit_status_without_live_claim():
    report = module.preview(snap("vps"), snap("cpanel"),
                            MANIFEST, repository_root=ROOT)
    identities = report["identity_dispositions"]
    assert report["source_defined_identity_count_not_live_bots"] == 21
    assert len(identities) == 21
    assert len({(x["source"], x["code"]) for x in identities}) == 21
    assert all(x["retirement_authorized"] is False for x in identities)
    assert all(x["live_execution_verified"] is False for x in identities)
    assert all(x["registration_state"].startswith("unknown_") for x in identities)


def test_cpanel_private_registry_yields_per_role_records_not_false_active_bots():
    php = {
        "state": "source_registry_snapshot_only",
        "agent_roles": [
            {"code": "master", "enabled": True},
            {"code": "weather", "enabled": False},
            {"code": "PRIVATE_EXTERNAL_SECRET", "enabled": True},
        ],
        "known_roles_found": 2, "enabled_count": 2,
    }
    report = module.preview(
        snap("vps"), snap("cpanel", private_php_site_registry=php),
        MANIFEST, repository_root=ROOT,
    )
    roles = {r["code"]: r for r in report["identity_dispositions"]}
    assert roles["master"]["registration_state"] == "enabled_database_record_not_live_worker"
    assert roles["weather"]["registration_state"] == "disabled_database_record_not_retirement_proof"
    assert roles["seo"]["registration_state"] == "not_in_observed_private_registry"
    assert roles["mojtaba-bot-ai"]["registration_state"] == "unknown_django_database_not_observed"
    assert "PRIVATE_EXTERNAL_SECRET" not in json.dumps(report)
    assert roles["weather"]["retirement_authorized"] is False


def test_php_disabled_record_cannot_justify_deactivating_live_scheduler():
    php = {
        "state": "source_registry_snapshot_only",
        "agent_roles": [{"code": "research", "enabled": False}],
        "known_roles_found": 1, "enabled_count": 0,
    }
    cpanel = snap("cpanel", private_php_site_registry=php)
    cpanel["processes"]["route_match_counts"] = {"site_agent_workforce.php": 1}
    report = module.preview(snap("vps"), cpanel, MANIFEST, repository_root=ROOT)
    identity = next(i for i in report["identity_dispositions"]
                    if i["source"] == "cpanel_php_sqlite" and i["code"] == "research")
    assert identity["registration_state"] == "disabled_database_record_not_retirement_proof"
    assert identity["retirement_authorized"] is False
    assert report["verified_live_agents"] is None


def test_non_boolean_site_enabled_value_is_not_accepted_as_valid_record():
    php = {
        "state": "source_registry_snapshot_only",
        "agent_roles": [{"code": "master", "enabled": 1}],
        "known_roles_found": 1, "enabled_count": 1,
    }
    identities = module.identity_dispositions(
        snap("cpanel", private_php_site_registry=php)
    )
    assert identities[0]["registration_state"] == "not_in_observed_private_registry"


def test_source_groups_cover_trading_coin_cycles_and_off_host_runtimes():
    report = module.preview(snap("vps"), snap("cpanel"), MANIFEST, repository_root=ROOT)
    groups = {g["source_group"]: g for g in report["groups"]}
    assert report["sources_evaluated"] == 14
    assert report["sources_in_manifest"] == 14
    assert report["unscoped_runtime_scope_count"] == 6
    assert report["all_source_families_accounted_for"] is False
    assert report["all_independent_runtimes_retired_verified"] is False
    for group in (
        "mojtrade_signal_and_broker_runtime",
        "moj_coin_game_token_workers",
        "canonical_cycle_and_legacy_master_schedulers",
    ):
        assert len(groups[group]["host_observations"]) == 2
        assert groups[group]["retirement_authorized"] is False
    for group in (
        "mobile_sms_termux_automate_runtime",
        "external_connected_app_agents",
    ):
        assert groups[group]["host_observations"] == []
        assert "external_runtime_outside_vps_cpanel_observation" in groups[group]["blocking_evidence"]
        assert groups[group]["retirement_authorized"] is False


def test_previously_unclassified_trading_and_game_routes_are_observable_not_attested():
    vps = snap("vps")
    vps["cron"]["entries"] = [
        {"known_route_flags": ["mojtrade_observer"]},
        {"known_route_flags": ["mojcoin"]},
        {"known_route_flags": ["autonomous_master_loop"]},
    ]
    report = module.preview(vps, snap("cpanel"), MANIFEST, repository_root=ROOT)
    groups = {g["source_group"]: g for g in report["groups"]}
    for group in (
        "mojtrade_signal_and_broker_runtime",
        "moj_coin_game_token_workers",
        "canonical_cycle_and_legacy_master_schedulers",
    ):
        item = groups[group]
        assert item["status"] == "candidate_routes_seen_but_not_verified_live"
        assert item["host_observations"][0]["by_observation_surface"]["user_cron"] == 1
        assert "no_proven_complete_external_scheduler_census" in item["blocking_evidence"]
        assert item["retirement_authorized"] is False
    assert report["verified_live_agents"] is None


@pytest.mark.parametrize("invalidity", ["unknown", "duplicate", "malformed"])
def test_manifest_does_not_silently_drop_or_duplicate_untracked_sources(invalidity):
    altered = json.loads(json.dumps(MANIFEST))
    if invalidity == "unknown":
        altered["sources"].append({"id": "unknown_unreviewed_agent_root"})
    elif invalidity == "duplicate":
        altered["sources"].append(dict(altered["sources"][0]))
    else:
        altered["sources"].append({"name": "missing_source_id"})
    with pytest.raises(ValueError, match="DISPOSITION_MANIFEST_"):
        module.preview(snap("vps"), snap("cpanel"), altered, repository_root=ROOT)


def test_missing_manifest_group_is_explicit_blocker_not_completion():
    altered = json.loads(json.dumps(MANIFEST))
    altered["sources"] = [
        x for x in altered["sources"]
        if x["id"] != "moj_coin_game_token_workers"
    ]
    report = module.preview(snap("vps"), snap("cpanel"), altered, repository_root=ROOT)
    coin = next(
        x for x in report["groups"]
        if x["source_group"] == "moj_coin_game_token_workers"
    )
    assert "group_missing_from_checked_in_manifest" in coin["blocking_evidence"]
    assert report["sources_in_manifest"] == 13
    assert report["all_source_families_accounted_for"] is False
    assert report["production_cutover_authorized"] is False


def test_untracked_external_scope_does_not_disappear_from_completion_report():
    report = module.preview(snap("vps"), snap("cpanel"), MANIFEST, repository_root=ROOT)
    assert "mobile_Termux_Automate_SMS_device_schedulers" in report["unscoped_runtime_scopes_not_attested"]
    assert "external_automation_and_connected_app_agents" in report["unscoped_runtime_scopes_not_attested"]
    assert "broker_remote_accounts_and_marketplace_webhooks" in report["unscoped_runtime_scopes_not_attested"]
    assert report["percent_fully_consolidated"] is None



def test_report_percentages_measure_source_registry_not_live_cleanup():
    report = module.preview(snap("vps"), snap("cpanel"), MANIFEST, repository_root=ROOT)
    p = report["evidence_progress"]
    assert p["known_source_group_registration"] == {
        "registered": 14,
        "expected_known_source_groups": 14,
        "percent": 100.0,
        "scope": "checked_in_known_groups_only_not_a_complete_live_bot_census",
    }
    assert p["verified_live_retirement"]["groups_with_verified_handoff_and_retirement"] == 0
    assert p["verified_live_retirement"]["proof_coverage_percent"] == 0.0
    assert p["overall_operational_completion_percent"] is None
    assert report["percent_fully_consolidated"] is None
    assert report["all_legacy_agents_retired"] is False


def test_missing_source_group_reduces_only_registration_coverage():
    altered = json.loads(json.dumps(MANIFEST))
    altered["sources"] = [
        x for x in altered["sources"]
        if x["id"] != "external_connected_app_agents"
    ]
    report = module.preview(snap("vps"), snap("cpanel"), altered, repository_root=ROOT)
    progress = report["evidence_progress"]
    assert progress["known_source_group_registration"]["registered"] == 13
    assert progress["known_source_group_registration"]["expected_known_source_groups"] == 14
    assert progress["known_source_group_registration"]["percent"] == 92.9
    assert progress["overall_operational_completion_percent"] is None
    assert report["production_cutover_authorized"] is False


@pytest.mark.parametrize("layer,blocker", [
    ("cron", "host_cron_inventory_truncated"),
    ("processes", "host_process_inventory_truncated"),
])
def test_truncated_host_inventory_blocks_source_disposition(layer, blocker):
    vps = snap("vps")
    vps[layer]["enumeration_truncated"] = True
    vps[layer]["state"] = "observed"
    report = module.preview(vps, snap("cpanel"), MANIFEST, repository_root=ROOT)
    canonical = next(x for x in report["groups"]
                     if x["source_group"] == "canonical_cycle_and_legacy_master_schedulers")
    assert blocker in canonical["blocking_evidence"]
    assert canonical["retirement_authorized"] is False
    assert report["evidence_progress"]["overall_operational_completion_percent"] is None
