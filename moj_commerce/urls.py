from django.urls import path
from .operations_views import merchant_dashboard, operator_scanner_health
from .views import buyer_download, buyer_download_link, receive_tron_fulfillment
from .wallet_views import create_wallet_challenge, verify_wallet_challenge
from .checkout_views import create_buyer_checkout, buyer_checkout_status

urlpatterns = [
    path('moj-commerce/merchants/<uuid:merchant_id>/dashboard/',
         merchant_dashboard, name='moj-commerce-merchant-dashboard'),
    path('moj-commerce/operator/scanner-health/',
         operator_scanner_health, name='moj-commerce-operator-scanner-health'),
    path('moj-commerce/merchants/<uuid:merchant_id>/products/<int:product_id>/checkout/',
         create_buyer_checkout, name='moj-commerce-buyer-checkout'),
    path('moj-commerce/orders/<str:order_ref>/status/',
         buyer_checkout_status, name='moj-commerce-checkout-status'),
    # Include under site root ONLY after operator review; no duplicate public routes.
    path('moj-commerce/merchants/<uuid:merchant_id>/addresses/<int:address_id>/challenge/',
         create_wallet_challenge, name='moj-commerce-wallet-challenge'),
    path('moj-commerce/merchants/<uuid:merchant_id>/addresses/<int:address_id>/verify/',
         verify_wallet_challenge, name='moj-commerce-wallet-verify'),
    path('api/payments/tron/fulfill/', receive_tron_fulfillment,
         name='moj-commerce-tron-fulfill'),
    path('moj-commerce/orders/<str:order_ref>/download-link/', buyer_download_link,
         name='moj-commerce-download-link'),
    path('moj-commerce/download/<uuid:public_id>/<str:ticket>/', buyer_download,
         name='moj-commerce-download'),
]