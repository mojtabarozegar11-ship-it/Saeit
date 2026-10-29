"""Standalone same-origin identity URL patterns; no financial transfer endpoints."""
from django.http import JsonResponse
from django.urls import path
from banknew.identity_urls import urlpatterns as identity_urls


def health(_request):
    return JsonResponse({
        "service": "mojpay-identity",
        "status": "standby",
        "payments_enabled": False,
        "financial_kyc_verified": False,
    })


urlpatterns = [path("_health/", health, name="mojpay-health"), *identity_urls]
