"""Isolated CI-only URLconf. Live site routing remains untouched."""
from django.urls import include, path

urlpatterns = [
    path("_ci_wallet/", include("mpw_native_checkout.merchant_wallet_urls")),
    path("_ci_commerce/", include("mpw_commerce.urls")),
]
