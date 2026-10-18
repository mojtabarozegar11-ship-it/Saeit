"""Fail-closed, read-only on-host status of requested MojPlayWin staff agent charts.

No DB, secrets, protected subsite content, process or web application imports.
No writes, restart, or route changes.
"""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,stat

SITE=Path("/home/zomorod2/mojplaywin.com")
SHARED=Path("/home/zomorod2/Saeit-staging")
PRIVATE=Path("/home/zomorod2/.private_mojplaywin_main_agents/v91_verified_main_port_20261018")
def file_read(path, needle=None):
    if not path.is_file() or path.is_symlink():
        return {"exists":False,"feature_present":False}
    size=path.stat().st_size
    if size>400000: return {"exists":True,"feature_present":False,"oversized":True}
    content=path.read_text(encoding="utf8",errors="replace")
    return {"exists":True,"feature_present":bool(needle in content) if needle else None,
            "sha256_12":hashlib.sha256(content.encode("utf8")).hexdigest()[:12]}
files={
 "staff_dashboard_template":(SHARED/"command_center/templates/command_center/dashboard.html","mpw_v91_agent_performance.html"),
 "staff_metrics_api":(SHARED/"command_center/mpw_v91_agent_views.py","private_mpw_agent_metrics"),
 "staff_chart_template":(SHARED/"command_center/templates/command_center/mpw_v91_agent_performance.html","drawChart"),
 "admin_agent_settings":(SHARED/"core/admin.py","MojPlayWinAwareAgentAdmin"),
 "admin_v91_chart":(SHARED/"core/templates/admin/core/agent/mpw_v91_performance.html","mpw_v91_agent_performance.html"),
 "staff_routes":(SHARED/"command_center/urls.py","mpw_private_v91_agent_performance"),
 "private_master_worker":(PRIVATE/"mpw_v91_port/worker.py","def tick("),
}
status={
 "classification":"MOJPLAYWIN_AGENT_PANEL_RELEASE_GATE_20261018",
 "site_root_present":SITE.is_dir() and not SITE.is_symlink(),
 "shared_django_present":SHARED.is_dir() and not SHARED.is_symlink(),
 "private_stage_present":PRIVATE.is_dir() and not PRIVATE.is_symlink(),
 "files":{key:file_read(path,needle) for key,(path,needle) in files.items()},
 "do_not_restart_shared_passenger":True,
 "public_subsites_modified":False,
 "live_management_ui_confirmed":False,
 "production_release_gate":"fail_closed",
}
if all(status["files"][k]["feature_present"] for k in (
    "staff_dashboard_template","staff_metrics_api","staff_chart_template",
    "admin_agent_settings","admin_v91_chart","staff_routes")):
    status["live_management_ui_source_files_present"]=True
else:
    status["live_management_ui_source_files_present"]=False
print(json.dumps(status,ensure_ascii=False,sort_keys=True))
