"""Account-backed API only. Static /living-cities/play/ stays on the existing site."""
from django.urls import path

from . import api, auth_api, tycoon_api, world_api
from .host_scope import mojplaywin_only as scoped


urlpatterns = [
    path("world/", scoped(world_api.world_snapshot)),
    path("world/actions/", scoped(world_api.world_action)),
    path("tycoon/", scoped(tycoon_api.tycoon_snapshot)),
    path("tycoon/actions/", scoped(tycoon_api.tycoon_action)),
    path("gem-purchases/", scoped(tycoon_api.gem_purchase)),
    path("realm/", scoped(api.realm)),
    path("rewards/moj1-policy/", scoped(api.moj1_reward_policy)),
    path("explore/", scoped(api.explore)),
    path("migrate/", scoped(api.migrate)),
    path("harvest/", scoped(api.harvest)),
    path("manufacturing/labels/", scoped(api.issue_product_labels)),
    path("manufacturing/delivery/", scoped(api.confirm_product_delivery)),
    path("physical-codes/claim/", scoped(api.claim_code)),
    path("auth/csrf/", scoped(auth_api.csrf_view)),
    path("auth/login/", scoped(auth_api.login_view)),
    path("auth/logout/", scoped(auth_api.logout_view)),
    path("auth/me/", scoped(auth_api.me_view)),
]
