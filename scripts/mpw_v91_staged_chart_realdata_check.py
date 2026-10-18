"""Read-only verification of staged MojPlayWin staff chart against REAL private V91 outputs.

No live Django import, no DB calls, no website/cron modification.
Uses a fresh, local-only Django Settings object solely for this check.
"""
from pathlib import Path
import importlib.util
import json
import sys

CANDIDATE=Path("/home/zomorod2/.private_mojplaywin_main_agents/management_release_candidate_20261018")
METRICS=CANDIDATE/"files/command_center/mpw_v91_agent_metrics.py"
STATE=Path("/home/zomorod2/.private_mojplaywin_main_agents/v91_verified_main_port_20261018/operator_state")
if not METRICS.is_file() or METRICS.is_symlink() or not STATE.is_dir() or STATE.is_symlink():
    raise SystemExit("UNTRUSTED_OR_MISSING_PRIVATE_STAFF_CANDIDATE")
from django.conf import settings
if not settings.configured:
    settings.configure(MPW_V91_PRIVATE_OPERATOR_STATE=str(STATE))
spec=importlib.util.spec_from_file_location("mpw_v91_panel_metric_probe",str(METRICS))
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
s=module.snapshot()
by={a["id"]:a for a in s["agents"]}
if not all(k in by for k in ("master_gen64","research_digest","product_blueprint")):
    raise SystemExit("MISSING_REQUIRED_MPW_AGENT")
summary={"kind":"MPW_V91_PRIVATE_STAFF_CHART_REALDATA_VERIFICATION",
         "state":s["state"],
         "master_agent_status":by["master_gen64"]["status"],
         "master_fake_history":by["master_gen64"]["history_available"],
         "research_digest_completed_14d":by["research_digest"]["completed"],
         "research_digest_queued":by["research_digest"]["queue"],
         "research_days":len(by["research_digest"]["days"]),
         "product_blueprint_completed_14d":by["product_blueprint"]["completed"],
         "product_blueprint_queued":by["product_blueprint"]["queue"],
         "product_days":len(by["product_blueprint"]["days"]),
         "invented_failures":s["historical_failures_measured"],
         "auto_publish":s["auto_publish"],
         "production_site_modified":False,
         "subsites_modified":False,
         "shared_django_imported":False}
print(json.dumps(summary,sort_keys=True))
if (s["state"]!="active_private"
    or by["research_digest"]["completed"]<1
    or by["product_blueprint"]["completed"]<1
    or len(by["research_digest"]["series"])!=14
    or len(by["product_blueprint"]["series"])!=14
    or s["auto_publish"] is not False):
    raise SystemExit("REALDATA_CHART_NOT_OPERATIONAL")
