from django.urls import include, path
from . import views, sso_views
from . import trial_balance as reports

app_name = "enterprise_portal"

urlpatterns = [
    path("sso/consume/", sso_views.consume_ticket, name="sso_consume"),
    path("sso/otp/", sso_views.CompanySsoOtpStepUp.as_view(), name="sso_step_up"),
    path("assets/app.css", views.office_stylesheet, name="office_css"),
    path("secure-login/", views.CompanyLogin.as_view(), name="login"),
    path("logout/", views.CompanyLogout.as_view(), name="logout"),
    path("", views.dashboard, name="dashboard"),
    path("finance/", views.finance, name="finance"),
    path("ecosystem/", include("ecosystem_hub.urls")),
    path("finance/trial-balance/", reports.trial_balance, name="trial_balance"),
    path("finance/trial-balance.csv", reports.trial_balance_csv, name="trial_balance_csv"),
    path("inventory/", views.inventory, name="inventory"),
    path("tasks/", views.tasks, name="tasks"),
    path("tasks/new/", views.new_task, name="new_task"),
    path("letters/", views.letters, name="letters"),
    path("letters/new/", views.new_letter, name="new_letter"),
]
