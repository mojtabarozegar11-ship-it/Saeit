from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.views.decorators.http import require_GET
from .integrated_ledger_api import integrated_ledger_api

@staff_member_required
@require_GET
def integrated_dashboard(request):
    response = render(request, "command_center/integrated_dashboard.html")
    response["Cache-Control"] = "no-store"
    return response
