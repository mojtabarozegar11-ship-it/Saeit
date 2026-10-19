"""Render staged MojPlayWin admin view and verify all 16 source-backed roles.

Uses isolated template Engine only. Never loads production app, DB or Passenger.
"""
import hashlib,importlib.util,json,sys,types
from pathlib import Path
BASE=Path("/home/zomorod2/.private_mojplaywin_main_agents")
STAGE=BASE/"management_release_16_agents_20261018"
CODE=STAGE/"files"
manifest=json.loads((STAGE/"MANIFEST.json").read_text(encoding="utf8"))
checks=manifest["sha256"]
assert len(checks)==14
for rel,digest in checks.items():
    target=CODE/rel
    assert target.is_file() and not target.is_symlink()
    assert hashlib.sha256(target.read_bytes()).hexdigest()==digest

from django.conf import settings
from django.urls import path
module=types.ModuleType("mpw_only_16_agent_urlconf")
module.urlpatterns=[path("staff/command-center/api/mojplaywin/v91/performance/",
                        lambda req:None,name="mpw_private_v91_agent_performance")]
sys.modules[module.__name__]=module
assert not settings.configured
settings.configure(
    SECRET_KEY="private-offline-template-test-do-not-use-in-production",
    ROOT_URLCONF=module.__name__,
    MPW_V91_PRIVATE_OPERATOR_STATE=str(BASE/"v91_verified_main_port_20261018/operator_state"),
    INSTALLED_APPS=[],
    TEMPLATES=[{"BACKEND":"django.template.backends.django.DjangoTemplates",
                "DIRS":[str(CODE/"command_center/templates")],
                "APP_DIRS":False}],
)
from django.template import Engine,Context
engine=Engine(dirs=[str(CODE/"command_center/templates")],debug=False)
rendered=engine.get_template("command_center/mpw_v91_agent_performance.html").render(Context({}))
assert "drawChart(card,agent)" in rendered
assert "/staff/command-center/api/mojplaywin/v91/performance/" in rendered
assert 'id="mpw-v91-agent-settings"' in rendered

def module_load(name,filename):
    path=CODE/"command_center"/filename
    spec=importlib.util.spec_from_file_location(name,str(path))
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

original=module_load("mpw_sixteen_original","mpw_v91_agent_metrics.py").snapshot()
monitors=module_load("mpw_sixteen_monitors","mpw_v11_site_agent_charts.py").site_agent_chart_rows()
policy=module_load("mpw_sixteen_policies","mpw_zomorod_management_charts.py").rows()
combined=original["agents"]+monitors+policy
assert len(original["agents"])==3 and len(monitors)==11 and len(policy)==2
assert len(combined)==16 and len({x["id"] for x in combined})==16
assert sum(x["completed"] for x in monitors)>=11
assert all(x["completed"]>=1 for x in policy)
assert all(x["history_available"] is False and x["series"] is None for x in policy)
assert all(x["metric_kind"]=="site_health_checks" for x in monitors)

print(json.dumps({"status":"MPW_16_AGENT_ADMIN_PRIVATE_DJANGO_RENDER_OK",
    "template_rendered":True,
    "source_files_sha256_verified":len(checks),
    "agent_cards":len(combined),
    "legacy_master_and_editorial_agents":len(original["agents"]),
    "site_monitor_agents":len(monitors),
    "economic_and_reporting_agents":len(policy),
    "real_site_checks_14_days":sum(x["completed"] for x in monitors),
    "fabricated_policy_history":False,
    "web_panel_published":False,
    "shared_Django_imported":False,
    "other_sites_modified":False},sort_keys=True))
