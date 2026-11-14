"""Single URL namespace for every explicitly mounted FA/EN merchant host."""
from django.urls import path
from . import tron_gateway_web as views
from .tron_gateway_delivery import download_paid

urlpatterns = [
    path("", views.catalog, name="tron_gateway_catalog"),
    path("product/<int:product_id>/", views.checkout, name="tron_gateway_checkout"),
    path("email/<str:token>/", views.email_claim, name="tron_gateway_email_confirm"),
    path("invoice/<int:invoice_id>/", views.invoice_page, name="tron_gateway_invoice"),
    path("download/<int:invoice_id>/", download_paid, name="tron_gateway_download"),
    path("recover/", views.recovery, name="tron_gateway_recovery"),
    path("recovery/<str:token>/", views.recovery_link, name="tron_gateway_recovery_confirm"),
]
