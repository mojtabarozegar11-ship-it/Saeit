"""Only isolated, separately gated buyer entitlement URLs.

Not included in the active production URLconf.
"""
from django.urls import path
from .downloads import download_paid_item

app_name="mpw_commerce"
urlpatterns=[
    path("commerce/download/<int:item_id>/",download_paid_item,name="download"),
]
