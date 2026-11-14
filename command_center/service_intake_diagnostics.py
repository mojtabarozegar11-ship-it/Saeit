"""Owner-only, PII-free explanation of which company intake is authoritative.

Even all configuration flags saying "pass" cannot prove the actual live
Passenger, PHP, MariaDB, delivery or bank records. No external calls.
"""
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from core.service_intake_routing import service_intake_source_snapshot


@user_passes_test(
    lambda user: bool(user.is_active and user.is_superuser),
    login_url="/admin/login/",
)
@require_GET
def service_intake_diagnostics_api(request):
    response = JsonResponse(service_intake_source_snapshot())
    response["Cache-Control"] = "no-store, private, max-age=0"
    response["Pragma"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    response["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    response["Vary"] = "Cookie"
    return response
