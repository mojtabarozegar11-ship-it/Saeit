from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import ensure_csrf_cookie

@staff_member_required
@require_GET
@ensure_csrf_cookie
def integrated_dashboard(request):
    response = render(request, "command_center/integrated_dashboard.html")
    response["Cache-Control"] = "no-store"
    return response
