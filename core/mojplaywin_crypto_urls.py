"""Routes guarded against any non-MojPlayWin host in each view."""
from django.urls import path
from . import mojplaywin_crypto_gateway as gateway

urlpatterns = [
    path("", gateway.gateway_home, name="moj_crypto_home"),
    path("login/", gateway.signin, name="moj_crypto_login"),
    path("register/", gateway.signup, name="moj_crypto_register"),
    path("buy/<int:offer_id>/", gateway.buy, name="moj_crypto_buy"),
    path("invoice/<uuid:token>/", gateway.invoice_view, name="moj_crypto_invoice"),
    path("invoice/<uuid:token>/status/", gateway.invoice_status, name="moj_crypto_status"),
    path("invoice/<uuid:token>/verify/", gateway.submit_tx, name="moj_crypto_verify"),
    path("invoice/<uuid:token>/download/", gateway.download, name="moj_crypto_download"),
]
