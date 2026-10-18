"""Staff-only MojPlayWin agent statistics; not a public site endpoint."""
from django.contrib.admin.views.decorators import staff_member_required
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET
from mpw_v91_port.runtime import valid_main_host
from .mpw_v91_agent_metrics import snapshot

@staff_member_required
@require_GET
def private_mpw_agent_metrics(request):
    if not valid_main_host(request.get_host()):
        raise Http404
    answer=JsonResponse(snapshot())
    answer["Cache-Control"]="private, no-store, max-age=0"
    answer["X-Robots-Tag"]="noindex, nofollow, noarchive"
    return answer
