"""Read-only inventory of registered Agent rows on shared MojPlayWin Django.

This answers how many were defined as agents vs how many are running in the
separate, confirmed private Gen64 worker. No updates, migrations, cron changes.
"""
import json,os,sys
from pathlib import Path
SITE=Path("/home/zomorod2/Saeit-staging")
result={"kind":"MOJPLAYWIN_REGISTERED_AGENT_SOURCE_INVENTORY_READONLY",
        "site":"mojplaywin-main-shared-Django","source_root_exists":SITE.is_dir(),
        "database_modified":False,"cron_modified":False,
        "factory_modified":False,"other_sites_modified":False}
if not SITE.is_dir() or SITE.is_symlink() or not (SITE/"config"/"settings.py").is_file():
    print(json.dumps({**result,"status":"DJANGO_SITE_NOT_FOUND"}));raise SystemExit(0)
sys.path.insert(0,str(SITE))
os.environ["DJANGO_SETTINGS_MODULE"]="config.settings"
os.environ["PYTHONDONTWRITEBYTECODE"]="1"
try:
    import django
    django.setup()
    from django.db import connections
    from core.models import Agent,AgentCapability,AgentTask
    connection=connections["default"]
    # Assert read-only mode for sqlite; other backends run only SELECT ORM calls.
    if connection.vendor=="sqlite":
        with connection.cursor() as c:
            c.execute("PRAGMA query_only = ON")
    registered=list(Agent.objects.order_by("code").values("code","name","active")[:250])
    result.update({
        "status":"OK",
        "scope_note":"Shared Django Agent model rows; not automatically equal to running MojPlayWin worker roles",
        "database_engine":connection.vendor,
        "agent_rows_total":Agent.objects.count(),
        "agent_rows_enabled_flag":Agent.objects.filter(active=True).count(),
        "agent_rows_disabled_flag":Agent.objects.filter(active=False).count(),
        "agent_capability_rows":AgentCapability.objects.count(),
        "agent_capability_active_rows":AgentCapability.objects.filter(active=True).count(),
        "agent_task_rows":AgentTask.objects.count(),
        "agent_codes":[{"code":r["code"],"name":r["name"][:90],"db_enabled":r["active"]} for r in registered],
        "truncated":Agent.objects.count()>250
    })
except Exception as exc:
    result["status"]="UNAVAILABLE"
    result["error_type"]=type(exc).__name__
print(json.dumps(result,ensure_ascii=False,sort_keys=True))
