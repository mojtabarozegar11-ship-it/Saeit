from django.urls import path
from .views import buyer_download, buyer_download_link, receive_tron_fulfillment

urlpatterns = [
    # Include under site root ONLY after operator review; no duplicate public routes.
    path('api/payments/tron/fulfill/', receive_tron_fulfillment,
         name='moj-commerce-tron-fulfill'),
    path('moj-commerce/orders/<str:order_ref>/download-link/', buyer_download_link,
         name='moj-commerce-download-link'),
    path('moj-commerce/download/<uuid:public_id>/<str:ticket>/', buyer_download,
         name='moj-commerce-download'),
]