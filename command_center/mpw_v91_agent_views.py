"""Staff-only MojPlayWin agent statistics; not a public site endpoint."""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET
from mpw_v91_port.runtime import valid_main_host
from .mpw_v91_agent_metrics import snapshot
from .mpw_v11_site_agent_charts import site_agent_chart_rows

@staff_member_required
@require_GET
def private_mpw_agent_metrics(request):
    if not valid_main_host(request.get_host()):
        raise Http404
    payload=snapshot()
    # Original Gen64/editorial metrics and recovered 11 V11 website monitors
    # remain tenant-isolated, but appear together only in the private panel.
    site_rows=site_agent_chart_rows()
    payload["agents"].extend(site_rows)
    payload["recovered_site_monitor_count"]=len(site_rows)
    if payload["state"]=="unavailable" and any(row["history_available"] for row in site_rows):
        payload["state"]="site_monitoring_only"
    answer=JsonResponse(payload)
    answer["Cache-Control"]="private, no-store, max-age=0"
    answer["X-Robots-Tag"]="noindex, nofollow, noarchive"
    return answer
