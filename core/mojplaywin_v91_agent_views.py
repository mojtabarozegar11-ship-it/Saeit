"""Private MojPlayWin main-site research preview; never a public bot endpoint."""
import json

from django.conf import settings
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect

from mpw_v91_port.runtime import (
    MojPlayWinAgentInputError, review_draft, valid_main_host,
)

@require_POST
@csrf_protect
def mojplaywin_v91_agent_preview(request):
    # Shared Django services may host many unrelated sub-sites. Host and flag
    # checks precede authentication, payload parsing and any V91 import.
    if not valid_main_host(request.get_host()):
        raise Http404
    if not getattr(settings, "MOJPLAYWIN_V91_AGENT_REVIEW_ENABLED", False):
        raise Http404
    if not getattr(request.user, "is_authenticated", False) or not getattr(request.user, "is_staff", False):
        return HttpResponseForbidden("Staff access required")
    if len(request.body)>65536:
        return JsonResponse({"error":"payload_too_large"},status=413)
    try:
        payload=json.loads(request.body)
        answer=review_draft(payload)
    except (json.JSONDecodeError,UnicodeError):
        return JsonResponse({"error":"invalid_json"},status=400)
    except MojPlayWinAgentInputError:
        return JsonResponse({"error":"invalid_agent_request"},status=400)
    return JsonResponse({"status":"private_review_only","draft":answer})
