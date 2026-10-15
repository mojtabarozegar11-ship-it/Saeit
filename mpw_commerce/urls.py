"""Only isolated, separately gated buyer entitlement URLs.

Not included in the active production URLconf.
"""
from django.urls import path
from .downloads import download_paid_item
from .buyer_orders import create_digital_order
from .checkout_views import (
    checkout_challenge,checkout_verify_signature,
    checkout_invoice,checkout_status,
)

app_name="mpw_commerce"
urlpatterns=[
    path("commerce/checkout/order/",create_digital_order,name="order"),
    path("commerce/download/<int:item_id>/",download_paid_item,name="download"),
    path("commerce/checkout/challenge/",checkout_challenge,name="challenge"),
    path("commerce/checkout/verify/",checkout_verify_signature,name="verify"),
    path("commerce/checkout/invoice/",checkout_invoice,name="invoice"),
    path("commerce/checkout/status/<int:order_id>/",checkout_status,name="status"),
]
