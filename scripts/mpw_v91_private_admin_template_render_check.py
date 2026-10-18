"""Standalone real Django template render of private MojPlayWin admin candidate.

Reads staged manager template + verified private agent state; no production
Django settings, WSGI imports, DB connections, writes, external network or
unrelated tenant resources.
"""
import hashlib
import importlib.util
import json
import sys
import types
from pathlib import Path

ROOT=Path("/home/zomorod2/.private_mojplaywin_main_agents/management_release_candidate_20261018")
CODE=ROOT/"files"
OPERATOR=Path("/home/zomorod2/.private_mojplaywin_main_agents/v91_verified_main_port_20261018/operator_state")
if not ROOT.is_dir() or ROOT.is_symlink() or not OPERATOR.is_dir() or OPERATOR.is_symlink():
    raise SystemExit("PRIVATE_STAGE_MISSING")
manifest=json.loads((ROOT/"MANIFEST.json").read_text(encoding="utf-8"))
paths=manifest.get("sha256",{})
if len(paths)!=11:
    raise SystemExit("INVALID_PRIVATE_RELEASE_MANIFEST")
for rel,expected in paths.items():
    f=CODE/rel
    if not f.is_file() or f.is_symlink() or hashlib.sha256(f.read_bytes()).hexdigest()!=expected:
        raise SystemExit("PRIVATE_RELEASE_CONTENT_MISMATCH")

# Isolated in-memory Django config. No project settings or production models.
from django.conf import settings
url_module=types.ModuleType("mpw_agent_dashboard_isolated_urls")
from django.urls import path
url_module.urlpatterns=[
    path("staff/command-center/api/mojplaywin/v91/performance/",
         lambda request: None,name="mpw_private_v91_agent_performance")
]
sys.modules[url_module.__name__]=url_module
if settings.configured:
    raise SystemExit("UNEXPECTED_DJANGO_SETTINGS_LOADED")
settings.configure(
    SECRET_KEY="isolated-render-do-not-use-in-production",
    ROOT_URLCONF=url_module.__name__,
    MPW_V91_PRIVATE_OPERATOR_STATE=str(OPERATOR),
    INSTALLED_APPS=[],
    TEMPLATES=[{"BACKEND":"django.template.backends.django.DjangoTemplates",
                "DIRS":[str(CODE/"command_center/templates")],
                "APP_DIRS":False}],
)
from django.template import Engine, Context
engine=Engine(dirs=[str(CODE/"command_center/templates")],debug=False)
template=engine.get_template("command_center/mpw_v91_agent_performance.html")
rendered=template.render(Context({}))
requirements=(
    'id="mpw-v91-agent-settings"',
    'id="mpw-v91-agent-cards"',
    "drawChart(card,agent)",
    "/staff/command-center/api/mojplaywin/v91/performance/",
)
if not all(x in rendered for x in requirements):
    raise SystemExit("DASHBOARD_TEMPLATE_RENDER_MISSING_COMPONENTS")

metric_file=CODE/"command_center/mpw_v91_agent_metrics.py"
spec=importlib.util.spec_from_file_location("isolated_mpw_real_metrics",str(metric_file))
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
data=mod.snapshot()
agents={a["id"]:a for a in data["agents"]}
expected=("master_gen64","research_digest","product_blueprint")
if data["state"]!="active_private" or not all(x in agents for x in expected):
    raise SystemExit("AGENT_STAGED_DATA_NOT_READY")
for key in ("research_digest","product_blueprint"):
    if not isinstance(agents[key]["series"],list) or len(agents[key]["series"])!=14:
        raise SystemExit("INVALID_REAL_SERIES")
if agents["master_gen64"]["history_available"] or agents["master_gen64"]["series"] is not None:
    raise SystemExit("MASTER_HISTORY_NOT_PRESENT_MUST_NOT_BE_FAKED")

print(json.dumps({
    "status":"MPW_AGENT_ADMIN_DJANGO_TEMPLATE_REAL_RENDER_OK",
    "verified_candidate_source_files":len(paths),
    "django_rendered_template":True,
    "admin_component_and_js_found":True,
    "private_master_engine":agents["master_gen64"]["status"],
    "research_draft_count_14d":agents["research_digest"]["completed"],
    "product_draft_count_14d":agents["product_blueprint"]["completed"],
    "series_days":14,
    "master_history_not_fabricated":True,
    "public_site_updated":False,
    "protected_subsites_updated":False,
    "factory_touched":False,
    "shared_django_loaded":False,
    "passenger_restarted":False
},ensure_ascii=False,sort_keys=True))
