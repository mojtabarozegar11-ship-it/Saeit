"""Same private buyer routes at root or when Passenger mounts a sub-URI.

On a cPanel Passenger sub-URI '/moj-prop-v141/', WSGI SCRIPT_NAME is stripped
from PATH_INFO. Never alter an existing application's root URL mapping.
The legacy-prefixed aliases below keep isolated tests and non-URI setups
compatible; named routes use the SCRIPT_NAME-aware short paths.
"""
from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path
from django.views.generic import RedirectView

from core.mojprop_v141_native_receipt_view import moj_prop_v141_native_invoice
from core.mojprop_v141_private_statement_view import moj_prop_v141_private_statement

_login = LoginView.as_view(template_name="mojprop/v141-isolated-login.html")
_logout = LogoutView.as_view()
_home = RedirectView.as_view(url="/moj-prop-v141/login/", permanent=False)

urlpatterns = [
    path("", _home, name="mojprop_v141_home"),
    path("login/", _login, name="mojprop_v141_isolated_login"),
    path("logout/", _logout, name="mojprop_v141_isolated_logout"),
    path("payment/<slug:reference>/", moj_prop_v141_native_invoice,
         name="moj_prop_v141_native_invoice"),
    path("statement/<str:challenge_ref>/", moj_prop_v141_private_statement,
         name="moj_prop_v141_private_statement"),
    # Fallback only for a Passenger application installed at domain root.
    path("moj-prop-v141/", _home),
    path("moj-prop-v141/login/", _login),
    path("moj-prop-v141/logout/", _logout),
    path("moj-prop-v141/payment/<slug:reference>/", moj_prop_v141_native_invoice),
    path("moj-prop-v141/statement/<str:challenge_ref>/",
         moj_prop_v141_private_statement),
]
