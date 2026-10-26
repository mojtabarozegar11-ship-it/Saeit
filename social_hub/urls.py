"""Mount only inside the independent personal Django deployment URLconf."""
from django.urls import path
from .portal import dashboard, read_status

urlpatterns = [
    path("", dashboard, name="mojtaba_social_command"),
    path("status/", read_status, name="mojtaba_social_status"),
]
