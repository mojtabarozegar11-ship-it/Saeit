"""Inventory ONLY Zomorod site's own Django Agent/Knowledge/Activity objects.

No changes, model saves, migrations or production scheduler; read-only queries.
"""
import json,os,sys
from pathlib import Path

root=Path("/home/zomorod2/Saeit")
out={"kind":"ZOMOROD_SITE_LOCAL_DJANGO_AGENT_DIFFERENCE",
    "scope":"zomorodmelal only, read-only",
    "production_site_changed":False,"factory_changed":False,
    "mpw_changed":False}
if not root.is_dir() or root.is_symlink() or not (root/"manage.py").is_file():
    out["status"]="SITE_SOURCE_MISSING"
else:
    try:
        os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings")
        os.environ["PYTHONDONTWRITEBYTECODE"]="1"
        sys.path.insert(0,str(root))
        import django
        django.setup()
        from core.models import Agent, AgentCapability, AgentTask
        rows=list(Agent.objects.order_by("code").values("code","name","active")[:200])
        out.update({
            "status":"OK",
            "registered_agents_total":Agent.objects.count(),
            "registered_agents_active_flags":Agent.objects.filter(active=True).count(),
            "registered_agents":rows,
            "capability_count":AgentCapability.objects.count(),
            "task_count":AgentTask.objects.count(),
            "role_counts_only_not_proof_of_execution":True
        })
        try:
            from core.knowledge_agent_models import KnowledgeAgentPlan
            out["knowledge_agent_plans"]=list(KnowledgeAgentPlan.objects.order_by("code").values(
                "code","active","cadence_hours","require_owner_approval")[:30])
        except Exception as ex:
            out["knowledge_agent_plans_status"]=type(ex).__name__
        try:
            from core.company_activity_models import CompanyActivityAgentPlan
            out["company_activity_agent_plans"]=list(CompanyActivityAgentPlan.objects.order_by("code").values(
                "code","active","cadence_hours","require_owner_approval")[:30])
        except Exception as ex:
            out["company_activity_plans_status"]=type(ex).__name__
    except Exception as exc:
        out["status"]="UNAVAILABLE"
        out["error_type"]=type(exc).__name__
print(json.dumps(out,ensure_ascii=False,sort_keys=True,default=str))
