"""Merchant proof is isolated from all public checkout routes."""
from django.urls import path
from .merchant_wallet_views import (
    merchant_wallet_page, merchant_challenge, merchant_verify,
)

app_name = "mpw_wallet_proof"
urlpatterns = [
    path("merchant/wallet-proof/", merchant_wallet_page, name="page"),
    path("merchant/wallet-proof/challenge/", merchant_challenge, name="challenge"),
    path("merchant/wallet-proof/verify/", merchant_verify, name="verify"),
]
