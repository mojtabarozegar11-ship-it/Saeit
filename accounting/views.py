from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from .services import ledger_summary


@staff_member_required
@require_GET
def dashboard(request):
    response = render(request, "accounting/dashboard.html")
    response["Cache-Control"] = "private, no-store, max-age=0"
    return response


@staff_member_required
@require_GET
def summary_api(request):
    response = JsonResponse(ledger_summary())
    response["Cache-Control"] = "private, no-store, max-age=0"
    return response
