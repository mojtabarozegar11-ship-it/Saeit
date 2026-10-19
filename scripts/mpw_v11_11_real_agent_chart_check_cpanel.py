"""Check actual historical metrics for all eleven recovered site agents on cPanel.

Only the private management release candidate and private agent history are read.
No project Django settings, DB access, site writes or cron modifications.
"""
from datetime import datetime,timezone
from pathlib import Path
import hashlib,importlib.util,json

ROOT=Path("/home/zomorod2/.private_mojplaywin_main_agents/management_release_v11_agents_20261018")
SCRIPT=ROOT/"files/command_center/mpw_v11_site_agent_charts.py"
HEALTH=Path("/home/zomorod2/.private_mojplaywin_main_agents/site_health_v11_port_20261018")
assert ROOT.is_dir() and not ROOT.is_symlink()
assert HEALTH.is_dir() and not HEALTH.is_symlink()
manifest=json.loads((ROOT/"MANIFEST.json").read_text(encoding="utf8"))
checks=manifest["sha256"]
assert len(checks)==13
for rel,digest in checks.items():
    p=ROOT/"files"/rel
    assert p.is_file() and not p.is_symlink()
    assert hashlib.sha256(p.read_bytes()).hexdigest()==digest
spec=importlib.util.spec_from_file_location("mpw_11_isolated_chart_readback",SCRIPT)
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
now=datetime.now(timezone.utc)
rows=mod.site_agent_chart_rows(now=now)
assert len(rows)==11 and len({r["id"] for r in rows})==11
assert all(len(r["days"])==14 and len(r["series"])==14 for r in rows)
actual=mod.AUDIT_AGENTS
assert {r["id"] for r in rows}=={"site_v11_"+a[0] for a in actual}
assert all(r["metric_kind"]=="site_health_checks" for r in rows)
verified=sum(1 for r in rows if r["completed"]>=1 and r["history_available"])
assert verified==11, "missing genuine cPanel monitoring records"
errors=sum(r["error_count"] for r in rows)
warnings=sum(r["warning_count"] for r in rows)
report={"status":"MPW_PRIVATE_11_SITE_AGENT_CHARTS_REAL_EVIDENCE_OK",
        "checked_utc":now.isoformat(),"agent_charts":len(rows),
        "real_data_agent_charts":verified,
        "current_agent_states":{r["id"]:r["status"] for r in rows},
        "total_successful_http_checks_14d":sum(r["completed"] for r in rows),
        "total_warnings_14d":warnings,"total_errors_14d":errors,
        "verified_admin_source_files":len(checks),
        "zomorod_files_modified":False,"mpw_public_site_modified":False,
        "shared_passenger_restarted":False,"factory_modified":False}
print(json.dumps(report,sort_keys=True))
