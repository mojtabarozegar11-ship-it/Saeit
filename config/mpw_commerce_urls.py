"""Host-scoped commerce route registry.

These routes belong to the legacy merchant runtime. MojProp.top is guarded
before dispatch and never falls through to this merchant until its own
standalone commerce contract is proven.
"""
from django.urls import path
from services import mpw_trx_commercial_web as commercial
from services import mpw_trx_public_pages as public
from services.mpw_trx_guest_commerce import patch_commercial, patch_public
from services.mojprop_standalone_boundary import guard_legacy_commerce

patch_commercial(vars(commercial))
patch_public(vars(public))

urlpatterns = [
    path("commerce/trx-easy/", guard_legacy_commerce(public.public_shop), name="mpw_trx_shop"),
    path("commerce/book/<int:product_id>/", guard_legacy_commerce(public.product_checkout), name="mpw_trx_checkout"),
    path("commerce/trx-easy/purchases/", guard_legacy_commerce(public.purchases), name="mpw_trx_purchases"),
    *[path(route, guard_legacy_commerce(view)) for route, view in commercial.COMMERCIAL_URLPATTERNS],
]
