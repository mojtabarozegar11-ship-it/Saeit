from django.urls import path
from . import api, tycoon_api, world_api

urlpatterns = [
    path("world/", world_api.world_snapshot),
    path("world/actions/", world_api.world_action),
    path("tycoon/", tycoon_api.tycoon_snapshot),
    path("tycoon/actions/", tycoon_api.tycoon_action),
    path("gem-purchases/", tycoon_api.gem_purchase),
    path("realm/", api.realm),
    path("rewards/moj1-policy/", api.moj1_reward_policy),
    path("explore/", api.explore),
    path("migrate/", api.migrate),
    path("harvest/", api.harvest),
    path("manufacturing/labels/", api.issue_product_labels),
    path("manufacturing/delivery/", api.confirm_product_delivery),
    path("physical-codes/claim/", api.claim_code),
]

