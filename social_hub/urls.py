"""Mount only inside the independent personal Django deployment URLconf."""
from django.urls import path
from .portal import dashboard, read_status
from .official import public_channels, public_channels_json

urlpatterns = [
    path("", dashboard, name="mojtaba_social_command"),
    path("status/", read_status, name="mojtaba_social_status"),
    path("official/", public_channels, name="mojtaba_official_channels"),
    path("official.json", public_channels_json, name="mojtaba_official_channels_json"),
]
