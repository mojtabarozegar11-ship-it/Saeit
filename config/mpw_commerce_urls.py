"""Explicit MojPlayWin route registry; underlying views retain release gates."""
from django.urls import path
from services import mpw_trx_commercial_web as commercial
from services import mpw_trx_public_pages as public
from services.mpw_trx_guest_commerce import patch_commercial, patch_public

patch_commercial(vars(commercial))
patch_public(vars(public))

urlpatterns = [
    path("commerce/trx-easy/", public.public_shop, name="mpw_trx_shop"),
    path("commerce/book/<int:product_id>/", public.product_checkout, name="mpw_trx_checkout"),
    path("commerce/trx-easy/purchases/", public.purchases, name="mpw_trx_purchases"),
    *[path(route, view) for route, view in commercial.COMMERCIAL_URLPATTERNS],
]
