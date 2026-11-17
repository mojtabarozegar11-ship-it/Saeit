"""Exactly the two real-world 20+FA views, no database, login, checkout or broker."""
from django.urls import path
from core.world20_views import worldwide_index, worldwide_language
from core.world20_prop_interest import localized_prop_interest
from core.world20_sitemap import mojplaywin_world_sitemap, mojplaywin_world_robots

urlpatterns = [
    path("world/<str:lang>/moj-prop-interest/", localized_prop_interest, name="mojplaywin_world_prop_interest"),
    path("sitemap.xml", mojplaywin_world_sitemap, name="world20_sitemap"),
    path("robots.txt", mojplaywin_world_robots, name="world20_robots"),
    path("world/", worldwide_index, name="mojplaywin_world_languages"),
    path("world/<str:lang>/", worldwide_language, name="mojplaywin_world_language"),
]
