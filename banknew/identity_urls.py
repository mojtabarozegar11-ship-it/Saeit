"""Not mounted on production until same-origin routing and OAuth are verified."""
from django.urls import path
from banknew.identity_views import start, finish, session_state, signout
urlpatterns = [
    path("auth/start/", start, name="mojpay-auth-start"),
    path("auth/finish/", finish, name="mojpay-auth-finish"),
    path("auth/session/", session_state, name="mojpay-auth-session"),
    path("auth/signout/", signout, name="mojpay-auth-signout"),
]
