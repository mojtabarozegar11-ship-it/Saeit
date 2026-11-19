"""Explicit MojPlayWin route registry; underlying views retain release gates."""
from django.urls import path
from services import mpw_trx_commercial_web as commercial
from services import mpw_trx_public_pages as public
from services.mpw_trx_guest_commerce import patch_commercial, patch_public
from services.mpw_trx_email_recovery import (
    recovery_request, recovery_verify, recovery_orders, recovery_download,
)

patch_commercial(vars(commercial))
patch_public(vars(public))

urlpatterns = [
    path("commerce/trx-easy/", public.public_shop, name="mpw_trx_shop"),
    path("commerce/book/<int:product_id>/", public.product_checkout, name="mpw_trx_checkout"),
    path("commerce/trx-easy/purchases/", public.purchases, name="mpw_trx_purchases"),
    *[path(route, view) for route, view in commercial.COMMERCIAL_URLPATTERNS],
    path("commerce/trx-easy/recover/", recovery_request, name="mpw_trx_recovery"),
    path("commerce/trx-easy/recover/verify/", recovery_verify, name="mpw_trx_recovery_verify"),
    path("commerce/trx-easy/recover/orders/", recovery_orders, name="mpw_trx_recovery_orders"),
    path("commerce/trx-easy/recover/download/<int:invoice_id>/", recovery_download, name="mpw_trx_recovery_download"),
]
