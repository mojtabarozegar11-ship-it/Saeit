"""Only two private v1.4.1 endpoints for isolated Django session HTTP CI.

These are the SAME view functions as production, not mocked responses.
The public site's complete URLconf is source-checked separately and NEVER
served or deployed by this file.
"""
from django.urls import path
from core.mojprop_v141_info_view import moj_prop_v141_public_info
from core.mojprop_v141_lead_view import moj_prop_v141_interest
from core.mojprop_v141_private_statement_view import moj_prop_v141_private_statement
from core.mojprop_v141_private_portfolio_view import moj_prop_v141_private_portfolio

urlpatterns = [
    path("moj-prop-v141-info/", moj_prop_v141_public_info, name="moj_prop_v141_public_info"),
    path("moj-prop-v141-interest/", moj_prop_v141_interest, name="moj_prop_v141_interest"),
    path(
        "moj-prop-v141/statement/<slug:challenge_ref>/",
        moj_prop_v141_private_statement,
        name="moj_prop_v141_private_statement",
    ),
    path(
        "moj-prop-v141/portfolio/<slug:challenge_ref>/",
        moj_prop_v141_private_portfolio,
        name="moj_prop_v141_private_portfolio",
    ),
]
