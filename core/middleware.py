import uuid
from .models import AuditLog
class RequestAuditMiddleware:
 def __init__(self,get_response): self.get_response=get_response
 def __call__(self,request):
  trace=str(uuid.uuid4()); request.trace_id=trace; response=self.get_response(request)
  if getattr(request,"user",None) and request.user.is_authenticated: AuditLog.objects.create(actor_type="user",actor_id=str(request.user.pk),action=f"{request.method} {request.path}",trace_id=trace)
  return response
