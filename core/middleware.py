import logging
import uuid

from .models import AuditLog

logger = logging.getLogger(__name__)


class RequestAuditMiddleware:
    """Attach a trace ID and audit authenticated API/web requests without breaking them."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        trace_id = str(uuid.uuid4())
        request.trace_id = trace_id
        response = self.get_response(request)

        # A public catalog explicitly marked unavailable must not trigger an
        # additional audit DB write on a read-only GET/HEAD during schema loss.
        # Preserve auditing for all other responses, especially mutations.
        if (request.method in ("GET", "HEAD")
                and getattr(response, "status_code", None) == 503
                and response.get("X-ZM-Data-Status") == "temporarily-unavailable"):
            return response

        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            try:
                AuditLog.objects.create(
                    actor_type="user",
                    actor_id=str(user.pk),
                    action=f"{request.method} {request.path}",
                    target_type="HTTP",
                    target_id=str(getattr(response, "status_code", "")),
                    after_state={"status_code": response.status_code},
                    trace_id=trace_id,
                )
            except Exception:
                # Auditing must not turn a successful application response into a 500.
                logger.exception("Request audit write failed", extra={"trace_id": trace_id})
        return response
