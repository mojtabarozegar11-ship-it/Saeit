"""Mount only inside the independent personal Django deployment URLconf."""
from django.urls import path
from django.contrib import admin
from .portal import dashboard, read_status, connection_plan
from .official import public_channels, public_channels_json
from .activation_views import activation_page, activation_json

urlpatterns = [
    path("login/", admin.site.login, name="mojtaba_social_login"),
    path("", dashboard, name="mojtaba_social_command"),
    path("status/", read_status, name="mojtaba_social_status"),
    path("connection-plan/", connection_plan, name="mojtaba_social_connection_plan"),
    path("activation/", activation_page, name="mojtaba_social_activation"),
    path("activation.json", activation_json, name="mojtaba_social_activation_json"),
    path("official/", public_channels, name="mojtaba_official_channels"),
    path("official.json", public_channels_json, name="mojtaba_official_channels_json"),
]
