"""No public order-creation endpoint; private buyer login/receipt only."""
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path
from django.views.generic import RedirectView
from core.mojprop_v141_native_receipt_view import moj_prop_v141_native_invoice
from core.mojprop_v141_private_statement_view import moj_prop_v141_private_statement

urlpatterns=[
    path("moj-prop-v141/login/",
         LoginView.as_view(template_name="mojprop/v141-isolated-login.html"),
         name="mojprop_v141_isolated_login"),
    path("moj-prop-v141/logout/",LogoutView.as_view(),
         name="mojprop_v141_isolated_logout"),
    path("moj-prop-v141/",
         RedirectView.as_view(url="/moj-prop-v141/login/",permanent=False),
         name="mojprop_v141_home"),
    path("moj-prop-v141/payment/<slug:reference>/",
         moj_prop_v141_native_invoice,name="moj_prop_v141_native_invoice"),
    path("moj-prop-v141/statement/<str:challenge_ref>/",
         moj_prop_v141_private_statement,name="moj_prop_v141_private_statement"),
]
