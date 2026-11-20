"""Application-relative English routes for the isolated /moj-prop mount."""
from django.urls import path
from django.http import Http404
from django.shortcuts import render, redirect
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe
from prop_firm.simulation_identity_views import available, simulation_login, simulation_logout
from prop_firm.simulation_identity import is_verified_simulation_user
from prop_firm.simulation_checkout_views import checkout_page_context, start_simulation_checkout
from prop_firm.simulation_dashboard_views import simulation_dashboard
from prop_firm.simulation_payment_views import simulation_invoice_detail
from prop_firm.simulation_terminal_views import simulation_terminal

@never_cache
@require_safe
def landing(request):
    if request.get_host()!="mojplaywin.com" or not request.is_secure():
        raise Http404
    identity_available=available(request)
    context=checkout_page_context(request)
    context.update(simulation_identity_available=identity_available,
        simulation_identity_verified=identity_available and is_verified_simulation_user(request.user))
    response=render(request,"mojplaywin/moj_prop_simulation.html",context)
    response["X-Robots-Tag"]="noindex, nofollow"
    return response

@never_cache
@require_safe
def dashboard(request):
    if request.get_host()!="mojplaywin.com" or not request.is_secure():
        raise Http404
    if not request.user.is_authenticated:
        return redirect("moj_prop_landing")
    return simulation_dashboard(request)

urlpatterns=[
    path("",landing,name="moj_prop_landing"),
    path("dashboard/",dashboard,name="moj_prop_dashboard"),
    path("account/login/",simulation_login,name="moj_prop_simulation_login"),
    path("account/logout/",simulation_logout,name="moj_prop_simulation_logout"),
    path("checkout/start/",start_simulation_checkout,name="moj_prop_simulation_checkout"),
    path("invoice/<slug:order_ref>/",simulation_invoice_detail,name="moj_prop_simulation_invoice"),
    path("account/<int:account_id>/terminal/",simulation_terminal,name="moj_prop_simulation_terminal"),
]
