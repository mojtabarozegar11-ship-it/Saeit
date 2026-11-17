"""Exactly the two real-world 20+FA views, no database, login, checkout or broker."""
from django.urls import path
from core.world20_views import worldwide_index, worldwide_language

urlpatterns = [
    path("world/", worldwide_index, name="mojplaywin_world_languages"),
    path("world/<str:lang>/", worldwide_language, name="mojplaywin_world_language"),
]
